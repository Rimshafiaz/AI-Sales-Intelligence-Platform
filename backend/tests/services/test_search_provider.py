import pytest
from requests import ConnectionError as RequestsConnectionError
from requests import Timeout as RequestsTimeout

from app.integrations.search_provider import (
    CollectedSource,
    SearchProviderError,
    TavilySearchProvider,
    create_tavily_search_provider,
)


class FakeTavilyClient:
    def __init__(self, results=None, error=None):
        self.results = results or []
        self.error = error
        self.calls = 0

    def search(self, **kwargs):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return {"results": self.results}


def _result(url, title="  Title  ", content="  Some content  "):
    return {"url": url, "title": title, "content": content}


class TestProviderMapping:
    def test_missing_key_rejected(self):
        with pytest.raises(SearchProviderError):
            create_tavily_search_provider("  ")

    def test_results_normalized_and_bounded(self):
        results = [
            _result(f"https://example.com/{i}", title=f"  T{i}  ", content=f"  C{i}  ")
            for i in range(10)
        ]
        provider = TavilySearchProvider(api_key="key", client=FakeTavilyClient(results), max_results=3)
        sources = provider.search("query")
        assert len(sources) == 3
        assert sources[0].url == "https://example.com/0"
        assert sources[0].title == "T0"
        assert sources[0].excerpt == "C0"
        assert sources[0].source_type == "web_search"

    def test_invalid_urls_dropped(self):
        results = [_result("not-a-url"), _result("https://example.com/ok")]
        provider = TavilySearchProvider(api_key="key", client=FakeTavilyClient(results))
        sources = provider.search("query")
        assert [s.url for s in sources] == ["https://example.com/ok"]

    def test_blank_query_rejected(self):
        provider = TavilySearchProvider(api_key="key", client=FakeTavilyClient())
        with pytest.raises(ValueError):
            provider.search("   ")

    def test_timeout_retries_then_fails(self):
        client = FakeTavilyClient(error=RequestsTimeout("timeout"))
        provider = TavilySearchProvider(api_key="key", client=client, retry_attempts=2)
        with pytest.raises(SearchProviderError):
            provider.search("query")
        assert client.calls == 2

    def test_connection_error_surfaces_as_provider_error(self):
        client = FakeTavilyClient(error=RequestsConnectionError("down"))
        provider = TavilySearchProvider(api_key="key", client=client, retry_attempts=1)
        with pytest.raises(SearchProviderError):
            provider.search("query")

    def test_collected_source_defaults(self):
        source = CollectedSource(url="https://example.com", title=None, excerpt=None)
        assert source.source_type == "web_search"
