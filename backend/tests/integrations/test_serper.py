from datetime import UTC

import httpx
import pytest

from app.integrations.serper import (
    SERPER_SEARCH_URL,
    SerperProviderError,
    SerperSearchProvider,
    create_serper_search_provider,
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

    def post(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def status_error(status_code: int):
    request = httpx.Request("POST", SERPER_SEARCH_URL)
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError("provider error", request=request, response=response)


class TestSerperSearchProvider:
    def test_missing_key_rejected(self):
        with pytest.raises(SerperProviderError):
            create_serper_search_provider(" ")

    def test_normalizes_bounded_organic_results(self):
        client = FakeClient([FakeResponse({"organic": [{"title": " Brand ", "link": "https://brand.example/x", "snippet": " Text "}, {"title": "Missing URL"}]})])
        provider = SerperSearchProvider("key", client=client)

        results = provider.search("boutiques Lahore", max_results=5)

        assert len(results) == 1
        assert results[0].title == "Brand"
        assert results[0].url == "https://brand.example/x"
        assert results[0].retrieved_at.tzinfo is UTC
        assert client.calls[0]["json"] == {"q": "boutiques Lahore", "num": 5, "hl": "en"}

    def test_timeout_retries_then_fails(self):
        provider = SerperSearchProvider("key", client=FakeClient([httpx.TimeoutException("timeout"), httpx.TimeoutException("timeout")]), retry_attempts=2)
        with pytest.raises(SerperProviderError, match="timed out"):
            provider.search("boutiques Lahore")

    def test_quota_error_is_honest(self):
        provider = SerperSearchProvider("key", client=FakeClient([FakeResponse({}, status_error(429))]))
        with pytest.raises(SerperProviderError, match="quota or rate limit"):
            provider.search("boutiques Lahore")
