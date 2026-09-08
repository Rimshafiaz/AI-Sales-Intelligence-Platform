from dataclasses import dataclass
from datetime import UTC, datetime
from time import sleep
from urllib.parse import urlparse

import httpx


PAGESPEED_RUN_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_RETRY_ATTEMPTS = 2


class PageSpeedProviderError(Exception):
    pass


@dataclass(frozen=True)
class MobilePerformanceMeasurement:
    final_url: str
    score: float
    retrieved_at: datetime


class PageSpeedInsightsProvider:
    def __init__(
        self,
        api_key: str,
        client: object | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
    ) -> None:
        if not api_key.strip():
            raise ValueError("PageSpeed API key cannot be blank.")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive.")
        if retry_attempts < 1:
            raise ValueError("retry_attempts must be at least 1.")
        self.api_key = api_key
        self.client = client
        self.timeout_seconds = timeout_seconds
        self.retry_attempts = retry_attempts

    def measure_mobile(self, website_url: str) -> MobilePerformanceMeasurement:
        requested_url = self._http_url(website_url)
        if requested_url is None:
            raise ValueError("Website URL must use http or https.")

        data = self._get(
            {
                "url": requested_url,
                "strategy": "mobile",
                "category": "performance",
                "key": self.api_key,
            }
        )
        score = self._performance_score(data)
        final_url = self._http_url(data.get("id")) or requested_url
        return MobilePerformanceMeasurement(
            final_url=final_url,
            score=score,
            retrieved_at=datetime.now(UTC),
        )

    def _get(self, params: dict[str, str]) -> dict[str, object]:
        for attempt in range(self.retry_attempts):
            try:
                if self.client is None:
                    with httpx.Client(timeout=self.timeout_seconds) as client:
                        response = client.get(PAGESPEED_RUN_URL, params=params)
                else:
                    response = self.client.get(
                        PAGESPEED_RUN_URL,
                        params=params,
                        timeout=self.timeout_seconds,
                    )
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise PageSpeedProviderError("PageSpeed returned an invalid response.")
                return data
            except PageSpeedProviderError:
                raise
            except (httpx.TimeoutException, httpx.NetworkError) as error:
                if attempt == self.retry_attempts - 1:
                    raise PageSpeedProviderError(
                        "PageSpeed did not respond. Try the website audit again later."
                    ) from error
                sleep(0.25)
            except httpx.HTTPStatusError as error:
                if error.response.status_code in {402, 429}:
                    raise PageSpeedProviderError(
                        "PageSpeed quota or rate limit was reached. Try again later."
                    ) from error
                raise PageSpeedProviderError(
                    "PageSpeed could not audit this website. Check the API configuration and try again."
                ) from error
            except (httpx.HTTPError, TypeError, ValueError) as error:
                raise PageSpeedProviderError(
                    "PageSpeed could not audit this website. Try again later."
                ) from error
        raise PageSpeedProviderError("PageSpeed could not audit this website. Try again later.")

    @staticmethod
    def _performance_score(data: dict[str, object]) -> float:
        lighthouse = data.get("lighthouseResult")
        categories = lighthouse.get("categories") if isinstance(lighthouse, dict) else None
        performance = categories.get("performance") if isinstance(categories, dict) else None
        raw_score = performance.get("score") if isinstance(performance, dict) else None
        if isinstance(raw_score, bool) or not isinstance(raw_score, (int, float)):
            raise PageSpeedProviderError("PageSpeed did not return a usable mobile performance score.")
        if not 0 <= raw_score <= 1:
            raise PageSpeedProviderError("PageSpeed returned an invalid mobile performance score.")
        return round(raw_score * 100, 1)

    @staticmethod
    def _http_url(value: object) -> str | None:
        if not isinstance(value, str):
            return None
        clean_value = value.strip()
        parsed = urlparse(clean_value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return None
        return clean_value


def create_pagespeed_provider(api_key: str | None) -> PageSpeedInsightsProvider:
    if api_key is None or not api_key.strip():
        raise PageSpeedProviderError("PageSpeed is not configured. Set PAGESPEED_API_KEY.")
    return PageSpeedInsightsProvider(api_key)
