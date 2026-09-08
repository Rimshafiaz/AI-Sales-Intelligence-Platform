from app.integrations.social_enrichment import SocialEnrichmentProvider, social_profile_target
from app.schemas.social_enrichment import SocialEnrichmentRequest, SocialEnrichmentResponse


class SocialEnrichmentError(Exception):
    pass


def enrich_social_profiles(
    request: SocialEnrichmentRequest,
    provider: SocialEnrichmentProvider,
) -> SocialEnrichmentResponse:
    targets = []
    for profile_url in request.profile_urls:
        target = social_profile_target(str(profile_url))
        if target is None:
            raise SocialEnrichmentError(
                "Social enrichment supports public Instagram, Facebook, and TikTok profile URLs only."
            )
        targets.append(target)
    return SocialEnrichmentResponse(observations=provider.enrich(targets))
