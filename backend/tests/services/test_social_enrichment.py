from datetime import UTC, datetime

import pytest

from app.integrations.social_enrichment import SocialProfileTarget
from app.schemas.opportunity_models import EvidenceSource
from app.schemas.social_enrichment import (
    SocialEnrichmentRequest,
    SocialEnrichmentState,
    SocialPlatform,
    SocialProfileObservation,
)
from app.services.social_enrichment import SocialEnrichmentError, enrich_social_profiles


class RecordingProvider:
    def __init__(self, observations: list[SocialProfileObservation]):
        self.observations = observations
        self.targets: list[SocialProfileTarget] = []

    def enrich(self, targets: list[SocialProfileTarget]) -> list[SocialProfileObservation]:
        self.targets = targets
        return self.observations


def observation() -> SocialProfileObservation:
    return SocialProfileObservation(
        profile_url="https://www.instagram.com/glowboutique",
        platform=SocialPlatform.INSTAGRAM,
        state=SocialEnrichmentState.OBSERVED,
        handle="glowboutique",
        source=EvidenceSource(
            provider="apify",
            source_url="https://www.instagram.com/glowboutique",
            retrieved_at=datetime(2026, 9, 8, tzinfo=UTC),
        ),
    )


class TestSocialEnrichment:
    def test_passes_supported_public_profile_urls_to_the_provider(self):
        provider = RecordingProvider([observation()])
        request = SocialEnrichmentRequest(
            profile_urls=["https://www.instagram.com/glowboutique/"]
        )

        response = enrich_social_profiles(request, provider)

        assert response.observations == [observation()]
        assert provider.targets[0].platform is SocialPlatform.INSTAGRAM
        assert provider.targets[0].handle == "glowboutique"

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.instagram.com/p/post/",
            "https://www.linkedin.com/company/example/",
            "https://www.tiktok.com/example",
        ],
    )
    def test_rejects_non_profile_or_unsupported_urls(self, url: str):
        with pytest.raises(SocialEnrichmentError, match="Instagram, Facebook, and TikTok"):
            enrich_social_profiles(
                SocialEnrichmentRequest(profile_urls=[url]),
                RecordingProvider([]),
            )

    def test_rejects_duplicate_urls_before_provider_cost_is_incurred(self):
        with pytest.raises(ValueError, match="only once"):
            SocialEnrichmentRequest(
                profile_urls=[
                    "https://www.instagram.com/glowboutique/",
                    "https://www.instagram.com/glowboutique",
                ]
            )
