from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx


DEFAULT_TIMEOUT_SECONDS = 10.0
EXCERPT_LIMIT = 1_000
USER_AGENT = "AI-Sales-Intelligence-Platform/1.0"
IGNORED_TAGS = {"script", "style", "noscript"}


@dataclass(frozen=True)
class WebsiteMetadata:
    url: str
    title: str | None
    description: str | None
    excerpt: str | None
    source_type: str = "company_website"


class WebsiteMetadataCollector:
    def __init__(self, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive.")
        self.timeout_seconds = timeout_seconds

    def collect(self, website: str) -> WebsiteMetadata | None:
        if not self._is_http_url(website):
            return None

        try:
            with httpx.Client(
                follow_redirects=True,
                timeout=self.timeout_seconds,
                headers={"User-Agent": USER_AGENT},
            ) as client:
                response = client.get(website)
                response.raise_for_status()
        except httpx.HTTPError:
            return None

        content_type = response.headers.get("content-type", "").casefold()
        if "text/html" not in content_type:
            return None

        try:
            parser = _WebsiteHTMLParser()
            parser.feed(response.text)
            parser.close()
        except Exception:
            return None

        return WebsiteMetadata(
            url=str(response.url),
            title=self._clean_text(" ".join(parser.title_parts)),
            description=self._clean_text(parser.description),
            excerpt=self._clean_text(" ".join(parser.visible_text_parts), EXCERPT_LIMIT),
        )

    @staticmethod
    def _is_http_url(value: str) -> bool:
        parsed_url = urlparse(value.strip())
        return parsed_url.scheme in {"http", "https"} and parsed_url.netloc != ""

    @staticmethod
    def _clean_text(value: str | None, limit: int | None = None) -> str | None:
        if value is None:
            return None

        clean_value = " ".join(value.split())
        if not clean_value:
            return None

        return clean_value[:limit] if limit is not None else clean_value


class _WebsiteHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.description: str | None = None
        self.visible_text_parts: list[str] = []
        self._ignored_depth = 0
        self._inside_title = False
        self._inside_body = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
        if tag in IGNORED_TAGS:
            self._ignored_depth += 1
            return

        if tag == "title":
            self._inside_title = True
        elif tag == "body":
            self._inside_body = True
        elif tag == "meta" and self.description is None:
            attributes = {key.casefold(): value for key, value in attrs}
            if attributes.get("name", "").casefold() == "description":
                self.description = attributes.get("content")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag in IGNORED_TAGS and self._ignored_depth > 0:
            self._ignored_depth -= 1
        elif tag == "title":
            self._inside_title = False
        elif tag == "body":
            self._inside_body = False

    def handle_data(self, data: str) -> None:
        if self._ignored_depth > 0:
            return
        if self._inside_title:
            self.title_parts.append(data)
        elif self._inside_body:
            self.visible_text_parts.append(data)
