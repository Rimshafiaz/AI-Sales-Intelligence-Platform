from dataclasses import dataclass
from time import sleep
from urllib.parse import urlparse

from requests import ConnectionError as RequestsConnectionError
from requests import Timeout as RequestsTimeout
from tavily import TavilyClient
from tavily.errors import TimeoutError as TavilyTimeoutError


DEFAULT_MAX_RESULTS = 5
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_RETRY_ATTEMPTS = 2
EXCERPT_LIMIT = 1_000


class SearchProviderError(Exception):
    pass


@dataclass(frozen=True)
class NormalizedSearchSource:
    url: str
    title: str | None
    excerpt: str | None
    source_type: str = "web_search"


class TavilySearchProvider:
    def __init__(
        self,
        api_key: str,
        client: TavilyClient | None = None,
        max_results: int = DEFAULT_MAX_RESULTS,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Tavily API key cannot be blank.")
        if not 1 <= max_results <= 20:
            raise ValueError("max_results must be between 1 and 20.")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive.")
        if retry_attempts < 1:
            raise ValueError("retry_attempts must be at least 1.")

        self.client = client or TavilyClient(api_key=api_key)
        self.max_results = max_results
        self.timeout_seconds = timeout_seconds
        self.retry_attempts = retry_attempts

    def search(self, query: str) -> list[NormalizedSearchSource]:
        clean_query = query.strip()
        if not clean_query:
            raise ValueError("Search query cannot be blank.")

        results = self._search(clean_query)
        sources: list[NormalizedSearchSource] = []
        seen_urls: set[str] = set()

        for result in results:
            source = self._normalize_source(result)
            if source is None or source.url in seen_urls:
                continue

            sources.append(source)
            seen_urls.add(source.url)

            if len(sources) == self.max_results:
                break

        return sources

    def _search(self, query: str) -> list[dict[str, object]]:
        for attempt in range(self.retry_attempts):
            try:
                response = self.client.search(
                    query=query,
                    search_depth="basic",
                    topic="general",
                    max_results=self.max_results,
                    include_answer=False,
                    include_raw_content=False,
                    include_images=False,
                    timeout=self.timeout_seconds,
                )
                results = response.get("results", [])
                return results if isinstance(results, list) else []
            except (TavilyTimeoutError, RequestsConnectionError, RequestsTimeout) as error:
                if attempt == self.retry_attempts - 1:
                    raise SearchProviderError(
                        "Tavily request timed out. Please try again."
                    ) from error
                sleep(0.25)
            except Exception as error:
                raise SearchProviderError(
                    "Tavily request failed. Check provider configuration and try again."
                ) from error

        raise SearchProviderError("Tavily request failed. Please try again.")

    @staticmethod
    def _normalize_source(result: dict[str, object]) -> NormalizedSearchSource | None:
        raw_url = result.get("url")
        if not isinstance(raw_url, str) or not TavilySearchProvider._is_http_url(raw_url):
            return None

        title = result.get("title")
        content = result.get("content")
        return NormalizedSearchSource(
            url=raw_url,
            title=title.strip() if isinstance(title, str) and title.strip() else None,
            excerpt=(
                content.strip()[:EXCERPT_LIMIT]
                if isinstance(content, str) and content.strip()
                else None
            ),
        )

    @staticmethod
    def _is_http_url(value: str) -> bool:
        parsed_url = urlparse(value)
        return parsed_url.scheme in {"http", "https"} and parsed_url.netloc != ""


def create_tavily_search_provider(api_key: str | None) -> TavilySearchProvider:
    if api_key is None or not api_key.strip():
        raise SearchProviderError("Tavily is not configured. Set TAVILY_API_KEY.")
    return TavilySearchProvider(api_key)
