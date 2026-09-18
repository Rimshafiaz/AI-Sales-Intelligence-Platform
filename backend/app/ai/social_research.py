from uuid import UUID

from crewai import Crew, Process, Task
from sqlalchemy.orm import Session

from app.ai.tasks.social_research_task import create_social_research_task
from app.ai.tools.social_research import (
    SocialResearchToolTrace,
    build_grounded_social_evidence,
    build_social_research_tools,
)
from app.models.campaign_candidate_selection import CampaignCandidateSelection
from app.models.company import Company
from app.models.research_request import ResearchRequest
from app.schemas.agent_outputs import SocialResearchOutput
from app.schemas.opportunity_models import EvidenceSignalType
from app.schemas.social_audit import (
    SocialCandidateDiscoveryState,
    SocialEnrichmentResultState,
    SocialVerificationState,
)
from app.schemas.social_research import GroundedSocialEvidenceResult, SocialResearchHandoff


class SocialResearchError(ValueError):
    pass


def run_social_research_agent(
    db: Session,
    research_request: ResearchRequest,
    company: Company,
    selection: CampaignCandidateSelection | None,
    expected_user_id: UUID,
) -> SocialResearchOutput:
    trace = SocialResearchToolTrace()
    tools = build_social_research_tools(
        db, research_request, company, selection, expected_user_id, trace
    )
    starting_state = build_grounded_social_evidence(
        db, research_request, company, selection, expected_user_id
    )
    objective = research_request.objective or {}
    handoff = SocialResearchHandoff(
        seller_goal=_required_context_text(objective, "goal"),
        offering=_required_context_text(objective, "offering"),
        company_name=company.name,
        location=objective.get("location") or objective.get("region"),
        starting_state=starting_state,
    )
    output = _run_task(create_social_research_task(handoff, tools))
    final_state = build_grounded_social_evidence(
        db, research_request, company, selection, expected_user_id
    )
    return validate_social_research_output(output, final_state, trace)


def validate_social_research_output(
    output: SocialResearchOutput,
    final_state: GroundedSocialEvidenceResult,
    trace: SocialResearchToolTrace,
) -> SocialResearchOutput:
    validated = SocialResearchOutput.model_validate(output)
    validated = validated.model_copy(
        update={"presence_status": _presence_status(final_state, trace)}
    )
    evidence_keys = {item.key for item in final_state.evidence}
    if any(not set(item.evidence_keys) <= evidence_keys for item in validated.findings):
        raise SocialResearchError("Social research output cited unavailable evidence.")
    statements = [item.statement.casefold() for item in validated.findings]
    if len(statements) != len(set(statements)):
        raise SocialResearchError("Social research output duplicated a finding.")
    gaps = " ".join(validated.evidence_gaps).casefold()
    verification_state = (
        trace.verification_state or final_state.check_states.verification.state
    )
    if (
        EvidenceSignalType.BUSINESS_ACTIVITY_CONFIRMED
        in final_state.unresolved_requirements
        and "business activity" not in gaps
    ):
        raise SocialResearchError("Missing business activity evidence must remain an explicit gap.")
    if (
        verification_state is SocialVerificationState.INSUFFICIENT_ACTIVITY_HISTORY
        and "histor" not in gaps
    ):
        raise SocialResearchError("Insufficient social activity history must remain an explicit gap.")
    if (
        verification_state is SocialVerificationState.DORMANCY_UNMEASURABLE
        and "dormancy" not in gaps
        and "latest" not in gaps
    ):
        raise SocialResearchError("Unmeasurable dormancy must remain an explicit gap.")
    return validated


def _presence_status(
    state: GroundedSocialEvidenceResult,
    trace: SocialResearchToolTrace,
) -> str:
    verification_state = (
        trace.verification_state or state.check_states.verification.state
    )
    discovery_state = trace.discovery_state or state.check_states.discovery.state
    enrichment_state = trace.enrichment_state or state.check_states.enrichment.state
    if any(
        item.signal_type is EvidenceSignalType.OFFICIAL_SOCIAL_PROFILE_CONFIRMED
        for item in state.evidence
    ):
        return "verified"
    if verification_state is SocialVerificationState.NO_OFFICIAL_PROFILE_VERIFIED:
        return "none_verified"
    if discovery_state is SocialCandidateDiscoveryState.NO_CANDIDATES:
        return "none_verified"
    if state.observations:
        return "partially_verified"
    if enrichment_state in {
        SocialEnrichmentResultState.UNAVAILABLE,
        SocialEnrichmentResultState.NOT_PERMITTED,
    }:
        return "unresolved"
    return "unresolved"


def _required_context_text(objective: dict, field: str) -> str:
    value = objective.get(field)
    if not isinstance(value, str) or not value.strip():
        raise SocialResearchError(f"Social research requires the persisted seller {field}.")
    return value.strip()


def _run_task(task: Task) -> SocialResearchOutput:
    crew = Crew(
        agents=[task.agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )
    try:
        crew.kickoff()
        if task.output is None or task.output.pydantic is None:
            raise SocialResearchError(
                "Social Research Agent did not return valid structured output."
            )
        return SocialResearchOutput.model_validate(task.output.pydantic)
    except SocialResearchError:
        raise
    except Exception as error:
        raise SocialResearchError(
            "Social Research Agent did not return valid structured output."
        ) from error
