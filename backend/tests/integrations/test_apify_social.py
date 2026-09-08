from datetime import UTC

import httpx
import pytest

from app.integrations.apify_social import (
    APIFY_RUN_SYNC_DATASET_URL,
    ApifySocialEnrichmentProvider,
    ApifySocialProviderError,
    create_apify_social_enrichment_provider,
)
from app.integrations.social_enrichment import social_profile_target
from app.schemas.social_enrichment import SocialEnrichmentState, SocialPlatform


class FakeResponse:
    def __init__(self, data: object, error: Exception | None = None):
        self.data = data
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise self.error

    def json(self):
        return self.data


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def target(url: str):
    result = social_profile_target(url)
    assert result is not None
    return result


def provider(client: object) -> ApifySocialEnrichmentProvider:
    return ApifySocialEnrichmentProvider(
        api_token="token",
        instagram_actor_id="apify/instagram-profile-scraper",
        facebook_actor_id="apify/facebook-pages-scraper",
        tiktok_actor_id="coregent/tiktok-profile-scraper",
        client=client,
    )


def status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://api.apify.com")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError("provider error", request=request, response=response)


class TestApifySocialEnrichmentProvider:
    def test_missing_token_is_rejected(self):
        with pytest.raises(ApifySocialProviderError):
            create_apify_social_enrichment_provider(
                " ", "instagram", "facebook", "tiktok"
            )

    def test_normalizes_observed_instagram_profile_with_public_post_dates(self):
        client = FakeClient(
            [
                FakeResponse(
                    [
                        {
                            "username": "glowboutique",
                            "fullName": "Glow Boutique",
                            "url": "https://www.instagram.com/glowboutique/",
                            "id": "ig-123",
                            "biography": "Lahore fashion",
                            "externalUrl": "https://glow.example",
                            "businessEmail": "hello@glow.example",
                            "followersCount": 4200,
                            "postsCount": 18,
                            "verified": False,
                            "businessCategoryName": "Shopping & retail",
                            "latestPosts": [
                                {"takenAt": "2026-09-01T12:00:00Z"},
                                {"timestamp": 1754006400},
                            ],
                        }
                    ]
                )
            ]
        )

        observations = provider(client).enrich(
            [target("https://www.instagram.com/glowboutique/")]
        )

        assert len(observations) == 1
        observation = observations[0]
        assert observation.platform is SocialPlatform.INSTAGRAM
        assert observation.state is SocialEnrichmentState.OBSERVED
        assert observation.display_name == "Glow Boutique"
        assert observation.provider_profile_id == "ig-123"
        assert str(observation.external_url) == "https://glow.example/"
        assert observation.follower_count == 4200
        assert observation.latest_public_post_at.isoformat() == "2026-09-01T12:00:00+00:00"
        assert len(observation.recent_public_post_dates) == 2
        assert observation.source.provider == "apify"
        assert observation.source.provider_record_id == "apify/instagram-profile-scraper:ig-123"
        assert observation.source.retrieved_at.tzinfo is UTC
        assert client.calls[0]["url"] == APIFY_RUN_SYNC_DATASET_URL.format(
            actor_id="apify~instagram-profile-scraper"
        )
        assert client.calls[0]["json"] == {
            "usernames": ["https://www.instagram.com/glowboutique"]
        }
        assert client.calls[0]["params"]["maxItems"] == 20

    def test_marks_a_private_profile_as_unavailable_without_a_negative_claim(self):
        client = FakeClient(
            [
                FakeResponse(
                    [
                        {
                            "username": "privatebrand",
                            "url": "https://www.instagram.com/privatebrand/",
                            "private": True,
                        }
                    ]
                )
            ]
        )

        observation = provider(client).enrich(
            [target("https://www.instagram.com/privatebrand/")]
        )[0]

        assert observation.state is SocialEnrichmentState.UNAVAILABLE
        assert observation.is_private is True
        assert observation.detail == "The profile is private, so public content is unavailable."
        assert observation.biography is None

    def test_uses_platform_specific_actor_inputs(self):
        client = FakeClient([FakeResponse([]), FakeResponse([])])

        observations = provider(client).enrich(
            [
                target("https://www.facebook.com/glowboutique/"),
                target("https://www.tiktok.com/@glowboutique/"),
            ]
        )

        assert len(observations) == 2
        assert client.calls[0]["json"] == {
            "startUrls": [{"url": "https://www.facebook.com/glowboutique"}]
        }
        assert client.calls[1]["json"] == {
            "profiles": ["https://www.tiktok.com/@glowboutique"],
            "includeRecentVideos": False,
            "maxTotalProfiles": 1,
        }

    def test_does_not_attach_an_unmatched_provider_record_to_a_requested_profile(self):
        client = FakeClient(
            [
                FakeResponse(
                    [
                        {
                            "username": "differentbrand",
                            "url": "https://www.instagram.com/differentbrand/",
                        }
                    ]
                )
            ]
        )

        observation = provider(client).enrich(
            [target("https://www.instagram.com/glowboutique/")]
        )[0]

        assert observation.state is SocialEnrichmentState.UNAVAILABLE
        assert observation.detail == "No matching public profile data was returned."

    def test_timeout_retries_then_fails(self):
        client = FakeClient([httpx.TimeoutException("timeout"), httpx.TimeoutException("timeout")])
        with pytest.raises(ApifySocialProviderError, match="timed out"):
            provider(client).enrich([target("https://www.instagram.com/glowboutique/")])
        assert len(client.calls) == 2

    def test_quota_error_is_honest(self):
        client = FakeClient([FakeResponse([], status_error(429))])
        with pytest.raises(ApifySocialProviderError, match="quota or rate limit"):
            provider(client).enrich([target("https://www.instagram.com/glowboutique/")])
