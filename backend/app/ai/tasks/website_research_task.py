from crewai import Task
from crewai.tools import BaseTool

from app.ai.agents.website_research_agent import create_website_research_agent
from app.ai.config_loader import render_task_config
from app.schemas.agent_outputs import WebsiteResearchOutput
from app.schemas.website_research import WebsiteResearchHandoff


def create_website_research_task(
    handoff: WebsiteResearchHandoff,
    tools: tuple[BaseTool, BaseTool, BaseTool, BaseTool],
) -> Task:
    config = render_task_config(
        "website_research_task",
        handoff=handoff.model_dump_json(indent=2),
    )
    return Task(
        description=config["description"],
        expected_output=config["expected_output"],
        agent=create_website_research_agent(tools),
        tools=list(tools),
        output_pydantic=WebsiteResearchOutput,
    )
