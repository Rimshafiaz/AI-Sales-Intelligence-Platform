from collections import defaultdict
from urllib.parse import urlparse

from app.integrations.business_discovery import DiscoveredBusiness, DiscoverySourceType
from app.schemas.company_discovery import (
    CompanyDiscoveryRequest,
    CompanyDiscoveryResponse,
    DiscoveredCompanyCandidate,
)


SOURCE_PRIORITY = {
    DiscoverySourceType.LOCAL_PLACES: 0,
    DiscoverySourceType.WEB_SEARCH: 1,
    DiscoverySourceType.SOCIAL_SEARCH: 2,
}


def merge_candidate_pool(
    criteria: CompanyDiscoveryRequest,
    businesses: list[DiscoveredBusiness],
) -> CompanyDiscoveryResponse:
    groups: list[list[DiscoveredBusiness]] = []
    key_to_group: dict[str, int] = {}
    for business in businesses:
        keys = business_identity_keys(business)
        matching_groups = {key_to_group[key] for key in keys if key in key_to_group}
        if len(matching_groups) > 1:
            primary_index = min(matching_groups)
            for group_index in sorted(matching_groups - {primary_index}, reverse=True):
                groups[primary_index].extend(groups[group_index])
                for key, index in tuple(key_to_group.items()):
                    if index == group_index:
                        key_to_group[key] = primary_index
                groups[group_index] = []
            group_index = primary_index
        elif matching_groups:
            group_index = matching_groups.pop()
        else:
            group_index = len(groups)
            groups.append([])
        groups[group_index].append(business)
        for key in keys:
            key_to_group[key] = group_index

    candidates = [
        group_to_candidate(criteria, group)
        for group in groups
        if group
    ]
    return CompanyDiscoveryResponse(candidates=candidates)


def business_identity_keys(business: DiscoveredBusiness) -> set[str]:
    keys = {f"provider:{business.provider}:{business.provider_record_id}"}
    if business.website:
        domain = normalized_domain(business.website)
        if domain:
            keys.add(f"domain:{domain}")
    if business.social_profile_url:
        keys.add(f"social:{business.social_profile_url.casefold()}")
    return keys


def group_to_candidate(
    criteria: CompanyDiscoveryRequest,
    group: list[DiscoveredBusiness],
) -> DiscoveredCompanyCandidate:
    ordered = sorted(group, key=lambda item: SOURCE_PRIORITY[item.source_type])
    primary = ordered[0]
    website = next((item.website for item in ordered if item.website), None)
    social_urls = list(
        dict.fromkeys(
            item.social_profile_url for item in ordered if item.social_profile_url
        )
    )
    source_urls = list(
        dict.fromkeys(item.source_url for item in ordered if item.source_url)
    )
    return DiscoveredCompanyCandidate(
        company_name=primary.name,
        website=website,
        industry=primary.category or criteria.industry,
        short_description=primary.formatted_address,
        match_explanation=(
            "Discovery sources returned this possible business identity. It has not "
            "been verified or qualified as an opportunity yet."
        ),
        supporting_source_urls=source_urls,
        source_provider=primary.provider,
        source_record_id=primary.provider_record_id,
        source_retrieved_at=primary.retrieved_at,
        source_data_release=primary.source_data_release,
        formatted_address=primary.formatted_address,
        business_status=primary.business_status,
        phone_number=primary.phone_number,
        website_verification_state=("listed_unverified" if website else None),
        discovery_source_types=list(dict.fromkeys(item.source_type.value for item in ordered)),
        social_profile_urls=social_urls,
    )


def normalized_domain(url: str) -> str | None:
    hostname = urlparse(url).hostname
    return hostname.casefold().removeprefix("www.") if hostname else None
