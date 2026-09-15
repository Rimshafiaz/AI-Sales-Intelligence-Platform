from crewai import Agent
from crewai.tools import BaseTool

from app.ai.config_loader import get_agent_config
from app.ai.llm import get_llm


def create_social_research_agent(
    tools: tuple[BaseTool, BaseTool, BaseTool, BaseTool],
) -> Agent:
    return Agent(
        config=get_agent_config("social_research_agent"),
        llm=get_llm(max_tokens=2_000),
        allow_delegation=False,
        tools=list(tools),
    )
