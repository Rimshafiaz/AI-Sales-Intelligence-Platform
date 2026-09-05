from urllib.parse import urlparse

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

DISCOVERY_RESULTS_PER_QUERY = 8
DISCOVERY_SEARCH_DEPTH = "advanced"
DISCOVERY_MAX_SOURCES = 16
MAX_DISCOVERY_QUERIES = 4


def build_discovery_queries(criteria: CompanyDiscoveryRequest) -> list[str]:
    industry = criteria.industry
    region = criteria.region
    company_size = criteria.company_size
    keywords = criteria.keywords

    queries: list[str] = []

    if industry and region:
        queries.append(f"top {industry} companies in {region}")
        queries.append(f"leading {industry} firms in {region}")
    elif industry:
        queries.append(f"top {industry} companies")
    elif region:
        queries.append(f"major companies in {region}")

    if keywords:
        if region:
            queries.append(f"{keywords} companies in {region}")
        else:
            queries.append(f"{keywords} companies")

    if company_size:
        if industry and region:
            queries.append(
                f"{industry} companies in {region} with {company_size} employees"
            )
        elif industry:
            queries.append(f"{industry} companies with {company_size} employees")
        elif region:
            queries.append(f"companies in {region} with {company_size} employees")
        else:
            queries.append(f"companies with {company_size} employees")

    if not queries:
        queries.append("notable companies")

    unique_queries: list[str] = []
    for query in queries:
        if query not in unique_queries:
            unique_queries.append(query)

    return unique_queries[:MAX_DISCOVERY_QUERIES]


def _domain_of(url: str) -> str:
    netloc = urlparse(url).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


def collect_discovery_sources(
    criteria: CompanyDiscoveryRequest,
    search_provider: TavilySearchProvider,
) -> list[CollectedSource]:
    queries = build_discovery_queries(criteria)
    seen_domains: set[str] = set()
    sources: list[CollectedSource] = []

    for query in queries:
        results = search_provider.search(
            query,
            max_results=DISCOVERY_RESULTS_PER_QUERY,
            search_depth=DISCOVERY_SEARCH_DEPTH,
        )
        for source in results:
            domain = _domain_of(source.url)
            if domain in seen_domains:
                continue
            seen_domains.add(domain)
            sources.append(source)
            if len(sources) == DISCOVERY_MAX_SOURCES:
                return sources

    return sources


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
