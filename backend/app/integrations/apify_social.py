from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from time import sleep
from urllib.parse import urlparse

import httpx

from app.integrations.social_enrichment import (
    SocialProfileTarget,
    social_profile_key,
    social_profile_target,
)
from app.schemas.opportunity_models import EvidenceSource
from app.schemas.social_enrichment import (
    SocialEnrichmentState,
    SocialPlatform,
    SocialProfileObservation,
)


APIFY_RUN_SYNC_DATASET_URL = "https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"
DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_RETRY_ATTEMPTS = 2
MAX_PROFILES_PER_REQUEST = 20


class ApifySocialProviderError(Exception):
    pass


@dataclass(frozen=True)
class ApifyActor:
    actor_id: str
    platform: SocialPlatform


class ApifySocialEnrichmentProvider:
    def __init__(
        self,
        api_token: str,
        instagram_actor_id: str,
        facebook_actor_id: str,
        tiktok_actor_id: str,
        client: object | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
    ) -> None:
        if not api_token.strip():
            raise ValueError("Apify API token cannot be blank.")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive.")
        if retry_attempts < 1:
            raise ValueError("retry_attempts must be at least 1.")
        self.api_token = api_token
        self.actors = {
            SocialPlatform.INSTAGRAM: ApifyActor(instagram_actor_id, SocialPlatform.INSTAGRAM),
            SocialPlatform.FACEBOOK: ApifyActor(facebook_actor_id, SocialPlatform.FACEBOOK),
            SocialPlatform.TIKTOK: ApifyActor(tiktok_actor_id, SocialPlatform.TIKTOK),
        }
        self.client = client
        self.timeout_seconds = timeout_seconds
        self.retry_attempts = retry_attempts

    def enrich(self, targets: list[SocialProfileTarget]) -> list[SocialProfileObservation]:
        if len(targets) > MAX_PROFILES_PER_REQUEST:
            raise ValueError(
                f"At most {MAX_PROFILES_PER_REQUEST} social profiles may be enriched at once."
            )
        targets_by_platform: dict[SocialPlatform, list[SocialProfileTarget]] = defaultdict(list)
        for target in targets:
            targets_by_platform[target.platform].append(target)

        observations: list[SocialProfileObservation] = []
        for platform, platform_targets in targets_by_platform.items():
            actor = self.actors[platform]
            records = self._run_actor(actor, platform_targets)
            observations.extend(
                self._observations_for_platform(actor, platform_targets, records)
            )
        return observations

    def _run_actor(
        self,
        actor: ApifyActor,
        targets: list[SocialProfileTarget],
    ) -> list[object]:
        actor_id = actor.actor_id.replace("/", "~")
        url = APIFY_RUN_SYNC_DATASET_URL.format(actor_id=actor_id)
        data = self._post(url, self._actor_input(actor.platform, targets))
        return data if isinstance(data, list) else []

    @staticmethod
    def _actor_input(
        platform: SocialPlatform,
        targets: list[SocialProfileTarget],
    ) -> dict[str, object]:
        urls = [target.profile_url for target in targets]
        if platform is SocialPlatform.INSTAGRAM:
            return {"usernames": urls}
        if platform is SocialPlatform.FACEBOOK:
            return {"startUrls": [{"url": url} for url in urls]}
        return {
            "profiles": urls,
            "includeRecentVideos": False,
            "maxTotalProfiles": len(urls),
        }

    def _post(self, url: str, payload: dict[str, object]) -> object:
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }
        params = {"timeout": int(self.timeout_seconds), "maxItems": MAX_PROFILES_PER_REQUEST}
        for attempt in range(self.retry_attempts):
            try:
                if self.client is None:
                    with httpx.Client(timeout=self.timeout_seconds) as client:
                        response = client.post(url, headers=headers, params=params, json=payload)
                else:
                    response = self.client.post(
                        url,
                        headers=headers,
                        params=params,
                        json=payload,
                        timeout=self.timeout_seconds,
                    )
                response.raise_for_status()
                return response.json()
            except (httpx.TimeoutException, httpx.NetworkError) as error:
                if attempt == self.retry_attempts - 1:
                    raise ApifySocialProviderError(
                        "Apify social enrichment timed out. Please try again."
                    ) from error
                sleep(0.25)
            except httpx.HTTPStatusError as error:
                if error.response.status_code in {402, 429}:
                    raise ApifySocialProviderError(
                        "Apify quota or rate limit was reached. Please try again later."
                    ) from error
                raise ApifySocialProviderError(
                    "Apify social enrichment failed. Check provider configuration and try again."
                ) from error
            except (httpx.HTTPError, ValueError, TypeError) as error:
                raise ApifySocialProviderError(
                    "Apify social enrichment failed. Check provider configuration and try again."
                ) from error
        raise ApifySocialProviderError("Apify social enrichment failed. Please try again.")

    def _observations_for_platform(
        self,
        actor: ApifyActor,
        targets: list[SocialProfileTarget],
        records: list[object],
    ) -> list[SocialProfileObservation]:
        records_by_key: dict[str, dict[str, object]] = {}
        for record in records:
            if not isinstance(record, dict):
                continue
            key = self._record_key(record, actor.platform)
            if key and key not in records_by_key:
                records_by_key[key] = record
        retrieved_at = datetime.now(UTC)
        return [
            self._observation_from_record(
                actor,
                target,
                records_by_key.get(f"{target.platform.value}:{target.handle.casefold()}"),
                retrieved_at,
            )
            for target in targets
        ]

    @staticmethod
    def _record_key(record: dict[str, object], platform: SocialPlatform) -> str | None:
        for value in (
            record.get("profileUrl"),
            record.get("profile_url"),
            record.get("url"),
            record.get("pageUrl"),
            record.get("facebookUrl"),
            record.get("instagramUrl"),
            record.get("input"),
        ):
            if isinstance(value, str):
                key = social_profile_key(value)
                if key and key.startswith(f"{platform.value}:"):
                    return key
        handle = ApifySocialEnrichmentProvider._text(
            record.get("username")
            or record.get("pageName")
            or record.get("uniqueId")
            or record.get("unique_id")
        )
        if handle is None:
            return None
        if platform is SocialPlatform.TIKTOK and not handle.startswith("@"):
            handle = f"@{handle}"
        target = social_profile_target(
            ApifySocialEnrichmentProvider._profile_url_for_handle(platform, handle)
        )
        return f"{platform.value}:{target.handle.casefold()}" if target else None

    def _observation_from_record(
        self,
        actor: ApifyActor,
        target: SocialProfileTarget,
        record: dict[str, object] | None,
        retrieved_at: datetime,
    ) -> SocialProfileObservation:
        if record is None:
            return self._unavailable_observation(
                actor,
                target,
                retrieved_at,
                "No matching public profile data was returned.",
            )
        is_private = self._boolean(
            record.get("isPrivate")
            if "isPrivate" in record
            else record.get("private")
            if "private" in record
            else record.get("privateAccount")
        )
        if is_private is True:
            return self._unavailable_observation(
                actor,
                target,
                retrieved_at,
                "The profile is private, so public content is unavailable.",
                is_private=True,
            )
        if self._record_failed(record):
            return self._unavailable_observation(
                actor,
                target,
                retrieved_at,
                "The provider could not retrieve public profile data.",
            )
        profile_id = self._text(
            record.get("id")
            or record.get("profileId")
            or record.get("pageId")
            or record.get("facebookId")
            or record.get("userId")
            or record.get("uid")
        )
        post_dates = self._post_dates(record)
        return SocialProfileObservation(
            profile_url=target.profile_url,
            platform=target.platform,
            state=SocialEnrichmentState.OBSERVED,
            display_name=self._text(
                record.get("fullName")
                or record.get("full_name")
                or record.get("title")
                or record.get("name")
                or record.get("nickname")
            ),
            handle=self._text(
                record.get("username")
                or record.get("pageName")
                or record.get("uniqueId")
                or record.get("unique_id")
                or target.handle
            ),
            provider_profile_id=profile_id,
            biography=self._text(
                record.get("biography")
                or record.get("bio")
                or record.get("description")
                or record.get("intro")
                or record.get("signature")
            ),
            external_url=self._http_url(
                record.get("externalUrl")
                or record.get("external_url")
                or record.get("website")
                or record.get("bioLinkNormalized")
                or record.get("bio_url")
            ),
            public_emails=self._texts(
                record.get("businessEmail"),
                record.get("contactEmail"),
                record.get("email"),
                record.get("bioEmail"),
            ),
            public_phones=self._texts(
                record.get("businessPhoneNumber"),
                record.get("phone"),
                record.get("bioPhone"),
            ),
            follower_count=self._integer(
                record.get("followersCount")
                or record.get("followers")
                or record.get("followerCount")
            ),
            post_count=self._integer(
                record.get("postsCount")
                or record.get("post_count")
                or record.get("videoCount")
                or record.get("aweme_count")
            ),
            is_private=is_private,
            is_verified=self._boolean(
                record.get("verified")
                if "verified" in record
                else record.get("isVerified")
            ),
            public_business_category=self._text(
                record.get("businessCategoryName")
                or record.get("businessCategory")
                or record.get("category")
                or record.get("categoryName")
            ),
            latest_public_post_at=post_dates[0] if post_dates else None,
            recent_public_post_dates=post_dates,
            source=EvidenceSource(
                provider="apify",
                provider_record_id=(f"{actor.actor_id}:{profile_id}" if profile_id else None),
                source_url=target.profile_url,
                retrieved_at=retrieved_at,
            ),
        )

    def _unavailable_observation(
        self,
        actor: ApifyActor,
        target: SocialProfileTarget,
        retrieved_at: datetime,
        detail: str,
        is_private: bool | None = None,
    ) -> SocialProfileObservation:
        return SocialProfileObservation(
            profile_url=target.profile_url,
            platform=target.platform,
            state=SocialEnrichmentState.UNAVAILABLE,
            handle=target.handle,
            is_private=is_private,
            source=EvidenceSource(
                provider="apify",
                source_url=target.profile_url,
                retrieved_at=retrieved_at,
            ),
            detail=detail,
        )

    @staticmethod
    def _record_failed(record: dict[str, object]) -> bool:
        status = ApifySocialEnrichmentProvider._text(record.get("status"))
        if status and status.casefold() in {"error", "failed", "not_found", "not available"}:
            return True
        success = record.get("success")
        return success is False or isinstance(record.get("error"), str)

    @staticmethod
    def _profile_url_for_handle(platform: SocialPlatform, handle: str) -> str:
        if platform is SocialPlatform.INSTAGRAM:
            return f"https://www.instagram.com/{handle}"
        if platform is SocialPlatform.FACEBOOK:
            return f"https://www.facebook.com/{handle}"
        return f"https://www.tiktok.com/{handle}"

    @staticmethod
    def _post_dates(record: dict[str, object]) -> list[datetime]:
        raw_posts = (
            record.get("latestPosts")
            or record.get("latest_posts")
            or record.get("recentPosts")
            or record.get("recentVideos")
        )
        if not isinstance(raw_posts, list):
            return []
        dates: list[datetime] = []
        for post in raw_posts:
            if not isinstance(post, dict):
                continue
            for value in (
                post.get("timestamp"),
                post.get("takenAt"),
                post.get("taken_at_timestamp"),
                post.get("takenAtTimestamp"),
                post.get("createdAt"),
                post.get("createTime"),
                post.get("publishedAt"),
                post.get("postedAt"),
            ):
                parsed = ApifySocialEnrichmentProvider._datetime(value)
                if parsed is not None:
                    dates.append(parsed)
                    break
        return sorted(set(dates), reverse=True)[:12]

    @staticmethod
    def _datetime(value: object) -> datetime | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int | float):
            timestamp = float(value)
            if timestamp > 1_000_000_000_000:
                timestamp /= 1_000
            try:
                return datetime.fromtimestamp(timestamp, tz=UTC)
            except (OverflowError, OSError, ValueError):
                return None
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)

    @staticmethod
    def _text(value: object) -> str | None:
        return value.strip() or None if isinstance(value, str) else None

    @staticmethod
    def _texts(*values: object) -> list[str]:
        return list(
            dict.fromkeys(
                value.strip()
                for value in values
                if isinstance(value, str) and value.strip()
            )
        )[:3]

    @staticmethod
    def _integer(value: object) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value if value >= 0 else None
        if isinstance(value, float) and value.is_integer() and value >= 0:
            return int(value)
        return None

    @staticmethod
    def _boolean(value: object) -> bool | None:
        return value if isinstance(value, bool) else None

    @staticmethod
    def _http_url(value: object) -> str | None:
        clean_value = ApifySocialEnrichmentProvider._text(value)
        if clean_value is None:
            return None
        parsed = urlparse(clean_value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return None
        return clean_value


def create_apify_social_enrichment_provider(
    api_token: str | None,
    instagram_actor_id: str,
    facebook_actor_id: str,
    tiktok_actor_id: str,
) -> ApifySocialEnrichmentProvider:
    if api_token is None or not api_token.strip():
        raise ApifySocialProviderError("Apify is not configured. Set APIFY_TOKEN.")
    return ApifySocialEnrichmentProvider(
        api_token=api_token,
        instagram_actor_id=instagram_actor_id,
        facebook_actor_id=facebook_actor_id,
        tiktok_actor_id=tiktok_actor_id,
    )
