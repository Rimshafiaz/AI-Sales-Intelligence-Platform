from crewai import Crew, Process, Task

from app.ai.agents.strategy_agent import create_strategy_agent
from app.ai.config_loader import render_task_config
from app.schemas.company_discovery import QualificationTaskOutput


def create_qualification_task(
    objective_context: str,
    candidates_context: str,
) -> Task:
    clean_objective = objective_context.strip()
    if not clean_objective:
        raise ValueError("Objective context cannot be blank.")

    clean_candidates = candidates_context.strip()
    if not clean_candidates:
        raise ValueError("Candidates context cannot be blank.")

    config = render_task_config(
        "qualification_task",
        objective_context=clean_objective,
        candidates_context=clean_candidates,
    )

    return Task(
        description=config["description"],
        expected_output=config["expected_output"],
        agent=create_strategy_agent(),
        output_pydantic=QualificationTaskOutput,
    )


def run_qualification_task(task: Task) -> QualificationTaskOutput:
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
            "Qualification task failed to produce valid structured output."
        )

    return output.pydantic
