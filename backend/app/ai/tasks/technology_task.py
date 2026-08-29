from crewai import Task
from app.ai.agents.technology_agent import create_technology_agent
from app.ai.config_loader import render_task_config
from app.schemas.agent_outputs import TechnologyAgentOutput


def create_technology_task(
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
        "technology_task",
        company_name=clean_company_name,
        evidence_context=clean_evidence_context,
    )

    return Task(
        description=config["description"],
        expected_output=config["expected_output"],
        agent=create_technology_agent(),
        output_pydantic=TechnologyAgentOutput,
    )
