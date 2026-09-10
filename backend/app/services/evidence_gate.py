from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit

from app.integrations.search_provider import CollectedSource
from app.models.campaign_candidate_selection import CampaignCandidateSelection
from app.models.company import Company
from app.models.research_request import ResearchRequest
from app.schemas.evidence_gate import EvidenceGateResponse, EvidenceGateState, SourceAdmissionState
from app.services.identity_resolution import (
    IdentityResolution,
    IdentityStatus,
    REASONABLE_NAME_SCORE,
    domain_stem,
    resolve_source_identity,
)


@dataclass(frozen=True)
class EvidenceGateTarget:
    company_name: str
    location: str | None
    official_origin: str | None
    official_website: str | None
    identity_verified: bool
    trusted_source_urls: frozenset[str]
    no_listed_official_website: bool = False
    phone_number: str | None = None


@dataclass(frozen=True)
class SourceAdmission:
    source: CollectedSource
    state: SourceAdmissionState
    reason: str


def target_from_research_request(
    research_request: ResearchRequest,
    company: Company,
    selection: CampaignCandidateSelection | None = None,
) -> EvidenceGateTarget:
    objective = research_request.objective if isinstance(research_request.objective, dict) else {}
    resolved_target = objective.get("resolved_target")
    if isinstance(resolved_target, dict):
        source = resolved_target.get("source")
        source_url = source.get("source_url") if isinstance(source, dict) else None
        official_website = resolved_target.get("website")
        return EvidenceGateTarget(
            company_name=_text(resolved_target.get("business_name")) or company.name,
            location=_text(objective.get("location")),
            official_origin=_origin(official_website),
            official_website=_normalized_url(official_website),
            identity_verified=resolved_target.get("identity_state") == "verified",
            trusted_source_urls=frozenset(
                value for value in (_normalized_url(source_url),) if value is not None
            ),
        )

    if selection is not None:
        candidate = selection.candidate_snapshot
        trusted_urls = _selection_source_urls(selection)
        return EvidenceGateTarget(
            company_name=_text(candidate.get("company_name")) or company.name,
            location=_text(objective.get("location")) or _text(candidate.get("formatted_address")),
            official_origin=None,
            official_website=None,
            identity_verified=_selection_confirms_identity(selection),
            trusted_source_urls=frozenset(trusted_urls),
            no_listed_official_website=_selection_has_no_listed_website(selection),
            phone_number=_text(candidate.get("phone_number")),
        )

    return EvidenceGateTarget(
        company_name=company.name,
        location=_text(objective.get("location")) or _text(objective.get("region")),
        official_origin=None,
        official_website=None,
        identity_verified=False,
        trusted_source_urls=frozenset(),
    )


def review_sources(
    target: EvidenceGateTarget,
    sources: list[CollectedSource],
) -> tuple[list[SourceAdmission], EvidenceGateResponse]:
    reviewed = [_review_source(target, source) for source in sources]
    admissions = [admission for admission, _resolution in reviewed]
    resolutions = [resolution for _admission, resolution in reviewed]

    _apply_corroboration(admissions, reviewed, target)

    has_accepted_source = any(
        item.state is SourceAdmissionState.ACCEPTED for item in admissions
    )

    if not target.identity_verified:
        state = EvidenceGateState.NEEDS_REVIEW
        reason = "The business identity is not verified by traceable target evidence."
    elif not has_accepted_source and target.no_listed_official_website:
        state = EvidenceGateState.READY_FOR_DEEPER_RESEARCH
        reason = (
            "The provider record verified this business identity and lists no "
            "official website, so web evidence is unavailable by design. "
            "Proceed to social and contact verification."
        )
    elif not has_accepted_source:
        state = EvidenceGateState.NEEDS_REVIEW
        reason = "No collected source was accepted as evidence for the resolved target."
    else:
        state = EvidenceGateState.READY_FOR_DEEPER_RESEARCH
        reason = "Accepted sources are traceably linked to the resolved target."

    return admissions, EvidenceGateResponse(
        state=state,
        reason=reason,
        evaluated_at=datetime.now(UTC),
    )


def _apply_corroboration(
    admissions: list[SourceAdmission],
    reviewed: list[tuple[SourceAdmission, IdentityResolution]],
    target: EvidenceGateTarget,
) -> None:
    """Policy C: multiple independent corroborating sources upgrade
    name-matched, location-supported candidates from NEEDS_REVIEW to ACCEPTED."""
    corroborating = {
        index
        for index, (_admission, resolution) in enumerate(reviewed)
        if (
            admissions[index].state is SourceAdmissionState.NEEDS_REVIEW
            and resolution.name_score >= REASONABLE_NAME_SCORE
            and resolution.location_match
        )
    }
    if len(corroborating) < 2:
        return
    domains = {
        domain_stem(admissions[index].source.url) for index in corroborating
    }
    if len(domains) < 2:
        return
    for index in corroborating:
        admissions[index] = SourceAdmission(
            source=admissions[index].source,
            state=SourceAdmissionState.ACCEPTED,
            reason=(
                "Multiple independent sources name the resolved business at "
                "its resolved location."
            ),
        )


def requires_deep_qualification(research_request: ResearchRequest) -> bool:
    objective = research_request.objective
    return (
        research_request.campaign_candidate_selection_id is not None
        or isinstance(objective, dict) and objective.get("mode") == "known_prospect"
    )


def _review_source(target: EvidenceGateTarget, source: CollectedSource) -> tuple[
    SourceAdmission,
    IdentityResolution,
]:
    normalized_url = _normalized_url(source.url)
    if normalized_url is not None and normalized_url in target.trusted_source_urls:
        return SourceAdmission(
            source=source,
            state=SourceAdmissionState.ACCEPTED,
            reason="The source matches evidence captured during target resolution or selection.",
        ), _trusted_resolution(target)

    if target.official_origin and _origin(source.url) == target.official_origin:
        return SourceAdmission(
            source=source,
            state=SourceAdmissionState.ACCEPTED,
            reason="The source is hosted on the verified official website.",
        ), _trusted_resolution(target)

    resolution = resolve_source_identity(
        candidate_name=target.company_name,
        candidate_location=target.location,
        candidate_phone=target.phone_number,
        source_url=source.url,
        source_name=source.title or "",
        source_text=source.excerpt or "",
        identity_verified=target.identity_verified,
    )

    if resolution.status is IdentityStatus.CONFIRMED:
        state = SourceAdmissionState.ACCEPTED
    elif resolution.status is IdentityStatus.REJECTED:
        state = SourceAdmissionState.EXCLUDED
    else:
        state = SourceAdmissionState.NEEDS_REVIEW

    return SourceAdmission(
        source=source,
        state=state,
        reason=" ".join(resolution.reasons) or resolution.status.value,
    ), resolution


def _trusted_resolution(target: EvidenceGateTarget) -> IdentityResolution:
    return IdentityResolution(
        status=IdentityStatus.CONFIRMED,
        name_score=100,
        domain_match=True,
        location_match=None,
        contact_match=None,
        reasons=["Traceable identity evidence captured during resolution."],
    )


def _selection_confirms_identity(selection: CampaignCandidateSelection) -> bool:
    return any(
        isinstance(signal, dict)
        and signal.get("signal_type") == "business_identity_confirmed"
        and isinstance(signal.get("source"), dict)
        and (
            _normalized_url(signal["source"].get("source_url")) is not None
            or _text(signal["source"].get("provider_record_id")) is not None
        )
        for signal in selection.evidence_snapshot
    )


def _selection_has_no_listed_website(selection: CampaignCandidateSelection) -> bool:
    candidate = selection.candidate_snapshot
    return (
        candidate.get("website") is None
        and "local_places" in candidate.get("discovery_source_types", [])
    )


def _selection_source_urls(selection: CampaignCandidateSelection) -> set[str]:
    candidate_urls = selection.candidate_snapshot.get("supporting_source_urls", [])
    evidence_urls = [
        signal.get("source", {}).get("source_url")
        for signal in selection.evidence_snapshot
        if isinstance(signal, dict) and isinstance(signal.get("source"), dict)
    ]
    return {
        normalized_url
        for value in [*candidate_urls, *evidence_urls]
        if (normalized_url := _normalized_url(value)) is not None
    }


def _origin(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return f"{parsed.scheme.casefold()}://{parsed.netloc.casefold()}"


def _normalized_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return urlunsplit(
        (
            parsed.scheme.casefold(),
            parsed.netloc.casefold(),
            parsed.path.rstrip("/") or "/",
            parsed.query,
            "",
        )
    )


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    return value.strip() or None
