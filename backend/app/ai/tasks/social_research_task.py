from crewai import Task
from crewai.tools import BaseTool

from app.ai.agents.social_research_agent import create_social_research_agent
from app.ai.config_loader import render_task_config
from app.schemas.agent_outputs import SocialResearchOutput
from app.schemas.social_research import SocialResearchHandoff


def create_social_research_task(
    handoff: SocialResearchHandoff,
    tools: tuple[BaseTool, BaseTool, BaseTool, BaseTool],
) -> Task:
    config = render_task_config(
        "social_research_task",
        handoff=handoff.model_dump_json(indent=2),
    )
    return Task(
        description=config["description"],
        expected_output=config["expected_output"],
        agent=create_social_research_agent(tools),
        tools=list(tools),
        output_pydantic=SocialResearchOutput,
    )
