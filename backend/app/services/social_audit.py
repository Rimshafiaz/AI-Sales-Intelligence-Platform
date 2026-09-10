from datetime import UTC, datetime
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations.apify_social import (
    ApifySocialEnrichmentProvider,
    ApifySocialProviderError,
    create_apify_social_enrichment_provider,
)
from app.models.campaign_candidate_selection import CampaignCandidateSelection
from app.models.company import Company
from app.models.research_request import ResearchRequest, ResearchStatus
from app.repositories.research_evidence import upsert_research_evidence
from app.repositories.research_requests import save_social_audit_result
from app.repositories.research_social_observations import upsert_social_observation
from app.schemas.evidence_gate import EvidenceGateState
from app.schemas.opportunity_models import EvidenceSignalType, EvidenceType
from app.schemas.social_audit import SocialAuditResult, SocialAuditState
from app.schemas.social_enrichment import (
    SocialEnrichmentRequest,
    SocialEnrichmentState,
    SocialProfileObservation,
)
from app.services.evidence_gate import EvidenceGateTarget, target_from_research_request
from app.services.identity_resolution import domain_stem
from app.services.social_enrichment import SocialEnrichmentError, enrich_social_profiles


class SocialAuditError(ValueError):
    pass


AUTO_DISCOVERY_QUERIES = (
    "{name} {location} Instagram",
    "{name} {location} Facebook",
)


def _discover_social_profiles(
    research_request: ResearchRequest,
    company: Company,
    selection: CampaignCandidateSelection | None,
) -> list[str]:
    """Find the prospect's public social profiles with deterministic web
    searches and the platform URL classifier. The user never has to supply
    links; a manual URL stays available as an override."""
    from app.integrations.search_provider import create_tavily_search_provider
    from app.integrations.social_enrichment import social_profile_target

    target = target_from_research_request(research_request, company, selection)
    location = target.location or ""
    query = " ".join(part for part in (target.company_name, location) if part)
    if not query.strip():
        return []

    try:
        search_provider = create_tavily_search_provider(settings.tavily_api_key)
        discovered: dict[str, str] = {}
        for platform_hint in ("Instagram", "Facebook", "TikTok"):
            try:
                results = search_provider.search(
                    f"{query} {platform_hint}",
                    max_results=6,
                )
            except Exception:
                continue
            for result in results:
                candidate = social_profile_target(result.url)
                if candidate is None:
                    continue
                # A profile only counts when its handle carries the business
                # identity, not just any profile in the results.
                if not _handle_matches_business(
                    candidate.handle, target.company_name
                ):
                    continue
                discovered.setdefault(candidate.profile_url, candidate.handle)
        return list(discovered.keys())[:3]
    except Exception:
        return []


def _handle_matches_business(handle: str, company_name: str) -> bool:
    compact = "".join(
        character for character in handle.casefold() if character.isalnum()
    )
    normalized = re.sub(r"[^a-z0-9]+", " ", company_name.casefold()).strip()
    if not compact or not normalized:
        return False
    tokens = [token for token in normalized.split() if len(token) >= 3]
    if not tokens:
        return compact in normalized or normalized in compact
    matched = sum(1 for token in tokens if token in compact)
    return matched >= 2 or compact in normalized


def audit_research_social_profiles(
    db: Session,
    research_request: ResearchRequest,
    company: Company,
    selection: CampaignCandidateSelection | None,
    profile_urls: list[str],
    provider: ApifySocialEnrichmentProvider | None = None,
) -> ResearchRequest:
    if research_request.status is not ResearchStatus.COMPLETED:
        raise SocialAuditError("Finish the evidence review before auditing social profiles.")
    if research_request.evidence_gate_state is not EvidenceGateState.READY_FOR_DEEPER_RESEARCH:
        raise SocialAuditError("Accepted evidence is required before a social audit.")

    urls = _profile_urls(selection, profile_urls)
    if not urls:
        urls = _discover_social_profiles(
            research_request=research_request,
            company=company,
            selection=selection,
        )
    if not urls:
        return _save_unavailable(
            db,
            research_request.id,
            "No public Instagram, Facebook, or TikTok profile URL is available to audit.",
        )
    try:
        enrichment_request = SocialEnrichmentRequest(profile_urls=urls)
        audit_provider = provider or create_apify_social_enrichment_provider(
            settings.apify_token,
            settings.apify_instagram_actor_id,
            settings.apify_facebook_actor_id,
            settings.apify_tiktok_actor_id,
        )
        observations = enrich_social_profiles(enrichment_request, audit_provider).observations
    except (ApifySocialProviderError, SocialEnrichmentError, ValueError) as error:
        return _save_unavailable(db, research_request.id, str(error))

    target = target_from_research_request(research_request, company, selection)
    observed_count = 0
    confirmed_count = 0
    for observation in observations:
        upsert_social_observation(db, research_request.id, observation)
        if observation.state is not SocialEnrichmentState.OBSERVED:
            continue
        observed_count += 1
        if _official_profile_reason(target, observation) is None:
            continue
        confirmed_count += 1
        _save_social_evidence(db, research_request.id, observation, target)

    audited_at = datetime.now(UTC)
    if observed_count == 0:
        return _save_unavailable(
            db,
            research_request.id,
            "No public profile data was available to verify.",
            audited_at,
        )
    reason = (
        f"Observed {observed_count} public profile(s); {confirmed_count} matched the verified business identity."
    )
    return _save_result(
        db,
        research_request.id,
        SocialAuditState.COMPLETED,
        reason,
        audited_at,
    )


def _profile_urls(
    selection: CampaignCandidateSelection | None,
    supplied_urls: list[str],
) -> list[str]:
    candidate_urls = (
        selection.candidate_snapshot.get("social_profile_urls", []) if selection else []
    )
    values = [*candidate_urls, *supplied_urls]
    urls = [value.strip() for value in values if isinstance(value, str) and value.strip()]
    return list(dict.fromkeys(urls))


def _official_profile_reason(
    target: EvidenceGateTarget,
    observation: SocialProfileObservation,
) -> str | None:
    if target.official_origin and _origin(observation.external_url) == target.official_origin:
        return "The profile links to the verified official website."

    if not _same_business_name(target.company_name, observation.display_name):
        return None
    if target.location and target.location.casefold() in (observation.biography or "").casefold():
        return "The public profile name and biography match the verified business and location."
    if target.official_origin and _public_email_matches_origin(
        observation.public_emails,
        target.official_origin,
    ):
        return "The public profile name and listed email match the verified business website."
    return None


def _save_social_evidence(
    db: Session,
    request_id: UUID,
    observation: SocialProfileObservation,
    target: EvidenceGateTarget,
) -> None:
    observed_at = datetime.now(UTC)
    source_key = _source_identity_key(observation)
    profile_reason = _official_profile_reason(target, observation)
    if profile_reason is None:
        return
    upsert_research_evidence(
        db=db,
        research_request_id=request_id,
        signal_type=EvidenceSignalType.OFFICIAL_SOCIAL_PROFILE_CONFIRMED,
        evidence_type=EvidenceType.OBSERVED,
        supporting_value=profile_reason,
        numeric_value=None,
        source=observation.source,
        source_identity_key=source_key,
        captured_at=observed_at,
    )
    if len(observation.recent_public_post_dates) >= 2:
        upsert_research_evidence(
            db=db,
            research_request_id=request_id,
            signal_type=EvidenceSignalType.SOCIAL_HISTORIC_ACTIVITY_CONFIRMED,
            evidence_type=EvidenceType.OBSERVED,
            supporting_value=(
                f"The verified official profile exposes {len(observation.recent_public_post_dates)} "
                "public post dates."
            ),
            numeric_value=float(len(observation.recent_public_post_dates)),
            source=observation.source,
            source_identity_key=source_key,
            captured_at=observed_at,
        )
    if observation.latest_public_post_at is not None:
        dormant_days = max(
            0,
            (observed_at.date() - observation.latest_public_post_at.date()).days,
        )
        upsert_research_evidence(
            db=db,
            research_request_id=request_id,
            signal_type=EvidenceSignalType.SOCIAL_DORMANCY_MEASURED,
            evidence_type=EvidenceType.OBSERVED,
            supporting_value=(
                "The verified official profile's latest observed public post was "
                f"{dormant_days} day(s) before this audit."
            ),
            numeric_value=float(dormant_days),
            source=observation.source,
            source_identity_key=source_key,
            captured_at=observed_at,
        )


def _save_unavailable(
    db: Session,
    request_id: UUID,
    reason: str,
    audited_at: datetime | None = None,
) -> ResearchRequest:
    return _save_result(
        db,
        request_id,
        SocialAuditState.UNAVAILABLE,
        reason,
        audited_at or datetime.now(UTC),
    )


def _save_result(
    db: Session,
    request_id: UUID,
    state: SocialAuditState,
    reason: str,
    audited_at: datetime,
) -> ResearchRequest:
    saved_request = save_social_audit_result(
        db,
        request_id,
        SocialAuditResult(state=state, reason=reason, audited_at=audited_at),
    )
    if saved_request is None:
        raise SocialAuditError("Research request was not found while saving the social audit.")
    return saved_request


def _source_identity_key(observation: SocialProfileObservation) -> str:
    return observation.source.provider_record_id or str(observation.profile_url).rstrip("/")


def _same_business_name(expected: str, observed: str | None) -> bool:
    if observed is None:
        return False
    return _name_key(expected) == _name_key(observed)


def _name_key(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _origin(value: object) -> str | None:
    if value is None:
        return None
    parsed = urlsplit(str(value))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return f"{parsed.scheme.casefold()}://{parsed.netloc.casefold()}"


def _public_email_matches_origin(emails: list[str], official_origin: str) -> bool:
    hostname = urlsplit(official_origin).hostname
    if hostname is None:
        return False
    domain = hostname.casefold().removeprefix("www.")
    return any(email.rsplit("@", 1)[-1].casefold() == domain for email in emails if "@" in email)
