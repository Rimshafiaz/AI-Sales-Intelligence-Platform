from pathlib import Path

from crewai import Task

from app.ai.agents.strategy_agent import create_strategy_agent
from app.ai.config_loader import render_task_config
from app.schemas.agent_outputs import (
    NewsAgentOutput,
    PainPointAgentOutput,
    ResearchAgentOutput,
    StrategyAgentOutput,
    TechnologyAgentOutput,
)


OPPORTUNITY_RUBRIC_PATH = (
    Path(__file__).parent.parent / "rubrics" / "opportunity_rubric.md"
)


def load_opportunity_rubric() -> str:
    if not OPPORTUNITY_RUBRIC_PATH.is_file():
        raise FileNotFoundError(
            f"Opportunity rubric not found: {OPPORTUNITY_RUBRIC_PATH}"
        )

    rubric = OPPORTUNITY_RUBRIC_PATH.read_text(encoding="utf-8").strip()
    if not rubric:
        raise ValueError("Opportunity rubric cannot be blank.")

    return rubric


def create_strategy_task(
    company_name: str,
    research_output: ResearchAgentOutput,
    technology_output: TechnologyAgentOutput,
    news_output: NewsAgentOutput,
    pain_point_output: PainPointAgentOutput,
) -> Task:
    clean_company_name = company_name.strip()
    if not clean_company_name:
        raise ValueError("Company name cannot be blank.")

    config = render_task_config(
        "strategy_task",
        company_name=clean_company_name,
        opportunity_rubric=load_opportunity_rubric(),
        research_output=research_output.model_dump_json(indent=2),
        technology_output=technology_output.model_dump_json(indent=2),
        news_output=news_output.model_dump_json(indent=2),
        pain_point_output=pain_point_output.model_dump_json(indent=2),
    )

    return Task(
        description=config["description"],
        expected_output=config["expected_output"],
        agent=create_strategy_agent(),
        output_pydantic=StrategyAgentOutput,
    )
