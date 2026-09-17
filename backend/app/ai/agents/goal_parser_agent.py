from crewai import Agent

from app.ai.config_loader import get_agent_config
from app.ai.llm import get_llm


def create_goal_parser_agent() -> Agent:
    return Agent(
        config=get_agent_config("goal_parser_agent"),
        llm=get_llm(),
        allow_delegation=False,
        tools=[],
    )
