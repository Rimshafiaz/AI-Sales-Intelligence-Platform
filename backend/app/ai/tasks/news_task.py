from datetime import date

from crewai import Task

from app.ai.agents.news_agent import create_news_agent
from app.ai.config_loader import render_task_config
from app.schemas.agent_outputs import NewsAgentOutput


def create_news_task(
    company_name: str,
    evidence_context: str,
) -> Task:
    clean_company_name = company_name.strip()
    if not clean_company_name:
        raise ValueError("Company name cannot be blank.")

    clean_evidence_context = evidence_context.strip()
    if not clean_evidence_context:
        raise ValueError("Evidence context cannot be blank.")

    config = render_task_config(
        "news_task",
        company_name=clean_company_name,
        evidence_context=clean_evidence_context,
        current_date=date.today().isoformat(),
    )

    return Task(
        description=config["description"],
        expected_output=config["expected_output"],
        agent=create_news_agent(),
        output_pydantic=NewsAgentOutput,
    )
