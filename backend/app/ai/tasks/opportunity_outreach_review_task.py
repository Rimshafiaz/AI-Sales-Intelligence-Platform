from crewai import Task

from app.ai.agents.opportunity_outreach_reviewer_agent import (
    create_opportunity_outreach_reviewer_agent,
)
from app.ai.config_loader import render_task_config
from app.schemas.agent_outputs import BriefReviewOutput
from app.schemas.opportunity_outreach_review import OpportunityOutreachReviewHandoff


def create_opportunity_outreach_review_task(
    handoff: OpportunityOutreachReviewHandoff,
) -> Task:
    config = render_task_config(
        "opportunity_outreach_review_task",
        handoff=handoff.model_dump_json(indent=2),
    )
    return Task(
        description=config["description"],
        expected_output=config["expected_output"],
        agent=create_opportunity_outreach_reviewer_agent(),
        tools=[],
        output_pydantic=BriefReviewOutput,
    )
