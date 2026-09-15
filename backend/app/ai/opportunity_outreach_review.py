from crewai import Crew, Process, Task

from app.ai.tasks.opportunity_outreach_review_task import (
    create_opportunity_outreach_review_task,
)
from app.schemas.agent_outputs import BriefReviewOutput
from app.schemas.opportunity_outreach_review import OpportunityOutreachReviewHandoff
from app.services.opportunity_outreach_review import (
    OpportunityOutreachReviewError,
    build_opportunity_outreach_review_handoff,
    validate_review_output,
)


def run_opportunity_outreach_reviewer(
    handoff: OpportunityOutreachReviewHandoff,
) -> BriefReviewOutput:
    trusted_handoff = build_opportunity_outreach_review_handoff(
        handoff.context,
        handoff.candidate,
    )
    output = _run_task(create_opportunity_outreach_review_task(trusted_handoff))
    return validate_review_output(output, trusted_handoff)


def _run_task(task: Task) -> BriefReviewOutput:
    crew = Crew(
        agents=[task.agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )
    crew.kickoff()
    if task.output is None or task.output.pydantic is None:
        raise OpportunityOutreachReviewError(
            "Opportunity + Outreach Reviewer did not return valid structured output."
        )
    return BriefReviewOutput.model_validate(task.output.pydantic)
