import httpx

from app.integrations.website_metadata import WebsiteMetadataCollector


class FakeResponse:
    def __init__(self, url: str, content: str, content_type: str = "text/html"):
        self.url = httpx.URL(url)
        self.text = content
        self.headers = {"content-type": content_type}

    def raise_for_status(self) -> None:
        return None


class FakeClient:
    responses: dict[str, FakeResponse] = {}
    requested_urls: list[str] = []

    def __init__(self, **_kwargs):
        return None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def get(self, url: str) -> FakeResponse:
        self.requested_urls.append(url)
        response = self.responses[url]
        if isinstance(response, Exception):
            raise response
        return response


def test_collects_bounded_same_site_identity_pages(monkeypatch):
    FakeClient.requested_urls = []
    FakeClient.responses = {
        "https://glowsalon.com": FakeResponse(
            "https://glowsalon.com/",
            """
            <html><head><title>Glow Salon</title></head><body>
            <a href="/contact">Contact us</a>
            <a href="/about">About</a>
            <a href="/locations">Locations</a>
            <a href="https://outside.example/contact">Contact partner</a>
            </body></html>
            """,
        ),
        "https://glowsalon.com/contact": FakeResponse(
            "https://glowsalon.com/contact",
            """
            <html><body>
            <script type="application/ld+json">
            {"@type":"LocalBusiness","name":"Glow Salon","telephone":"03001234567","address":{"addressLocality":"Lahore"}}
            </script>
            </body></html>
            """,
        ),
        "https://glowsalon.com/about": FakeResponse(
            "https://glowsalon.com/about",
            "<html><body>About Glow Salon</body></html>",
        ),
    }
    monkeypatch.setattr("app.integrations.website_metadata.httpx.Client", FakeClient)

    pages = WebsiteMetadataCollector().collect_identity_pages("https://glowsalon.com")

    assert [page.url for page in pages] == [
        "https://glowsalon.com/",
        "https://glowsalon.com/contact",
        "https://glowsalon.com/about",
    ]
    assert "03001234567" in pages[1].identity_text
    assert "Lahore" in pages[1].identity_text
    assert "https://outside.example/contact" not in FakeClient.requested_urls


def test_rejects_a_homepage_that_redirects_to_another_site(monkeypatch):
    FakeClient.requested_urls = []
    FakeClient.responses = {
        "https://glowsalon.com": FakeResponse(
            "https://outside.example/",
            "<html><body>Glow Salon Lahore</body></html>",
        )
    }
    monkeypatch.setattr("app.integrations.website_metadata.httpx.Client", FakeClient)

    pages = WebsiteMetadataCollector().collect_identity_pages("https://glowsalon.com")

    assert pages == ()


def test_keeps_homepage_evidence_when_a_linked_page_fails(monkeypatch):
    FakeClient.requested_urls = []
    FakeClient.responses = {
        "https://glowsalon.com": FakeResponse(
            "https://glowsalon.com/",
            "<html><body>Glow Salon Lahore <a href='/contact'>Contact</a></body></html>",
        ),
        "https://glowsalon.com/contact": httpx.TimeoutException("timed out"),
    }
    monkeypatch.setattr("app.integrations.website_metadata.httpx.Client", FakeClient)

    pages = WebsiteMetadataCollector().collect_identity_pages("https://glowsalon.com")

    assert [page.url for page in pages] == ["https://glowsalon.com/"]
