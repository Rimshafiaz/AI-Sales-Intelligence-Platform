from crewai import Task
from app.ai.agents.pain_point_agent import create_pain_point_agent
from app.ai.config_loader import render_task_config
from app.schemas.agent_outputs import (
    NewsAgentOutput,
    PainPointAgentOutput,
    ResearchAgentOutput,
    TechnologyAgentOutput,
)


def create_pain_point_task(
    company_name: str,
    research_output: ResearchAgentOutput,
    technology_output: TechnologyAgentOutput,
    news_output: NewsAgentOutput,
) -> Task:
    clean_company_name = company_name.strip()
    if not clean_company_name:
        raise ValueError("Company name cannot be blank.")

    config = render_task_config(
        "pain_point_task",
        company_name=clean_company_name,
        research_output=research_output.model_dump_json(indent=2),
        technology_output=technology_output.model_dump_json(indent=2),
        news_output=news_output.model_dump_json(indent=2),
    )

    return Task(
        description=config["description"],
        expected_output=config["expected_output"],
        agent=create_pain_point_agent(),
        output_pydantic=PainPointAgentOutput,
    )
