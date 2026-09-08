from sqlalchemy.orm import Session

from app.models.campaign_candidate_selection import CampaignCandidateSelection
from app.models.company import Company
from app.models.research_evidence import ResearchEvidence
from app.models.research_request import ResearchRequest, ResearchStatus
from app.repositories.opportunity_qualifications import list_opportunity_qualifications_for_user
from app.repositories.research_evidence import list_research_evidence_for_user
from app.repositories.research_social_observations import list_social_observations_for_user
from app.repositories.research_sources import list_research_sources_for_user
from app.schemas.evidence_gate import EvidenceGateState, SourceAdmissionState
from app.schemas.opportunity_models import EvidenceSignal, EvidenceSignalType, EvidenceSource, EvidenceType
from app.schemas.prospect_evidence_brief import (
    BriefContactPath,
    BriefEvidence,
    BriefObjective,
    BriefProspect,
    BriefQualification,
    BriefSource,
    BusinessContextHandoff,
    ContactEvidenceState,
    ContactPathType,
    DigitalPresenceHandoff,
    EvidenceQualityReviewHandoff,
    OpportunityDiagnosisHandoff,
    ProspectEvidenceBriefContext,
    ProspectEvidenceBriefHandoffs,
    PublicTractionHandoff,
    StrategyOutreachHandoff,
)
from app.services.evidence_gate import target_from_research_request


MAX_BRIEF_SOURCES = 12


class ProspectEvidenceBriefContextError(ValueError):
    pass


def build_prospect_evidence_brief_handoffs(
    db: Session,
    research_request: ResearchRequest,
    company: Company,
    selection: CampaignCandidateSelection | None,
) -> ProspectEvidenceBriefHandoffs:
    _require_ready_request(research_request)
    target = target_from_research_request(research_request, company, selection)
    if not target.identity_verified:
        raise ProspectEvidenceBriefContextError("A Prospect Evidence Brief requires a verified business identity.")

    objective = _objective_from_request(research_request)
    evidence = _brief_evidence(
        db,
        research_request,
        selection,
        target.identity_verified,
        target.official_website is not None,
    )
    qualifications = _brief_qualifications(db, research_request)
    sources = _brief_sources(db, research_request)
    contacts = _brief_contacts(db, research_request, selection, target.official_website, evidence)
    context = ProspectEvidenceBriefContext(
        objective=objective,
        prospect=BriefProspect(
            business_name=target.company_name,
            location=target.location,
            official_website=target.official_website,
            identity_verified=target.identity_verified,
        ),
        qualifications=qualifications,
        evidence=evidence,
        sources=sources,
        contacts=contacts,
    )
    return ProspectEvidenceBriefHandoffs(
        business_context=BusinessContextHandoff(
            objective=context.objective,
            prospect=context.prospect,
            evidence=context.evidence,
            sources=context.sources,
        ),
        digital_presence=DigitalPresenceHandoff(
            objective=context.objective,
            prospect=context.prospect,
            evidence=context.evidence,
        ),
        public_traction=PublicTractionHandoff(
            objective=context.objective,
            prospect=context.prospect,
            sources=context.sources,
            evidence=context.evidence,
        ),
        opportunity_diagnosis=OpportunityDiagnosisHandoff(
            objective=context.objective,
            prospect=context.prospect,
            qualifications=context.qualifications,
            evidence=context.evidence,
        ),
        strategy_outreach=StrategyOutreachHandoff(
            objective=context.objective,
            prospect=context.prospect,
            qualifications=context.qualifications,
            evidence=context.evidence,
            contacts=context.contacts,
        ),
        evidence_quality_review=EvidenceQualityReviewHandoff(context=context),
    )


def _require_ready_request(research_request: ResearchRequest) -> None:
    if research_request.status is not ResearchStatus.COMPLETED:
        raise ProspectEvidenceBriefContextError("Finish the evidence review before building a Prospect Evidence Brief.")
    if research_request.evidence_gate_state is not EvidenceGateState.READY_FOR_DEEPER_RESEARCH:
        raise ProspectEvidenceBriefContextError("Accepted evidence is required before building a Prospect Evidence Brief.")


def _objective_from_request(research_request: ResearchRequest) -> BriefObjective:
    objective = research_request.objective or {}
    try:
        return BriefObjective(
            goal=objective.get("goal"),
            offering=objective.get("offering"),
            desired_outcome=objective.get("desired_outcome"),
        )
    except ValueError as error:
        raise ProspectEvidenceBriefContextError(
            "A Prospect Evidence Brief requires the user's goal, offering, and desired outcome."
        ) from error


def _brief_evidence(
    db: Session,
    research_request: ResearchRequest,
    selection: CampaignCandidateSelection | None,
    identity_verified: bool,
    official_website_verified: bool,
) -> list[BriefEvidence]:
    evidence = [
        _persisted_evidence(item)
        for item in list_research_evidence_for_user(
            db,
            research_request.id,
            research_request.user_id,
        )
    ]
    if selection is not None:
        evidence.extend(_selection_evidence(selection))
        if _selection_has_no_listed_website(selection):
            evidence.append(_no_listed_website_evidence(selection))
    evidence.extend(
        _resolved_target_evidence(
            research_request,
            selection,
            identity_verified,
            official_website_verified,
        )
    )
    if not evidence:
        raise ProspectEvidenceBriefContextError("No structured evidence is available for the Prospect Evidence Brief.")
    return evidence


def _persisted_evidence(item: ResearchEvidence) -> BriefEvidence:
    return BriefEvidence(
        key=f"research_evidence:{item.id}",
        signal_type=EvidenceSignalType(item.signal_type),
        evidence_type=EvidenceType(item.evidence_type),
        supporting_value=item.supporting_value,
        numeric_value=item.numeric_value,
        source=EvidenceSource(
            provider=item.source_provider,
            provider_record_id=item.source_record_id,
            source_url=item.source_url,
            retrieved_at=item.retrieved_at,
        ),
        captured_at=item.captured_at,
    )


def _selection_evidence(selection: CampaignCandidateSelection) -> list[BriefEvidence]:
    evidence = []
    for index, value in enumerate(selection.evidence_snapshot):
        try:
            signal = EvidenceSignal.model_validate(value)
        except ValueError:
            continue
        evidence.append(
            BriefEvidence(
                key=f"selection_evidence:{selection.id}:{index}",
                signal_type=signal.signal_type,
                evidence_type=signal.evidence_type,
                supporting_value=signal.supporting_value,
                numeric_value=signal.numeric_value,
                source=signal.source,
                captured_at=signal.captured_at,
            )
        )
    return evidence


def _selection_has_no_listed_website(selection: CampaignCandidateSelection) -> bool:
    candidate = selection.candidate_snapshot
    return candidate.get("website") is None and "local_places" in candidate.get(
        "discovery_source_types", []
    )


def _no_listed_website_evidence(selection: CampaignCandidateSelection) -> BriefEvidence:
    candidate = selection.candidate_snapshot
    source = EvidenceSource(
        provider=candidate["source_provider"],
        provider_record_id=candidate.get("source_record_id"),
        source_url=_first_url(candidate.get("supporting_source_urls", [])),
        retrieved_at=candidate["source_retrieved_at"],
    )
    return BriefEvidence(
        key=f"selection_candidate:{selection.id}:no_listed_official_website",
        signal_type=EvidenceSignalType.NO_LISTED_OFFICIAL_WEBSITE,
        evidence_type=EvidenceType.OBSERVED,
        supporting_value="The traceable local discovery record did not list an official website.",
        source=source,
        captured_at=source.retrieved_at,
    )


def _resolved_target_evidence(
    research_request: ResearchRequest,
    selection: CampaignCandidateSelection | None,
    identity_verified: bool,
    official_website_verified: bool,
) -> list[BriefEvidence]:
    if not identity_verified:
        return []
    source = _resolved_target_source(research_request, selection)
    if source is None:
        return []
    evidence = [
        BriefEvidence(
            key="resolved_target:identity",
            signal_type=EvidenceSignalType.BUSINESS_IDENTITY_CONFIRMED,
            evidence_type=EvidenceType.OBSERVED,
            supporting_value="The research target was resolved to a verified business identity.",
            source=source,
            captured_at=source.retrieved_at,
        )
    ]
    if official_website_verified:
        evidence.append(
            BriefEvidence(
                key="resolved_target:official_website",
                signal_type=EvidenceSignalType.OFFICIAL_WEBSITE_CONFIRMED,
                evidence_type=EvidenceType.OBSERVED,
                supporting_value="The resolved target includes a verified official website.",
                source=source,
                captured_at=source.retrieved_at,
            )
        )
    return evidence


def _resolved_target_source(
    research_request: ResearchRequest,
    selection: CampaignCandidateSelection | None,
) -> EvidenceSource | None:
    objective = research_request.objective or {}
    target = objective.get("resolved_target")
    if isinstance(target, dict) and isinstance(target.get("source"), dict):
        try:
            return EvidenceSource.model_validate(target["source"])
        except ValueError:
            return None
    if selection is None:
        return None
    for item in _selection_evidence(selection):
        if item.signal_type is EvidenceSignalType.BUSINESS_IDENTITY_CONFIRMED:
            return item.source
    return None


def _brief_qualifications(
    db: Session,
    research_request: ResearchRequest,
) -> list[BriefQualification]:
    qualifications = list_opportunity_qualifications_for_user(
        db,
        research_request.id,
        research_request.user_id,
        include_not_eligible=True,
    )
    if not qualifications:
        raise ProspectEvidenceBriefContextError("Run opportunity qualification before building a Prospect Evidence Brief.")
    return [
        BriefQualification(
            opportunity_model_id=item.opportunity_model_id,
            state=item.state,
            reason=item.reason,
            supporting_evidence_keys=item.supporting_evidence_keys,
            evaluated_at=item.evaluated_at,
        )
        for item in qualifications
    ]


def _brief_sources(db: Session, research_request: ResearchRequest) -> list[BriefSource]:
    sources = list_research_sources_for_user(
        db,
        research_request.id,
        research_request.user_id,
        limit=MAX_BRIEF_SOURCES,
        admission_state=SourceAdmissionState.ACCEPTED,
    )
    return [
        BriefSource(
            key=f"research_source:{item.id}",
            provider=item.source_type,
            source_url=item.url,
            retrieved_at=item.retrieved_at,
            title=item.title,
            excerpt=item.excerpt,
        )
        for item in sources
    ]


def _brief_contacts(
    db: Session,
    research_request: ResearchRequest,
    selection: CampaignCandidateSelection | None,
    official_website: str | None,
    evidence: list[BriefEvidence],
) -> list[BriefContactPath]:
    contacts = []
    evidence_keys = {item.key for item in evidence}
    if official_website and "resolved_target:official_website" in evidence_keys:
        contacts.append(
            BriefContactPath(
                contact_type=ContactPathType.WEBSITE,
                value=official_website,
                state=ContactEvidenceState.VERIFIED,
                source_keys=["resolved_target:official_website"],
            )
        )
    if selection is not None:
        phone = selection.candidate_snapshot.get("phone_number")
        identity_source_key = next(
            (
                item.key
                for item in evidence
                if item.signal_type is EvidenceSignalType.BUSINESS_IDENTITY_CONFIRMED
                and item.key.startswith("selection_evidence:")
            ),
            None,
        )
        if isinstance(phone, str) and phone.strip():
            if identity_source_key:
                contacts.append(
                    BriefContactPath(
                        contact_type=ContactPathType.PHONE,
                        value=phone.strip(),
                        state=ContactEvidenceState.OBSERVED,
                        source_keys=[identity_source_key],
                    )
                )
    for observation in list_social_observations_for_user(
        db,
        research_request.id,
        research_request.user_id,
    ):
        if observation.state != "observed":
            continue
        matching_evidence_keys = [
            item.key
            for item in evidence
            if item.signal_type is EvidenceSignalType.OFFICIAL_SOCIAL_PROFILE_CONFIRMED
            and str(item.source.source_url).rstrip("/").casefold()
            == observation.profile_url.rstrip("/").casefold()
        ]
        if matching_evidence_keys:
            contacts.append(
                BriefContactPath(
                    contact_type=ContactPathType.SOCIAL_PROFILE,
                    value=observation.profile_url,
                    state=ContactEvidenceState.VERIFIED,
                    source_keys=matching_evidence_keys,
                )
            )
    return contacts


def _first_url(values: object) -> str | None:
    if not isinstance(values, list):
        return None
    for value in values:
        if isinstance(value, str) and value.strip():
            return value
    return None
