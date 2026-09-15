import json

from crewai import Task

from app.ai.agents.opportunity_outreach_agent import create_opportunity_outreach_agent
from app.ai.config_loader import render_task_config
from app.schemas.agent_outputs import BriefReviewIssue, OpportunityOutreachOutput
from app.schemas.opportunity_outreach import OpportunityOutreachHandoff


def create_opportunity_outreach_task(
    handoff: OpportunityOutreachHandoff,
    revision_issues: list[BriefReviewIssue] | None = None,
) -> Task:
    config = render_task_config(
        "opportunity_outreach_task",
        handoff=handoff.model_dump_json(indent=2),
        revision_guidance=(
            json.dumps(
                [issue.model_dump(mode="json") for issue in revision_issues],
                indent=2,
            )
            if revision_issues
            else "No reviewer revision guidance. Produce the initial candidate."
        ),
    )
    return Task(
        description=config["description"],
        expected_output=config["expected_output"],
        agent=create_opportunity_outreach_agent(),
        tools=[],
        output_pydantic=OpportunityOutreachOutput,
    )
