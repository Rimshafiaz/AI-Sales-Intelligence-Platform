from crewai import Crew, Process, Task

from app.ai.agents.research_agent import create_research_agent
from app.ai.config_loader import render_task_config
from app.schemas.company_discovery import (
    DiscoveryObjective,
    ParseDiscoveryRequest,
)


def _format_hints(request: ParseDiscoveryRequest) -> str:
    lines: list[str] = []

    if request.objective_hint:
        lines.append(f"- Objective: {request.objective_hint}")
    if request.region:
        lines.append(f"- Region: {request.region}")
    if request.company_size:
        lines.append(f"- Company size: {request.company_size}")

    if not lines:
        return "None provided."

    return "\n".join(lines)


def create_goal_parser_task(request: ParseDiscoveryRequest) -> Task:
    goal_context = request.goal.strip()
    if not goal_context:
        raise ValueError("Discovery goal cannot be blank.")

    config = render_task_config(
        "goal_parser_task",
        goal_context=goal_context,
        hint_context=_format_hints(request),
    )

    return Task(
        description=config["description"],
        expected_output=config["expected_output"],
        agent=create_research_agent(),
        output_pydantic=DiscoveryObjective,
    )


def run_goal_parser_task(task: Task) -> DiscoveryObjective:
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
            "Goal parser task failed to produce valid structured output."
        )

    return output.pydantic
