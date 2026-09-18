from crewai import Agent
from crewai.tools import BaseTool

from app.ai.config_loader import get_agent_config
from app.ai.llm import get_llm


def create_social_research_agent(
    tools: tuple[BaseTool, BaseTool, BaseTool, BaseTool],
) -> Agent:
    return Agent(
        config=get_agent_config("social_research_agent"),
        # CrewAI performs a final structured-output conversion after the tool
        # loop. Keep the full project default available for that JSON response.
        llm=get_llm(),
        allow_delegation=False,
        tools=list(tools),
    )
