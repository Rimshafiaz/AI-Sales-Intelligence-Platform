from app.integrations.search_provider import CollectedSource, TavilySearchProvider
from app.schemas.company_discovery import CompanyDiscoveryRequest


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
