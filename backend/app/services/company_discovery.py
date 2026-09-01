from app.ai.context import MAX_EVIDENCE_SOURCES, build_research_evidence_context
from app.ai.tasks.company_discovery_task import (
    create_company_discovery_task,
    run_company_discovery_task,
)
from app.core.config import settings
from app.integrations.search_provider import (
    CollectedSource,
    TavilySearchProvider,
    create_tavily_search_provider,
)
from app.schemas.company_discovery import (
    CompanyDiscoveryRequest,
    CompanyDiscoveryResponse,
    company_discovery_response_from_task_output,
)


def build_discovery_query(criteria: CompanyDiscoveryRequest) -> str:
    criteria_lines: list[str] = []

    if criteria.industry:
        criteria_lines.append(f"Industry: {criteria.industry}")
    if criteria.region:
        criteria_lines.append(f"Region: {criteria.region}")
    if criteria.company_size:
        criteria_lines.append(f"Company size: {criteria.company_size}")
    if criteria.keywords:
        criteria_lines.append(f"Keywords: {criteria.keywords}")

    formatted_criteria = "\n".join(f"- {line}" for line in criteria_lines)

    return (
        "Find publicly available sources about companies matching these criteria:\n"
        f"{formatted_criteria}\n\n"
        "Prefer official company websites and reliable public business sources. "
        "Return evidence that identifies the company, its website, and why it "
        "matches the criteria."
    )


def collect_discovery_sources(
    criteria: CompanyDiscoveryRequest,
    search_provider: TavilySearchProvider,
) -> list[CollectedSource]:
    query = build_discovery_query(criteria)
    return search_provider.search(query)


def generate_discovery_candidates(
    criteria: CompanyDiscoveryRequest,
    search_provider: TavilySearchProvider,
) -> CompanyDiscoveryResponse:
    collected_sources = collect_discovery_sources(criteria, search_provider)
    if not collected_sources:
        return CompanyDiscoveryResponse(candidates=[])

    evidence_context = build_research_evidence_context(
        collected_sources[:MAX_EVIDENCE_SOURCES]
    )
    discovery_task = create_company_discovery_task(
        criteria=criteria,
        evidence_context=evidence_context,
    )
    task_output = run_company_discovery_task(discovery_task)

    return company_discovery_response_from_task_output(task_output)


def discover_companies(
    criteria: CompanyDiscoveryRequest,
) -> CompanyDiscoveryResponse:
    search_provider = create_tavily_search_provider(settings.tavily_api_key)
    return generate_discovery_candidates(criteria, search_provider)
