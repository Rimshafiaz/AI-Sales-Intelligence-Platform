from datetime import UTC, datetime
import re
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations.apify_social import (
    ApifySocialEnrichmentProvider,
    ApifySocialProviderError,
    create_apify_social_enrichment_provider,
)
from app.integrations.social_enrichment import social_profile_key, social_profile_target
from app.models.campaign_candidate_selection import CampaignCandidateSelection
from app.models.company import Company
from app.models.research_request import ResearchRequest, ResearchStatus
from app.repositories.research_evidence import (
    list_research_evidence_for_user,
    upsert_research_evidence,
)
from app.repositories.research_requests import save_social_audit_result
from app.repositories.research_social_observations import (
    list_social_observations_for_user,
    upsert_social_observation,
)
from app.schemas.evidence_gate import EvidenceGateState
from app.schemas.opportunity_models import (
    EvidenceSignalType,
    EvidenceType,
    OpportunityModelSelection,
    ServiceFamily,
)
from app.schemas.social_audit import (
    SocialAuditResult,
    SocialAuditState,
    SocialCandidateDiscoveryResult,
    SocialCandidateDiscoveryState,
    SocialCandidateEnrichmentResult,
    SocialEnrichmentResultState,
    SocialProfileCandidate,
    SocialVerificationResult,
    SocialVerificationState,
)
from app.schemas.social_enrichment import (
    SocialEnrichmentRequest,
    SocialEnrichmentState,
    SocialProfileObservation,
)
from app.services.evidence_gate import EvidenceGateTarget, target_from_research_request
from app.services.identity_resolution import domain_stem
from app.services.social_enrichment import SocialEnrichmentError, enrich_social_profiles
from app.services.opportunity_model_catalog import get_opportunity_model


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
    _, permitted = _guard_social_capability(
        research_request, company, selection, research_request.user_id
    )
    if not permitted:
        return _save_unavailable(
            db, research_request.id, "No selected social opportunity model permits this audit."
        )
    candidates = (
        _candidate_result(_profile_urls(selection, profile_urls), "manual_compatibility")
        if profile_urls
        else discover_social_profile_candidates(
            db, research_request, company, selection, research_request.user_id
        )
    )
    if not candidates.candidates:
        return _save_unavailable(
            db,
            research_request.id,
            "No public Instagram, Facebook, or TikTok profile URL is available to audit.",
        )
    enrichment = enrich_social_profile_candidates(
        db,
        research_request,
        company,
        selection,
        research_request.user_id,
        candidates,
        provider,
    )
    if enrichment.state in {
        SocialEnrichmentResultState.UNAVAILABLE,
        SocialEnrichmentResultState.NO_CANDIDATES,
    }:
        return _save_unavailable(db, research_request.id, enrichment.reason)
    verification = verify_social_profiles_and_measure_activity(
        db,
        research_request,
        company,
        selection,
        research_request.user_id,
        enrichment,
    )
    audited_at = datetime.now(UTC)
    if verification.state is SocialVerificationState.UNAVAILABLE:
        return _save_unavailable(
            db,
            research_request.id,
            "No public profile data was available to verify.",
            audited_at,
        )
    return _save_result(
        db,
        research_request.id,
        SocialAuditState.COMPLETED,
        verification.reason,
        audited_at,
    )


def discover_social_profile_candidates(
    db: Session,
    research_request: ResearchRequest,
    company: Company,
    selection: CampaignCandidateSelection | None,
    expected_user_id: UUID,
) -> SocialCandidateDiscoveryResult:
    _, permitted = _guard_social_capability(
        research_request, company, selection, expected_user_id
    )
    if not permitted:
        return SocialCandidateDiscoveryResult(
            state=SocialCandidateDiscoveryState.NOT_PERMITTED,
            reason="No selected social opportunity model permits candidate discovery.",
        )
    campaign_urls = _profile_urls(selection, [])
    if campaign_urls:
        return _candidate_result(campaign_urls, "campaign")
    return _candidate_result(
        _discover_social_profiles(research_request, company, selection),
        "bounded_search",
    )


def enrich_social_profile_candidates(
    db: Session,
    research_request: ResearchRequest,
    company: Company,
    selection: CampaignCandidateSelection | None,
    expected_user_id: UUID,
    candidates: SocialCandidateDiscoveryResult,
    provider: ApifySocialEnrichmentProvider | None = None,
) -> SocialCandidateEnrichmentResult:
    _, permitted = _guard_social_capability(
        research_request, company, selection, expected_user_id
    )
    if not permitted:
        return SocialCandidateEnrichmentResult(
            state=SocialEnrichmentResultState.NOT_PERMITTED,
            reason="No selected social opportunity model permits candidate enrichment.",
        )
    canonical = [
        candidate
        for candidate in candidates.candidates
        if social_profile_target(str(candidate.profile_url)) is not None
    ]
    if not canonical:
        return SocialCandidateEnrichmentResult(
            state=SocialEnrichmentResultState.NO_CANDIDATES,
            reason="No server-controlled social profile candidates are available.",
        )
    existing = list_social_observations_for_user(db, research_request.id, expected_user_id)
    existing_by_key = {item.profile_identity_key: item for item in existing}
    candidate_keys = [social_profile_key(str(item.profile_url)) for item in canonical]
    if all(key in existing_by_key for key in candidate_keys):
        return SocialCandidateEnrichmentResult(
            state=SocialEnrichmentResultState.ALREADY_AVAILABLE,
            observations=[_observation_from_record(existing_by_key[key]) for key in candidate_keys],
            reason="Owned social observations are already available for all candidates.",
        )
    try:
        enrichment_request = SocialEnrichmentRequest(
            profile_urls=[item.profile_url for item in canonical]
        )
        audit_provider = provider or create_apify_social_enrichment_provider(
            settings.apify_token,
            settings.apify_instagram_actor_id,
            settings.apify_facebook_actor_id,
            settings.apify_tiktok_actor_id,
        )
        observations = enrich_social_profiles(enrichment_request, audit_provider).observations
    except (ApifySocialProviderError, SocialEnrichmentError, ValueError) as error:
        return SocialCandidateEnrichmentResult(
            state=SocialEnrichmentResultState.UNAVAILABLE,
            reason=str(error),
        )
    for observation in observations:
        upsert_social_observation(db, research_request.id, observation)
    db.commit()
    return SocialCandidateEnrichmentResult(
        state=SocialEnrichmentResultState.OBSERVATIONS_AVAILABLE,
        observations=observations,
        reason=f"Persisted {len(observations)} normalized social observation(s).",
    )


def verify_social_profiles_and_measure_activity(
    db: Session,
    research_request: ResearchRequest,
    company: Company,
    selection: CampaignCandidateSelection | None,
    expected_user_id: UUID,
    enrichment: SocialCandidateEnrichmentResult | None = None,
) -> SocialVerificationResult:
    target, permitted = _guard_social_capability(
        research_request, company, selection, expected_user_id
    )
    if not permitted:
        return SocialVerificationResult(
            state=SocialVerificationState.NOT_PERMITTED,
            reason="No selected social opportunity model permits profile verification.",
        )
    observed = (
        [
            item
            for item in enrichment.observations
            if item.state is SocialEnrichmentState.OBSERVED
        ]
        if enrichment is not None
        else [
            _observation_from_record(item)
            for item in list_social_observations_for_user(
                db, research_request.id, expected_user_id
            )
            if item.state == SocialEnrichmentState.OBSERVED.value
        ]
    )
    if not observed:
        return SocialVerificationResult(
            state=SocialVerificationState.UNAVAILABLE,
            reason="No owned public social observations are available to verify.",
        )
    existing_signals = {
        EvidenceSignalType(item.signal_type)
        for item in list_research_evidence_for_user(db, research_request.id, expected_user_id)
    }
    matched = 0
    for observation in observed:
        if _official_profile_reason(target, observation) is None:
            continue
        matched += 1
        _save_social_evidence(db, research_request.id, observation, target)
    if matched == 0:
        return SocialVerificationResult(
            state=SocialVerificationState.NO_OFFICIAL_PROFILE_VERIFIED,
            reason=f"Observed {len(observed)} public profile(s); 0 matched the verified business identity.",
        )
    db.commit()
    signals = {
        EvidenceSignalType(item.signal_type)
        for item in list_research_evidence_for_user(db, research_request.id, expected_user_id)
    }
    created = signals - existing_signals
    if EvidenceSignalType.SOCIAL_HISTORIC_ACTIVITY_CONFIRMED not in signals:
        state = SocialVerificationState.INSUFFICIENT_ACTIVITY_HISTORY
    elif EvidenceSignalType.SOCIAL_DORMANCY_MEASURED not in signals:
        state = SocialVerificationState.DORMANCY_UNMEASURABLE
    else:
        state = (
            SocialVerificationState.EVIDENCE_FOUND
            if created
            else SocialVerificationState.ALREADY_AVAILABLE
        )
    return SocialVerificationResult(
        state=state,
        reason=f"Observed {len(observed)} public profile(s); {matched} matched the verified business identity.",
        verified_profile_count=matched,
        evidence_signals=sorted(signals, key=lambda item: item.value),
    )


def _guard_social_capability(
    research_request: ResearchRequest,
    company: Company,
    selection: CampaignCandidateSelection | None,
    expected_user_id: UUID,
) -> tuple[EvidenceGateTarget, bool]:
    if research_request.user_id != expected_user_id or company.user_id != expected_user_id:
        raise SocialAuditError("Research request is not available to this user.")
    if research_request.company_id != company.id:
        raise SocialAuditError("Research request does not belong to the supplied company.")
    if selection is not None and (
        research_request.campaign_candidate_selection_id != selection.id
        or selection.company_id != company.id
    ):
        raise SocialAuditError("Campaign selection does not belong to this research request.")
    if research_request.status is not ResearchStatus.COMPLETED:
        raise SocialAuditError("Finish the evidence review before auditing social profiles.")
    if research_request.evidence_gate_state is not EvidenceGateState.READY_FOR_DEEPER_RESEARCH:
        raise SocialAuditError("Accepted evidence is required before a social audit.")
    target = target_from_research_request(research_request, company, selection)
    if not target.identity_verified:
        raise SocialAuditError("A verified business identity is required for social research.")
    try:
        selected = OpportunityModelSelection.model_validate(
            research_request.opportunity_model_selection
        )
    except ValueError as error:
        raise SocialAuditError("The selected opportunity-model scope is invalid.") from error
    permitted = any(
        model_id == "social_presence.dormant_official_presence"
        and get_opportunity_model(model_id).service_family
        is ServiceFamily.SOCIAL_PRESENCE_CONTENT
        for model_id in selected.model_ids
    )
    return target, permitted


def _candidate_result(
    urls: list[str],
    source: str,
) -> SocialCandidateDiscoveryResult:
    candidates = []
    for url in urls:
        target = social_profile_target(url)
        if target is None:
            continue
        candidates.append(
            SocialProfileCandidate(
                profile_url=target.profile_url,
                platform=target.platform,
                handle=target.handle,
                source=source,
            )
        )
    candidates = list({str(item.profile_url).rstrip("/").casefold(): item for item in candidates}.values())[:3]
    return SocialCandidateDiscoveryResult(
        state=(
            SocialCandidateDiscoveryState.CANDIDATES_AVAILABLE
            if candidates
            else SocialCandidateDiscoveryState.NO_CANDIDATES
        ),
        candidates=candidates,
        reason=(
            f"Found {len(candidates)} supported social profile candidate(s)."
            if candidates
            else "No supported social profile candidates were found."
        ),
    )


def _observation_from_record(record) -> SocialProfileObservation:
    return SocialProfileObservation(
        profile_url=record.profile_url,
        platform=record.platform,
        state=record.state,
        display_name=record.display_name,
        handle=record.handle,
        external_url=record.external_url,
        provider_profile_id=record.provider_profile_id,
        is_private=record.is_private,
        latest_public_post_at=record.latest_public_post_at,
        recent_public_post_dates=record.recent_public_post_dates,
        public_emails=record.public_emails,
        public_phones=record.public_phones,
        source={
            "provider": record.source_provider,
            "provider_record_id": record.source_record_id,
            "source_url": record.source_url,
            "retrieved_at": record.retrieved_at,
        },
        detail=record.detail,
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
