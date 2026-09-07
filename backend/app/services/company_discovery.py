from urllib.parse import urlparse

from app.ai.context import build_research_evidence_context
from app.ai.tasks.company_discovery_task import (
    create_company_discovery_task,
    run_company_discovery_task,
)
from app.ai.tasks.goal_parser_task import (
    create_goal_parser_task,
    run_goal_parser_task,
)
from app.ai.tasks.qualification_task import (
    create_qualification_task,
    run_qualification_task,
)
from app.core.config import settings
from app.integrations.search_provider import (
    CollectedSource,
    TavilySearchProvider,
    create_tavily_search_provider,
)
from app.schemas.company_discovery import (
    SUPPORTED_GOAL_TYPES,
    UNSUPPORTED_GOAL_MESSAGE,
    CompanyDiscoveryRequest,
    CompanyDiscoveryResponse,
    DiscoveryObjective,
    ParseDiscoveryRequest,
    QualificationTaskOutput,
    company_discovery_response_from_task_output,
)


def check_supported_objective(
    objective: DiscoveryObjective,
) -> tuple[bool, str | None]:
    if objective.goal_type not in SUPPORTED_GOAL_TYPES:
        return False, UNSUPPORTED_GOAL_MESSAGE
    if not objective.offering:
        return (
            False,
            "Say what you are offering so we know what a good match looks "
            "like, for example: website redesign services.",
        )
    if not objective.target_sectors:
        return (
            False,
            "Add the business category you are looking for, for example: "
            "dental clinics or beauty salons.",
        )
    if not objective.target_geographies:
        return (
            False,
            "Add the city or region to search, for example: Lahore or Toronto.",
        )
    return True, None

DISCOVERY_RESULTS_PER_QUERY = 8
DISCOVERY_SEARCH_DEPTH = "advanced"
DISCOVERY_MAX_SOURCES = 20
DISCOVERY_EVIDENCE_SOURCES = 20
MAX_DISCOVERY_QUERIES = 5
WEBSITE_LOOKUP_RESULTS = 3


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


def _join_list_items(items: list[str]) -> str:
    return ", ".join(items) if items else "not specified"


def build_objective_context(
    goal: str | None,
    objective: DiscoveryObjective | None,
) -> str:
    if objective is None:
        return "Not provided. Match the listed criteria."

    lines = [
        f"- Goal type: {objective.goal_type}",
        f"- Seller role: {objective.seller_role or 'not specified'}",
        f"- Offering: {objective.offering or 'not specified'}",
        f"- Target sectors: {_join_list_items(objective.target_sectors)}",
        f"- Target geographies: {_join_list_items(objective.target_geographies)}",
        f"- Company size: {objective.company_size or 'not specified'}",
        f"- Stage: {objective.stage or 'not specified'}",
        f"- Triggers: {_join_list_items(objective.triggers)}",
        f"- Signals to look for: {_join_list_items(objective.signals_to_look_for)}",
        f"- Decision makers: {_join_list_items(objective.decision_makers)}",
        f"- Fit rubric: {objective.fit_rubric}",
        f"- Desired outcome: {objective.desired_outcome}",
    ]

    if goal:
        lines.insert(0, f"- Original request: {goal}")

    return "\n".join(lines)


def collect_discovery_sources(
    criteria: CompanyDiscoveryRequest,
    search_provider: TavilySearchProvider,
    queries: list[str] | None = None,
) -> list[CollectedSource]:
    effective_queries = list(queries)[:5] if queries else build_discovery_queries(criteria)
    seen_domains: set[str] = set()
    sources: list[CollectedSource] = []

    for query in effective_queries:
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
    objective_queries = (
        list(criteria.objective.search_queries)
        if criteria.objective
        else None
    )
    collected_sources = collect_discovery_sources(
        criteria, search_provider, objective_queries,
    )
    if not collected_sources:
        return CompanyDiscoveryResponse(candidates=[])

    evidence_context = build_research_evidence_context(
        collected_sources[:DISCOVERY_EVIDENCE_SOURCES]
    )
    discovery_task = create_company_discovery_task(
        criteria=criteria,
        evidence_context=evidence_context,
        objective_context=build_objective_context(
            criteria.goal, criteria.objective,
        ),
    )
    task_output = run_company_discovery_task(discovery_task)

    return company_discovery_response_from_task_output(task_output)


def parse_discovery_objective(
    request: ParseDiscoveryRequest,
) -> DiscoveryObjective:
    task = create_goal_parser_task(request)
    return run_goal_parser_task(task)


def _name_tokens(name: str) -> set[str]:
    stop_words = {"the", "and", "of", "for", "ltd", "limited", "private", "pvt", "co", "company"}
    return {
        token
        for token in name.lower().replace("&", " ").split()
        if token not in stop_words and len(token) > 1
    }


def _domain_matches_company(domain: str, name: str) -> bool:
    domain_core = _domain_of(domain).split(".")[0].replace("-", "")
    if not domain_core:
        return False
    tokens = _name_tokens(name)
    if not tokens:
        return False
    compact_name = "".join(tokens)
    return (
        compact_name in domain_core
        or domain_core in compact_name
        or any(token in domain_core for token in tokens if len(token) > 3)
    )


def _lookup_official_website(
    candidate_name: str,
    geography: str,
    search_provider: TavilySearchProvider,
) -> str | None:
    query = f"{candidate_name} {geography} official website".strip()
    try:
        results = search_provider.search(
            query,
            max_results=WEBSITE_LOOKUP_RESULTS,
            search_depth="basic",
        )
    except Exception:
        return None

    for result in results:
        domain = _domain_of(result.url)
        if not domain:
            continue
        if _domain_matches_company(domain, candidate_name):
            return result.url
    return None




def qualify_candidates(
    objective: DiscoveryObjective | None,
    response: CompanyDiscoveryResponse,
    search_provider: TavilySearchProvider,
) -> CompanyDiscoveryResponse:
    if not response.candidates:
        return response

    geography = " ".join(objective.target_geographies) if objective else ""
    verification_lines: list[str] = []
    for index, candidate in enumerate(response.candidates, start=1):
        found_url: str | None = None
        if candidate.website is None:
            found_url = _lookup_official_website(
                candidate.company_name, geography, search_provider,
            )
        found_text = (
            f"official website found: {found_url}"
            if found_url
            else (
                f"candidate already supplied website: {candidate.website}"
                if candidate.website
                else "no official website found in verification"
            )
        )
        verification_lines.append(
            f"{index}. {candidate.company_name} | industry: "
            f"{candidate.industry or 'unknown'} | {found_text} | description: "
            f"{candidate.short_description or 'none'}"
        )
        if found_url and candidate.website is None:
            candidate.website = found_url

    candidates_context = "\n".join(verification_lines)
    objective_context = build_objective_context(None, objective)

    try:
        qualification_task = create_qualification_task(
            objective_context=objective_context,
            candidates_context=candidates_context,
        )
        qualified: QualificationTaskOutput = run_qualification_task(qualification_task)
    except Exception:
        return response

    qualified_by_name = {
        entry.company_name.casefold(): entry for entry in qualified.candidates
    }

    for candidate in response.candidates:
        entry = qualified_by_name.get(candidate.company_name.casefold())
        if entry is None:
            continue
        candidate.fit_score = entry.fit_score
        candidate.fit_tier = entry.fit_tier
        candidate.fit_reason = entry.fit_reason

    response.candidates.sort(
        key=lambda item: (
            item.fit_score is not None,
            item.fit_score if item.fit_score is not None else -1,
        ),
        reverse=True,
    )
    return response


def discover_companies(
    criteria: CompanyDiscoveryRequest,
) -> CompanyDiscoveryResponse:
    search_provider = create_tavily_search_provider(settings.tavily_api_key)
    response = generate_discovery_candidates(criteria, search_provider)
    return qualify_candidates(criteria.objective, response, search_provider)
