from crewai import Agent
from app.ai.config_loader import get_agent_config
from app.ai.llm import get_llm


def create_technology_agent() -> Agent:
    config = get_agent_config("technology_agent")

    return Agent(
        config=config,
        llm=get_llm(),
        allow_delegation=False,
        tools=[],
    )
