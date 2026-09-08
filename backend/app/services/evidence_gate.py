from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit

from app.integrations.search_provider import CollectedSource
from app.models.campaign_candidate_selection import CampaignCandidateSelection
from app.models.company import Company
from app.models.research_request import ResearchRequest
from app.schemas.evidence_gate import EvidenceGateResponse, EvidenceGateState, SourceAdmissionState


@dataclass(frozen=True)
class EvidenceGateTarget:
    company_name: str
    location: str | None
    official_origin: str | None
    identity_verified: bool
    trusted_source_urls: frozenset[str]


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
            identity_verified=_selection_confirms_identity(selection),
            trusted_source_urls=frozenset(trusted_urls),
        )

    return EvidenceGateTarget(
        company_name=company.name,
        location=_text(objective.get("location")) or _text(objective.get("region")),
        official_origin=None,
        identity_verified=False,
        trusted_source_urls=frozenset(),
    )


def review_sources(
    target: EvidenceGateTarget,
    sources: list[CollectedSource],
) -> tuple[list[SourceAdmission], EvidenceGateResponse]:
    admissions = [_review_source(target, source) for source in sources]
    has_accepted_source = any(
        item.state is SourceAdmissionState.ACCEPTED for item in admissions
    )

    if not target.identity_verified:
        state = EvidenceGateState.NEEDS_REVIEW
        reason = "The business identity is not verified by traceable target evidence."
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


def requires_deep_qualification(research_request: ResearchRequest) -> bool:
    objective = research_request.objective
    return (
        research_request.campaign_candidate_selection_id is not None
        or isinstance(objective, dict) and objective.get("mode") == "known_prospect"
    )


def _review_source(target: EvidenceGateTarget, source: CollectedSource) -> SourceAdmission:
    normalized_url = _normalized_url(source.url)
    if normalized_url is not None and normalized_url in target.trusted_source_urls:
        return SourceAdmission(
            source=source,
            state=SourceAdmissionState.ACCEPTED,
            reason="The source matches evidence captured during target resolution or selection.",
        )

    if target.official_origin and _origin(source.url) == target.official_origin:
        return SourceAdmission(
            source=source,
            state=SourceAdmissionState.ACCEPTED,
            reason="The source is hosted on the verified official website.",
        )

    source_text = " ".join(value for value in (source.title, source.excerpt) if value).casefold()
    company_name = target.company_name.casefold()
    if company_name not in source_text:
        return SourceAdmission(
            source=source,
            state=SourceAdmissionState.EXCLUDED,
            reason="The source does not identify the resolved target by name.",
        )

    if target.location and target.location.casefold() not in source_text:
        return SourceAdmission(
            source=source,
            state=SourceAdmissionState.NEEDS_REVIEW,
            reason="The source names the business but does not support the resolved location.",
        )

    return SourceAdmission(
        source=source,
        state=SourceAdmissionState.NEEDS_REVIEW,
        reason="The source names the target but is not traceably linked to its verified identity.",
    )


def _selection_confirms_identity(selection: CampaignCandidateSelection) -> bool:
    return any(
        isinstance(signal, dict)
        and signal.get("signal_type") == "business_identity_confirmed"
        and isinstance(signal.get("source"), dict)
        and _normalized_url(signal["source"].get("source_url")) is not None
        for signal in selection.evidence_snapshot
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
