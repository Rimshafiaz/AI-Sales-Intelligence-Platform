from dataclasses import dataclass
from html.parser import HTMLParser
import json
from urllib.parse import urljoin, urlparse

import httpx


DEFAULT_TIMEOUT_SECONDS = 10.0
EXCERPT_LIMIT = 1_000
IDENTITY_TEXT_LIMIT = 12_000
MAX_IDENTITY_PAGES = 3
USER_AGENT = "AI-Sales-Intelligence-Platform/1.0"
IGNORED_TAGS = {"script", "style", "noscript"}
IDENTITY_LINK_TERMS = (
    "about",
    "branch",
    "contact",
    "find-us",
    "location",
    "locations",
    "reach-us",
    "visit",
)
JSON_LD_IDENTITY_FIELDS = {
    "address",
    "addresscountry",
    "addresslocality",
    "addressregion",
    "name",
    "streetaddress",
    "telephone",
}


@dataclass(frozen=True)
class WebsiteMetadata:
    url: str
    title: str | None
    description: str | None
    excerpt: str | None
    source_type: str = "company_website"


@dataclass(frozen=True)
class WebsiteIdentityPage:
    url: str
    title: str | None
    description: str | None
    identity_text: str
    identity_links: tuple[str, ...]


@dataclass(frozen=True)
class WebsiteConversionSnapshot:
    url: str
    links: tuple[tuple[str, str], ...]


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

    def collect_identity_pages(
        self,
        website: str,
    ) -> tuple[WebsiteIdentityPage, ...]:
        if not self._is_http_url(website):
            return ()

        requested_host = self._normalized_host(website)
        if requested_host is None:
            return ()

        try:
            with httpx.Client(
                follow_redirects=True,
                timeout=self.timeout_seconds,
                headers={"User-Agent": USER_AGENT},
            ) as client:
                homepage = self._collect_identity_page(client, website)
                if homepage is None or not self._same_site(requested_host, homepage.url):
                    return ()

                pages = [homepage]
                for link in homepage.identity_links:
                    if len(pages) == MAX_IDENTITY_PAGES:
                        break
                    try:
                        page = self._collect_identity_page(client, link)
                    except httpx.HTTPError:
                        continue
                    if page is not None and self._same_site(requested_host, page.url):
                        pages.append(page)
        except httpx.HTTPError:
            return ()

        return tuple(pages)

    def collect_conversion_snapshot(
        self,
        website: str,
    ) -> WebsiteConversionSnapshot | None:
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
        if "text/html" not in response.headers.get("content-type", "").casefold():
            return None
        parser = self._parse(response.text)
        if parser is None:
            return None
        final_url = str(response.url)
        links = tuple(
            (urljoin(final_url, href), self._clean_text(label) or "")
            for href, label in parser.links
        )
        return WebsiteConversionSnapshot(url=final_url, links=links)

    @staticmethod
    def _identity_links(
        homepage_url: str,
        links: list[tuple[str, str]],
    ) -> tuple[str, ...]:
        homepage_host = WebsiteMetadataCollector._normalized_host(homepage_url)
        if homepage_host is None:
            return ()
        identity_links = []
        seen = set()
        for href, label in links:
            resolved = urljoin(homepage_url, href)
            if not WebsiteMetadataCollector._same_site(homepage_host, resolved):
                continue
            if not WebsiteMetadataCollector._is_identity_link(resolved, label):
                continue
            if resolved not in seen and resolved != homepage_url:
                identity_links.append(resolved)
                seen.add(resolved)
        return tuple(identity_links)

    def _collect_identity_page(
        self,
        client: httpx.Client,
        website: str,
    ) -> WebsiteIdentityPage | None:
        response = client.get(website)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").casefold()
        if "text/html" not in content_type:
            return None
        parser = self._parse(response.text)
        if parser is None:
            return None
        identity_text = self._clean_text(
            " ".join(
                value
                for value in (
                    " ".join(parser.title_parts),
                    parser.description,
                    " ".join(parser.visible_text_parts),
                    self._json_ld_identity_text(parser.json_ld_blocks),
                )
                if value
            ),
            IDENTITY_TEXT_LIMIT,
        )
        if identity_text is None:
            return None
        return WebsiteIdentityPage(
            url=str(response.url),
            title=self._clean_text(" ".join(parser.title_parts)),
            description=self._clean_text(parser.description),
            identity_text=identity_text,
            identity_links=self._identity_links(str(response.url), parser.links),
        )

    @staticmethod
    def _parse(content: str) -> "_WebsiteHTMLParser | None":
        try:
            parser = _WebsiteHTMLParser()
            parser.feed(content)
            parser.close()
            return parser
        except Exception:
            return None

    @staticmethod
    def _is_identity_link(url: str, label: str) -> bool:
        haystack = f"{urlparse(url).path} {label}".casefold()
        return any(term in haystack for term in IDENTITY_LINK_TERMS)

    @staticmethod
    def _normalized_host(url: str) -> str | None:
        hostname = urlparse(url).hostname
        return hostname.casefold().removeprefix("www.") if hostname else None

    @staticmethod
    def _same_site(expected_host: str, url: str) -> bool:
        observed_host = WebsiteMetadataCollector._normalized_host(url)
        return observed_host == expected_host

    @staticmethod
    def _json_ld_identity_text(blocks: list[str]) -> str | None:
        values = []
        for block in blocks:
            try:
                payload = json.loads(block)
            except json.JSONDecodeError:
                continue
            WebsiteMetadataCollector._collect_json_ld_values(payload, values)
        return WebsiteMetadataCollector._clean_text(" ".join(values))

    @staticmethod
    def _collect_json_ld_values(value: object, values: list[str]) -> None:
        if isinstance(value, list):
            for item in value:
                WebsiteMetadataCollector._collect_json_ld_values(item, values)
            return
        if not isinstance(value, dict):
            return
        for key, item in value.items():
            normalized_key = key.casefold()
            if normalized_key in JSON_LD_IDENTITY_FIELDS:
                if isinstance(item, str):
                    values.append(item)
                else:
                    WebsiteMetadataCollector._collect_json_ld_values(item, values)
            elif normalized_key == "@graph":
                WebsiteMetadataCollector._collect_json_ld_values(item, values)

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
        self.links: list[tuple[str, str]] = []
        self.json_ld_blocks: list[str] = []
        self._ignored_depth = 0
        self._inside_title = False
        self._inside_body = False
        self._inside_json_ld = False
        self._anchor_href: str | None = None
        self._anchor_text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
        attributes = {key.casefold(): value for key, value in attrs}
        if tag == "script" and attributes.get("type", "").casefold() == "application/ld+json":
            self._inside_json_ld = True
            return
        if tag in IGNORED_TAGS:
            self._ignored_depth += 1
            return

        if tag == "title":
            self._inside_title = True
        elif tag == "body":
            self._inside_body = True
        elif tag == "meta" and self.description is None:
            if attributes.get("name", "").casefold() == "description":
                self.description = attributes.get("content")
        elif tag == "a" and self._anchor_href is None:
            self._anchor_href = attributes.get("href")
            self._anchor_text_parts = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag == "script" and self._inside_json_ld:
            self._inside_json_ld = False
            return
        if tag in IGNORED_TAGS and self._ignored_depth > 0:
            self._ignored_depth -= 1
        elif tag == "title":
            self._inside_title = False
        elif tag == "body":
            self._inside_body = False
        elif tag == "a" and self._anchor_href is not None:
            self.links.append((self._anchor_href, " ".join(self._anchor_text_parts)))
            self._anchor_href = None
            self._anchor_text_parts = []

    def handle_data(self, data: str) -> None:
        if self._inside_json_ld:
            self.json_ld_blocks.append(data)
            return
        if self._ignored_depth > 0:
            return
        if self._anchor_href is not None:
            self._anchor_text_parts.append(data)
        if self._inside_title:
            self.title_parts.append(data)
        elif self._inside_body:
            self.visible_text_parts.append(data)
