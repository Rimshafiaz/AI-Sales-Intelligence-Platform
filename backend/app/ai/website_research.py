from uuid import UUID

from crewai import Crew, Process, Task
from sqlalchemy.orm import Session

from app.ai.tasks.website_research_task import create_website_research_task
from app.ai.tools.website_research import (
    build_grounded_website_evidence,
    build_website_research_tools,
)
from app.models.campaign_candidate_selection import CampaignCandidateSelection
from app.models.company import Company
from app.models.research_request import ResearchRequest
from app.schemas.agent_outputs import WebsiteResearchOutput
from app.schemas.website_research import (
    GroundedWebsiteEvidenceResult,
    WebsiteResearchHandoff,
)


class WebsiteResearchError(ValueError):
    pass


def run_website_research_agent(
    db: Session,
    research_request: ResearchRequest,
    company: Company,
    selection: CampaignCandidateSelection | None,
    expected_user_id: UUID,
) -> WebsiteResearchOutput:
    tools = build_website_research_tools(
        db, research_request, company, selection, expected_user_id
    )
    starting_state = build_grounded_website_evidence(
        db, research_request, company, selection, expected_user_id
    )
    objective = research_request.objective or {}
    seller_goal = _required_context_text(objective, "goal")
    offering = _required_context_text(objective, "offering")
    handoff = WebsiteResearchHandoff(
        seller_goal=seller_goal,
        offering=offering,
        company_name=company.name,
        location=objective.get("location") or objective.get("region"),
        starting_state=starting_state,
    )
    output = _run_task(create_website_research_task(handoff, tools))
    final_state = build_grounded_website_evidence(
        db, research_request, company, selection, expected_user_id
    )
    return validate_website_research_output(output, final_state)


def _required_context_text(objective: dict, field: str) -> str:
    value = objective.get(field)
    if not isinstance(value, str) or not value.strip():
        raise WebsiteResearchError(f"Website research requires the persisted seller {field}.")
    return value.strip()


def validate_website_research_output(
    output: WebsiteResearchOutput,
    final_state: GroundedWebsiteEvidenceResult,
) -> WebsiteResearchOutput:
    validated = WebsiteResearchOutput.model_validate(output)
    if validated.website_status != final_state.website_status.value:
        raise WebsiteResearchError("Website research output changed the trusted website status.")
    evidence_keys = {item.key for item in final_state.evidence}
    if any(not set(item.evidence_keys) <= evidence_keys for item in validated.findings):
        raise WebsiteResearchError("Website research output cited unavailable evidence.")
    statements = [item.statement.casefold() for item in validated.findings]
    if len(statements) != len(set(statements)):
        raise WebsiteResearchError("Website research output duplicated a finding.")
    return validated


def _run_task(task: Task) -> WebsiteResearchOutput:
    crew = Crew(
        agents=[task.agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )
    crew.kickoff()
    if task.output is None or task.output.pydantic is None:
        raise WebsiteResearchError("Website Research Agent did not return valid structured output.")
    return WebsiteResearchOutput.model_validate(task.output.pydantic)
