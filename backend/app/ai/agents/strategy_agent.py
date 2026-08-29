from crewai import Agent
from app.ai.config_loader import get_agent_config
from app.ai.llm import get_llm


def create_strategy_agent() -> Agent:
    config = get_agent_config("strategy_agent")

    return Agent(
        config=config,
        llm=get_llm(max_tokens=6_000),
        allow_delegation=False,
        tools=[],
    )
