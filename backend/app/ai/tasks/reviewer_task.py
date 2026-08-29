from crewai import Task

from app.ai.agents.reviewer_agent import create_reviewer_agent
from app.ai.config_loader import render_task_config
from app.ai.rubrics.loader import load_rubric
from app.schemas.agent_outputs import (
    NewsAgentOutput,
    PainPointAgentOutput,
    ResearchAgentOutput,
    ReviewerOutput,
    StrategyAgentOutput,
    TechnologyAgentOutput,
)


def create_reviewer_task(
    company_name: str,
    evidence_context: str,
    research_output: ResearchAgentOutput,
    technology_output: TechnologyAgentOutput,
    news_output: NewsAgentOutput,
    pain_point_output: PainPointAgentOutput,
    strategy_output: StrategyAgentOutput,
) -> Task:
    clean_company_name = company_name.strip()
    if not clean_company_name:
        raise ValueError("Company name cannot be blank.")

    clean_evidence_context = evidence_context.strip()
    if not clean_evidence_context:
        raise ValueError("Evidence context cannot be blank.")

    config = render_task_config(
        "reviewer_task",
        company_name=clean_company_name,
        evidence_context=clean_evidence_context,
        opportunity_rubric=load_rubric("opportunity_rubric.md"),
        reviewer_checklist=load_rubric("reviewer_checklist.md"),
        research_output=research_output.model_dump_json(indent=2),
        technology_output=technology_output.model_dump_json(indent=2),
        news_output=news_output.model_dump_json(indent=2),
        pain_point_output=pain_point_output.model_dump_json(indent=2),
        strategy_output=strategy_output.model_dump_json(indent=2),
    )

    return Task(
        description=config["description"],
        expected_output=config["expected_output"],
        agent=create_reviewer_agent(),
        output_pydantic=ReviewerOutput,
    )
