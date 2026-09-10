from app.integrations.website_metadata import WebsiteIdentityPage, WebsiteMetadataCollector


def test_collects_public_contacts_from_verified_website_pages(monkeypatch):
    pages = (
        WebsiteIdentityPage(
            url="https://glowsalon.example/",
            title="Glow Salon",
            description=None,
            identity_text="Email hello@glowsalon.example",
            identity_links=("https://glowsalon.example/contact",),
            contact_links=(
                "mailto:bookings@glowsalon.example",
                "tel:+923001234567",
                "https://wa.me/923001234567",
            ),
        ),
        WebsiteIdentityPage(
            url="https://glowsalon.example/contact",
            title="Contact Glow Salon",
            description=None,
            identity_text="Contact Glow Salon",
            identity_links=(),
            has_form=True,
        ),
    )
    collector = WebsiteMetadataCollector()
    monkeypatch.setattr(collector, "collect_identity_pages", lambda _website: pages)

    contacts = collector.collect_contact_paths("https://glowsalon.example")

    assert {(item.contact_type, item.value) for item in contacts} == {
        ("email", "hello@glowsalon.example"),
        ("email", "bookings@glowsalon.example"),
        ("phone", "+923001234567"),
        ("whatsapp", "https://wa.me/923001234567"),
        ("contact_form", "https://glowsalon.example/contact"),
    }


def test_does_not_treat_a_homepage_form_as_a_contact_form(monkeypatch):
    pages = (
        WebsiteIdentityPage(
            url="https://shop.example/",
            title="Shop",
            description=None,
            identity_text="Join our newsletter",
            identity_links=(),
            has_form=True,
        ),
    )
    collector = WebsiteMetadataCollector()
    monkeypatch.setattr(collector, "collect_identity_pages", lambda _website: pages)

    assert collector.collect_contact_paths("https://shop.example") == ()
