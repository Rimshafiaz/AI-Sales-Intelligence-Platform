from datetime import UTC

import httpx
import pytest

from app.integrations.pagespeed import (
    PAGESPEED_RUN_URL,
    PageSpeedInsightsProvider,
    PageSpeedProviderError,
    create_pagespeed_provider,
)


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

    def get(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def status_error(status_code: int):
    request = httpx.Request("GET", PAGESPEED_RUN_URL)
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError("provider error", request=request, response=response)


class TestPageSpeedInsightsProvider:
    def test_missing_key_rejected(self):
        with pytest.raises(PageSpeedProviderError, match="not configured"):
            create_pagespeed_provider(" ")

    def test_measures_mobile_score_and_uses_mobile_strategy(self):
        client = FakeClient(
            [
                FakeResponse(
                    {
                        "id": "https://glow.example/",
                        "lighthouseResult": {
                            "categories": {"performance": {"score": 0.43}}
                        },
                    }
                )
            ]
        )
        provider = PageSpeedInsightsProvider("key", client=client)

        measurement = provider.measure_mobile("https://glow.example")

        assert measurement.score == 43.0
        assert measurement.final_url == "https://glow.example/"
        assert measurement.retrieved_at.tzinfo is UTC
        assert client.calls[0]["url"] == PAGESPEED_RUN_URL
        assert client.calls[0]["params"] == {
            "url": "https://glow.example",
            "strategy": "mobile",
            "category": "performance",
            "key": "key",
        }

    def test_timeout_retries_then_reports_unavailable(self):
        provider = PageSpeedInsightsProvider(
            "key",
            client=FakeClient([httpx.TimeoutException("timeout"), httpx.TimeoutException("timeout")]),
            retry_attempts=2,
        )

        with pytest.raises(PageSpeedProviderError, match="did not respond"):
            provider.measure_mobile("https://glow.example")

    def test_quota_error_is_honest(self):
        provider = PageSpeedInsightsProvider(
            "key",
            client=FakeClient([FakeResponse({}, status_error(429))]),
        )

        with pytest.raises(PageSpeedProviderError, match="quota or rate limit"):
            provider.measure_mobile("https://glow.example")

    def test_invalid_score_is_not_saved_as_a_measurement(self):
        provider = PageSpeedInsightsProvider(
            "key",
            client=FakeClient([FakeResponse({"lighthouseResult": {"categories": {}}})]),
        )

        with pytest.raises(PageSpeedProviderError, match="usable mobile performance score"):
            provider.measure_mobile("https://glow.example")
