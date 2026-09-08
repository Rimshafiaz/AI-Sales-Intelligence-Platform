from crewai import Agent

from app.ai.config_loader import get_agent_config
from app.ai.llm import get_llm


def create_prospect_evidence_brief_agent(agent_name: str) -> Agent:
    return Agent(
        config=get_agent_config(agent_name),
        llm=get_llm(max_tokens=3_000),
        allow_delegation=False,
        tools=[],
    )
