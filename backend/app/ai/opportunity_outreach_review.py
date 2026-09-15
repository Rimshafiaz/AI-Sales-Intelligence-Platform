from crewai import Crew, Process, Task

from app.ai.tasks.opportunity_outreach_review_task import (
    create_opportunity_outreach_review_task,
)
from app.ai.opportunity_outreach import run_opportunity_outreach_agent
from app.schemas.agent_outputs import BriefReviewOutput, OpportunityOutreachOutput
from app.schemas.opportunity_outreach import OpportunityOutreachHandoff
from app.schemas.opportunity_outreach_review import OpportunityOutreachReviewHandoff
from app.services.opportunity_outreach_review import (
    OpportunityOutreachReviewError,
    OpportunityOutreachRejectedError,
    build_opportunity_outreach_review_handoff,
    validate_review_output,
)


MAX_OPPORTUNITY_OUTREACH_ATTEMPTS = 2


def run_reviewed_opportunity_outreach(
    handoff: OpportunityOutreachHandoff,
) -> OpportunityOutreachOutput:
    trusted_handoff = OpportunityOutreachHandoff.model_validate(handoff)
    revision_issues = None
    for _attempt in range(MAX_OPPORTUNITY_OUTREACH_ATTEMPTS):
        candidate = run_opportunity_outreach_agent(
            trusted_handoff,
            revision_issues=revision_issues,
        )
        review_handoff = build_opportunity_outreach_review_handoff(
            trusted_handoff,
            candidate,
        )
        review = run_opportunity_outreach_reviewer(review_handoff)
        if review.approved:
            return candidate
        revision_issues = review.issues
    raise OpportunityOutreachRejectedError(revision_issues or [])


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
