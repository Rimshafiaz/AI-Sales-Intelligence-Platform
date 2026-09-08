from dataclasses import dataclass
from datetime import UTC, datetime
from time import sleep
from urllib.parse import urlparse

import httpx


SERPER_SEARCH_URL = "https://google.serper.dev/search"
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_RETRY_ATTEMPTS = 2
MAX_RESULTS_PER_QUERY = 10


class SerperProviderError(Exception):
    pass


@dataclass(frozen=True)
class SerperSearchResult:
    title: str
    url: str
    snippet: str | None
    retrieved_at: datetime


class SerperSearchProvider:
    def __init__(
        self,
        api_key: str,
        client: object | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Serper API key cannot be blank.")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive.")
        if retry_attempts < 1:
            raise ValueError("retry_attempts must be at least 1.")
        self.api_key = api_key
        self.client = client
        self.timeout_seconds = timeout_seconds
        self.retry_attempts = retry_attempts

    def search(self, query: str, max_results: int = MAX_RESULTS_PER_QUERY) -> list[SerperSearchResult]:
        clean_query = query.strip()
        if not clean_query:
            raise ValueError("Serper search query cannot be blank.")
        if not 1 <= max_results <= MAX_RESULTS_PER_QUERY:
            raise ValueError(
                f"max_results must be between 1 and {MAX_RESULTS_PER_QUERY}."
            )
        data = self._post({"q": clean_query, "num": max_results, "hl": "en"})
        organic = data.get("organic")
        if not isinstance(organic, list):
            organic = []
        retrieved_at = datetime.now(UTC)
        results: list[SerperSearchResult] = []
        for item in organic:
            result = self._normalize_result(item, retrieved_at)
            if result is not None:
                results.append(result)
        return results

    def _post(self, payload: dict[str, object]) -> dict[str, object]:
        headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}
        for attempt in range(self.retry_attempts):
            try:
                if self.client is None:
                    with httpx.Client(timeout=self.timeout_seconds) as client:
                        response = client.post(SERPER_SEARCH_URL, headers=headers, json=payload)
                else:
                    response = self.client.post(
                        SERPER_SEARCH_URL,
                        headers=headers,
                        json=payload,
                        timeout=self.timeout_seconds,
                    )
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise SerperProviderError("Serper returned an invalid response.")
                return data
            except SerperProviderError:
                raise
            except (httpx.TimeoutException, httpx.NetworkError) as error:
                if attempt == self.retry_attempts - 1:
                    raise SerperProviderError("Serper request timed out. Please try again.") from error
                sleep(0.25)
            except httpx.HTTPStatusError as error:
                if error.response.status_code in {402, 429}:
                    raise SerperProviderError("Serper quota or rate limit was reached. Please try again later.") from error
                raise SerperProviderError("Serper request failed. Check provider configuration and try again.") from error
            except (httpx.HTTPError, ValueError, TypeError) as error:
                raise SerperProviderError("Serper request failed. Check provider configuration and try again.") from error
        raise SerperProviderError("Serper request failed. Please try again.")

    @staticmethod
    def _normalize_result(value: object, retrieved_at: datetime) -> SerperSearchResult | None:
        if not isinstance(value, dict):
            return None
        title = SerperSearchProvider._clean_text(value.get("title"))
        url = SerperSearchProvider._http_url(value.get("link"))
        if title is None or url is None:
            return None
        return SerperSearchResult(
            title=title[:255],
            url=url,
            snippet=SerperSearchProvider._clean_text(value.get("snippet")),
            retrieved_at=retrieved_at,
        )

    @staticmethod
    def _clean_text(value: object) -> str | None:
        return value.strip() or None if isinstance(value, str) else None

    @staticmethod
    def _http_url(value: object) -> str | None:
        clean_value = SerperSearchProvider._clean_text(value)
        if clean_value is None:
            return None
        parsed = urlparse(clean_value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return None
        return clean_value


def create_serper_search_provider(api_key: str | None) -> SerperSearchProvider:
    if api_key is None or not api_key.strip():
        raise SerperProviderError("Serper is not configured. Set SERPER_API_KEY.")
    return SerperSearchProvider(api_key)
