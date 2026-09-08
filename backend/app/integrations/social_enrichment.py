from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse, urlunparse

from app.schemas.social_enrichment import SocialPlatform, SocialProfileObservation


SOCIAL_DOMAINS: dict[SocialPlatform, set[str]] = {
    SocialPlatform.INSTAGRAM: {"instagram.com"},
    SocialPlatform.FACEBOOK: {"facebook.com", "web.facebook.com", "m.facebook.com"},
    SocialPlatform.TIKTOK: {"tiktok.com"},
}


@dataclass(frozen=True)
class SocialProfileTarget:
    profile_url: str
    platform: SocialPlatform
    handle: str


class SocialEnrichmentProvider(Protocol):
    def enrich(self, targets: list[SocialProfileTarget]) -> list[SocialProfileObservation]: ...


def social_profile_target(url: str) -> SocialProfileTarget | None:
    parsed = urlparse(url)
    domain = parsed.hostname.casefold().removeprefix("www.") if parsed.hostname else ""
    platform = next(
        (
            candidate_platform
            for candidate_platform, domains in SOCIAL_DOMAINS.items()
            if domain in domains
        ),
        None,
    )
    if platform is None:
        return None
    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) != 1:
        return None
    handle = segments[0]
    if platform is SocialPlatform.INSTAGRAM and handle.casefold() in {
        "accounts", "direct", "explore", "p", "reel", "reels", "stories",
    }:
        return None
    if platform is SocialPlatform.FACEBOOK and handle.casefold() in {
        "events", "groups", "marketplace", "photo", "share", "watch",
    }:
        return None
    if platform is SocialPlatform.TIKTOK and not handle.startswith("@"):
        return None
    return SocialProfileTarget(
        profile_url=urlunparse((parsed.scheme, parsed.netloc, f"/{handle}", "", "", "")),
        platform=platform,
        handle=handle,
    )


def social_profile_key(url: str) -> str | None:
    target = social_profile_target(url)
    if target is None:
        return None
    return f"{target.platform.value}:{target.handle.casefold()}"
