from typing import Type

from crewai import Task
from pydantic import BaseModel

from app.ai.agents.prospect_evidence_brief_agents import create_prospect_evidence_brief_agent
from app.ai.config_loader import render_task_config
from app.schemas.agent_outputs import BriefFindingsOutput, BriefReviewerOutput, BriefStrategyOutput
from app.schemas.prospect_evidence_brief import (
    BusinessContextHandoff,
    DigitalPresenceHandoff,
    EvidenceQualityReviewHandoff,
    OpportunityDiagnosisHandoff,
    ProspectEvidenceBrief,
    PublicTractionHandoff,
    StrategyOutreachHandoff,
)


def _create_task(
    task_name: str,
    agent_name: str,
    output_model: Type[BaseModel],
    **values: str,
) -> Task:
    config = render_task_config(task_name, **values)
    return Task(
        description=config["description"],
        expected_output=config["expected_output"],
        agent=create_prospect_evidence_brief_agent(agent_name),
        output_pydantic=output_model,
    )


def create_brief_business_context_task(handoff: BusinessContextHandoff) -> Task:
    return _create_task(
        "brief_business_context_task",
        "brief_business_context_agent",
        BriefFindingsOutput,
        handoff=handoff.model_dump_json(indent=2),
    )


def create_brief_digital_presence_task(handoff: DigitalPresenceHandoff) -> Task:
    return _create_task(
        "brief_digital_presence_task",
        "brief_digital_presence_agent",
        BriefFindingsOutput,
        handoff=handoff.model_dump_json(indent=2),
    )


def create_brief_public_traction_task(handoff: PublicTractionHandoff) -> Task:
    return _create_task(
        "brief_public_traction_task",
        "brief_public_traction_agent",
        BriefFindingsOutput,
        handoff=handoff.model_dump_json(indent=2),
    )


def create_brief_opportunity_diagnosis_task(
    handoff: OpportunityDiagnosisHandoff,
) -> Task:
    return _create_task(
        "brief_opportunity_diagnosis_task",
        "brief_opportunity_diagnosis_agent",
        BriefFindingsOutput,
        handoff=handoff.model_dump_json(indent=2),
    )


def create_brief_strategy_outreach_task(
    handoff: StrategyOutreachHandoff,
    findings: list[BriefFindingsOutput],
) -> Task:
    return _create_task(
        "brief_strategy_outreach_task",
        "brief_strategy_outreach_agent",
        BriefStrategyOutput,
        handoff=handoff.model_dump_json(indent=2),
        prior_findings=_outputs_json(findings),
    )


def create_brief_evidence_quality_review_task(
    handoff: EvidenceQualityReviewHandoff,
    proposed_brief: ProspectEvidenceBrief,
) -> Task:
    return _create_task(
        "brief_evidence_quality_review_task",
        "brief_evidence_quality_reviewer_agent",
        BriefReviewerOutput,
        handoff=handoff.model_dump_json(indent=2),
        proposed_brief=proposed_brief.model_dump_json(indent=2),
    )


def _outputs_json(outputs: list[BriefFindingsOutput]) -> str:
    return "[\n" + ",\n".join(item.model_dump_json(indent=2) for item in outputs) + "\n]"
