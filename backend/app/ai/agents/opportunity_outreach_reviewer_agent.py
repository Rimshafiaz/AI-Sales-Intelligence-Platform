from crewai import Agent

from app.ai.config_loader import get_agent_config
from app.ai.llm import get_llm


def create_opportunity_outreach_reviewer_agent() -> Agent:
    return Agent(
        config=get_agent_config("opportunity_outreach_reviewer_agent"),
        llm=get_llm(max_tokens=1_500),
        allow_delegation=False,
        tools=[],
    )
