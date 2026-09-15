from crewai import Crew, Process, Task

from app.ai.tasks.opportunity_outreach_task import create_opportunity_outreach_task
from app.schemas.agent_outputs import OpportunityOutreachOutput
from app.schemas.opportunity_outreach import OpportunityOutreachHandoff
from app.services.aggregate_verdict import AggregateVerdict
from app.services.opportunity_outreach import (
    OpportunityOutreachError,
    validate_opportunity_outreach_output,
)


def run_opportunity_outreach_agent(
    handoff: OpportunityOutreachHandoff,
) -> OpportunityOutreachOutput:
    trusted_handoff = OpportunityOutreachHandoff.model_validate(handoff)
    if trusted_handoff.aggregate_verdict is not AggregateVerdict.QUALIFIED:
        raise OpportunityOutreachError(
            "Opportunity and outreach generation requires a QUALIFIED aggregate verdict."
        )
    output = _run_task(create_opportunity_outreach_task(trusted_handoff))
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
