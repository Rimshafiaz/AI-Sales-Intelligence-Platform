from crewai import Crew, Process, Task
from pydantic import TypeAdapter

from app.ai.tasks.opportunity_outreach_task import create_opportunity_outreach_task
from app.schemas.agent_outputs import BriefReviewIssue, OpportunityOutreachOutput
from app.schemas.opportunity_outreach import OpportunityOutreachHandoff
from app.services.aggregate_verdict import AggregateVerdict
from app.services.opportunity_outreach import (
    OpportunityOutreachError,
    validate_opportunity_outreach_output,
)


def run_opportunity_outreach_agent(
    handoff: OpportunityOutreachHandoff,
    revision_issues: list[BriefReviewIssue] | None = None,
) -> OpportunityOutreachOutput:
    trusted_handoff = OpportunityOutreachHandoff.model_validate(handoff)
    if trusted_handoff.aggregate_verdict is not AggregateVerdict.QUALIFIED:
        raise OpportunityOutreachError(
            "Opportunity and outreach generation requires a QUALIFIED aggregate verdict."
        )
    trusted_issues = (
        TypeAdapter(list[BriefReviewIssue]).validate_python(revision_issues)
        if revision_issues
        else None
    )
    output = _run_task(
        create_opportunity_outreach_task(trusted_handoff, trusted_issues)
    )
    return validate_opportunity_outreach_output(output, trusted_handoff)


def _run_task(task: Task) -> OpportunityOutreachOutput:
    crew = Crew(
        agents=[task.agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )
    crew.kickoff()
    if task.output is None or task.output.pydantic is None:
        raise OpportunityOutreachError(
            "Opportunity + Outreach Agent did not return valid structured output."
        )
    return OpportunityOutreachOutput.model_validate(task.output.pydantic)
