from crewai import Task

from app.ai.agents.strategy_agent import create_strategy_agent
from app.ai.config_loader import render_task_config
from app.ai.rubrics.loader import load_rubric
from app.schemas.agent_outputs import (
    NewsAgentOutput,
    PainPointAgentOutput,
    ResearchAgentOutput,
    StrategyAgentOutput,
    TechnologyAgentOutput,
)

def load_opportunity_rubric() -> str:
    return load_rubric("opportunity_rubric.md")


def create_strategy_task(
    company_name: str,
    research_output: ResearchAgentOutput,
    technology_output: TechnologyAgentOutput,
    news_output: NewsAgentOutput,
    pain_point_output: PainPointAgentOutput,
    guidance: str | None = None,
) -> Task:
    clean_company_name = company_name.strip()
    if not clean_company_name:
        raise ValueError("Company name cannot be blank.")

    clean_guidance = guidance.strip() if guidance else ""
    if clean_guidance:
        guidance_text = clean_guidance
    else:
        guidance_text = "No additional guidance."

    config = render_task_config(
        "strategy_task",
        company_name=clean_company_name,
        opportunity_rubric=load_opportunity_rubric(),
        research_output=research_output.model_dump_json(indent=2),
        technology_output=technology_output.model_dump_json(indent=2),
        news_output=news_output.model_dump_json(indent=2),
        pain_point_output=pain_point_output.model_dump_json(indent=2),
        guidance=guidance_text,
    )

    return Task(
        description=config["description"],
        expected_output=config["expected_output"],
        agent=create_strategy_agent(),
        output_pydantic=StrategyAgentOutput,
    )
