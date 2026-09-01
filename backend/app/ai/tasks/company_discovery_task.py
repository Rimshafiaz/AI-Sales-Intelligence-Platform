from crewai import Crew, Process, Task

from app.ai.agents.research_agent import create_research_agent
from app.ai.config_loader import render_task_config
from app.schemas.company_discovery import (
    CompanyDiscoveryRequest,
    CompanyDiscoveryTaskOutput,
)


def _format_criteria(criteria: CompanyDiscoveryRequest) -> str:
    lines: list[str] = []

    if criteria.industry:
        lines.append(f"- Industry: {criteria.industry}")
    if criteria.region:
        lines.append(f"- Region: {criteria.region}")
    if criteria.company_size:
        lines.append(f"- Company size: {criteria.company_size}")
    if criteria.keywords:
        lines.append(f"- Keywords: {criteria.keywords}")

    return "\n".join(lines)


def create_company_discovery_task(
    criteria: CompanyDiscoveryRequest,
    evidence_context: str,
) -> Task:
    clean_evidence_context = evidence_context.strip()
    if not clean_evidence_context:
        raise ValueError("Evidence context cannot be blank.")

    criteria_context = _format_criteria(criteria)
    if not criteria_context:
        raise ValueError("At least one discovery criterion is required.")

    config = render_task_config(
        "company_discovery_task",
        criteria_context=criteria_context,
        evidence_context=clean_evidence_context,
    )

    return Task(
        description=config["description"],
        expected_output=config["expected_output"],
        agent=create_research_agent(),
        output_pydantic=CompanyDiscoveryTaskOutput,
    )


def run_company_discovery_task(task: Task) -> CompanyDiscoveryTaskOutput:
    crew = Crew(
        agents=[task.agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )
    crew.kickoff()

    output = task.output
    if output is None or output.pydantic is None:
        raise RuntimeError(
            "Company discovery task failed to produce valid structured output."
        )

    return output.pydantic
