from app.ai.tasks.goal_parser_task import (
    create_goal_parser_task,
    run_goal_parser_task,
)
from app.core.config import settings
from app.integrations.open_places import create_open_places_provider
from app.integrations.serper import create_serper_search_provider
from app.schemas.company_discovery import (
    SUPPORTED_GOAL_TYPES,
    UNSUPPORTED_GOAL_MESSAGE,
    CompanyDiscoveryRequest,
    CompanyDiscoveryResponse,
    DiscoveryObjective,
    ParseDiscoveryRequest,
)
from app.services.candidate_pool import merge_candidate_pool
from app.services.local_business_discovery import collect_local_businesses
from app.services.web_candidate_discovery import discover_web_and_social_candidates


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


def parse_discovery_objective(
    request: ParseDiscoveryRequest,
) -> DiscoveryObjective:
    return run_goal_parser_task(create_goal_parser_task(request))


def discover_companies(
    criteria: CompanyDiscoveryRequest,
) -> CompanyDiscoveryResponse:
    local_provider = create_open_places_provider(settings.open_places_api_key)
    web_provider = create_serper_search_provider(settings.serper_api_key)
    local_candidates = collect_local_businesses(criteria, local_provider)
    web_candidates = discover_web_and_social_candidates(criteria, web_provider)
    return merge_candidate_pool(criteria, [*local_candidates, *web_candidates])
