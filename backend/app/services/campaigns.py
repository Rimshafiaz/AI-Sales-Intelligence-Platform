import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.campaign_prospect import (
    CampaignProspect,
    CampaignProspectNextAction,
    CampaignProspectState,
)

from app.models.campaign import Campaign
from app.models.campaign_candidate_selection import CampaignCandidateSelection
from app.models.campaign_run import CampaignRun, CampaignRunStatus
from app.models.company import Company
from app.models.opportunity_qualification import OpportunityQualification
from app.models.research_request import ResearchRequest, ResearchStatus
from app.models.user import User
from app.schemas.campaign import (
    CampaignCandidateSelectionCreate,
    CampaignCandidateSelectionResponse,
    CampaignCandidatePoolSnapshot,
    CampaignCreate,
    CampaignRecommendedBatchCreate,
    CampaignRecommendedBatchResponse,
    CampaignResponse,
    CampaignResearchBatchMember,
    CampaignResearchBatchSummary,
    CampaignResearchQueueResponse,
    CampaignRunCreate,
    CampaignRunResponse,
)
from app.schemas.discovery_shortlist import (
    DiscoveryShortlistState,
    PreparedDiscoveryOpportunity,
)
from app.schemas.evidence_gate import EvidenceGateState
from app.schemas.opportunity_models import OpportunityModelSelection
from app.schemas.opportunity_qualification import OpportunityQualificationState
from app.services.aggregate_verdict import aggregate_verdict


class CampaignWorkflowError(ValueError):
    pass


def create_campaign(
    db: Session,
    current_user: User,
    campaign_data: CampaignCreate,
) -> Campaign:
    campaign = Campaign(
        user_id=current_user.id,
        title=campaign_data.title.strip(),
        goal=campaign_data.criteria.goal,
        discovery_criteria=campaign_data.criteria.model_dump(mode="json"),
        model_selection=campaign_data.model_selection.model_dump(mode="json"),
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


def list_campaign_summaries_for_user(
    db: Session,
    user_id: uuid.UUID,
) -> list[tuple[Campaign, int, int]]:
    statement = (
        select(
            Campaign,
            func.count(CampaignProspect.id),
            func.count(CampaignProspect.id).filter(
                CampaignProspect.workflow_state
                == CampaignProspectState.READY_FOR_OUTREACH
            ),
        )
        .outerjoin(CampaignProspect, CampaignProspect.campaign_id == Campaign.id)
        .where(Campaign.user_id == user_id)
        .group_by(Campaign.id)
        .order_by(Campaign.created_at.desc())
    )
    return [(campaign, saved, ready) for campaign, saved, ready in db.execute(statement)]


def get_campaign_for_user(
    db: Session,
    campaign_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Campaign | None:
    statement = select(Campaign).where(
        Campaign.id == campaign_id,
        Campaign.user_id == user_id,
    )
    return db.scalar(statement)


def create_campaign_run(
    db: Session,
    campaign: Campaign,
    run_data: CampaignRunCreate,
) -> CampaignRun:
    campaign_run = CampaignRun(
        campaign_id=campaign.id,
        status=CampaignRunStatus.COMPLETED,
        criteria_snapshot=campaign.discovery_criteria,
        model_selection_snapshot=campaign.model_selection,
        provider_summary=run_data.provider_summary,
        discovered_candidate_count=run_data.discovered_candidate_count,
        candidate_pool_snapshot=run_data.candidate_pool_snapshot.model_dump(mode="json"),
    )
    db.add(campaign_run)
    db.commit()
    db.refresh(campaign_run)
    return campaign_run


def get_campaign_run_for_user(
    db: Session,
    campaign_run_id: uuid.UUID,
    user_id: uuid.UUID,
) -> CampaignRun | None:
    statement = (
        select(CampaignRun)
        .join(Campaign)
        .where(
            CampaignRun.id == campaign_run_id,
            Campaign.user_id == user_id,
        )
    )
    return db.scalar(statement)


def create_candidate_selection_and_research_request(
    db: Session,
    campaign_run: CampaignRun,
    current_user: User,
    selection_data: CampaignCandidateSelectionCreate,
) -> tuple[CampaignCandidateSelection, ResearchRequest]:
    selections = create_candidate_selections_and_research_requests(
        db,
        campaign_run,
        current_user,
        [selection_data],
    )
    return selections[0]


def create_recommended_research_batch(
    db: Session,
    campaign_run: CampaignRun,
    current_user: User,
    batch_data: CampaignRecommendedBatchCreate,
) -> list[tuple[CampaignCandidateSelection, ResearchRequest]]:
    selected_model_ids = set(campaign_run.model_selection_snapshot.get("model_ids", []))
    remaining_by_key = {
        _opportunity_source_key(opportunity): opportunity
        for opportunity in remaining_campaign_run_candidates(db, campaign_run)
    }
    selection_data = []
    for submitted in batch_data.opportunities:
        source_identity_key = _opportunity_source_key(submitted)
        opportunity = remaining_by_key.get(source_identity_key)
        if opportunity is None:
            raise CampaignWorkflowError(
                "This candidate is not available in the campaign run's remaining pool."
            )
        queue_model_ids = {reason.model_id for reason in opportunity.queue_entry.reasons}
        if opportunity.queue_entry.verification_reason:
            queue_model_ids.update(
                evaluation.model_id
                for evaluation in opportunity.shortlist_entry.model_evaluations
                if evaluation.state
                is DiscoveryShortlistState.ELIGIBLE_FOR_DEEPER_RESEARCH
                and evaluation.missing_signal_types
            )
        if not queue_model_ids <= selected_model_ids:
            raise CampaignWorkflowError(
                "The recommended candidate does not match this campaign's Opportunity Models."
            )
        selection_data.append(
            CampaignCandidateSelectionCreate(
                candidate_input=opportunity.candidate_input,
                shortlist_entry=opportunity.shortlist_entry,
            )
        )
    return create_candidate_selections_and_research_requests(
        db,
        campaign_run,
        current_user,
        selection_data,
        research_batch_id=uuid.uuid4(),
    )


def create_candidate_selections_and_research_requests(
    db: Session,
    campaign_run: CampaignRun,
    current_user: User,
    selections_data: list[CampaignCandidateSelectionCreate],
    research_batch_id: uuid.UUID | None = None,
) -> list[tuple[CampaignCandidateSelection, ResearchRequest]]:
    source_identity_keys = [
        f"{selection_data.candidate_input.candidate.source_provider}:"
        f"{selection_data.candidate_input.candidate.source_record_id}"
        for selection_data in selections_data
    ]
    if len(source_identity_keys) != len(set(source_identity_keys)):
        raise CampaignWorkflowError("This candidate appears more than once in the batch.")

    for source_identity_key in source_identity_keys:
        existing_selection = db.scalar(
            select(CampaignCandidateSelection).where(
                CampaignCandidateSelection.campaign_run_id == campaign_run.id,
                CampaignCandidateSelection.source_identity_key == source_identity_key,
            )
        )
        if existing_selection is not None:
            raise CampaignWorkflowError("This candidate has already been selected in this run.")

    created: list[tuple[CampaignCandidateSelection, ResearchRequest]] = []
    try:
        for selection_data, source_identity_key in zip(
            selections_data,
            source_identity_keys,
            strict=True,
        ):
            candidate = selection_data.candidate_input.candidate
            existing_company = db.scalar(
                select(Company).where(
                    Company.user_id == current_user.id,
                    Company.identity_key == source_identity_key,
                )
            )
            company = existing_company or Company(
                id=uuid.uuid4(),
                user_id=current_user.id,
                name=candidate.company_name,
                website=str(candidate.website).rstrip("/") if candidate.website else None,
                identity_key=source_identity_key,
            )
            selection = CampaignCandidateSelection(
                id=uuid.uuid4(),
                campaign_run_id=campaign_run.id,
                company_id=company.id,
                source_identity_key=source_identity_key,
                research_batch_id=research_batch_id,
                candidate_snapshot=candidate.model_dump(mode="json"),
                shortlist_snapshot=selection_data.shortlist_entry.model_dump(mode="json"),
                evidence_snapshot=[
                    signal.model_dump(mode="json")
                    for signal in selection_data.candidate_input.evidence_signals
                ],
            )
            research_request = ResearchRequest(
                id=uuid.uuid4(),
                company_id=company.id,
                user_id=current_user.id,
                campaign_candidate_selection_id=selection.id,
                status=ResearchStatus.PENDING,
                opportunity_model_selection=OpportunityModelSelection.model_validate(
                    campaign_run.model_selection_snapshot
                ).model_dump(mode="json"),
                objective=_campaign_research_objective(
                    campaign_run,
                    selection,
                    candidate.company_name,
                ),
            )
            if existing_company is None:
                db.add(company)
            db.add(selection)
            db.add(research_request)
            existing_prospect = db.scalar(
                select(CampaignProspect).where(
                    CampaignProspect.campaign_id == campaign_run.campaign_id,
                    CampaignProspect.source_identity_key == source_identity_key,
                )
            )
            if existing_prospect is None:
                db.add(
                    CampaignProspect(
                        campaign_id=campaign_run.campaign_id,
                        campaign_run_id=campaign_run.id,
                        source_identity_key=source_identity_key,
                        candidate_index=selection_data.shortlist_entry.candidate_index,
                        candidate_snapshot=candidate.model_dump(mode="json"),
                        shortlist_snapshot=selection_data.shortlist_entry.model_dump(mode="json"),
                        evidence_snapshot=[
                            signal.model_dump(mode="json")
                            for signal in selection_data.candidate_input.evidence_signals
                        ],
                        workflow_state=CampaignProspectState.NEEDS_RESEARCH,
                        next_action=CampaignProspectNextAction.COLLECT_EVIDENCE,
                    )
                )
            created.append((selection, research_request))
        db.commit()
        for selection, research_request in created:
            db.refresh(selection)
            db.refresh(research_request)
    except Exception:
        db.rollback()
        raise
    return created


def list_campaign_selections_for_user(
    db: Session,
    campaign_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[tuple[CampaignCandidateSelection, ResearchRequest]]:
    statement = (
        select(CampaignCandidateSelection)
        .join(CampaignRun)
        .join(Campaign)
        .options(selectinload(CampaignCandidateSelection.research_request))
        .where(
            Campaign.id == campaign_id,
            Campaign.user_id == user_id,
        )
        .order_by(CampaignCandidateSelection.created_at.desc())
    )
    selections = db.scalars(statement).all()
    return [
        (selection, selection.research_request)
        for selection in selections
        if selection.research_request is not None
    ]


def campaign_response(
    campaign: Campaign,
    saved_prospect_count: int = 0,
    ready_prospect_count: int = 0,
) -> CampaignResponse:
    return CampaignResponse(
        id=campaign.id,
        title=campaign.title,
        goal=campaign.goal,
        criteria=campaign.discovery_criteria,
        model_selection=campaign.model_selection,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
        saved_prospect_count=saved_prospect_count,
        ready_prospect_count=ready_prospect_count,
    )


def campaign_run_response(campaign_run: CampaignRun) -> CampaignRunResponse:
    return CampaignRunResponse(
        id=campaign_run.id,
        campaign_id=campaign_run.campaign_id,
        status=campaign_run.status.value,
        criteria_snapshot=campaign_run.criteria_snapshot,
        model_selection_snapshot=campaign_run.model_selection_snapshot,
        provider_summary=campaign_run.provider_summary,
        discovered_candidate_count=campaign_run.discovered_candidate_count,
        created_at=campaign_run.created_at,
    )


def campaign_candidate_selection_response(
    selection: CampaignCandidateSelection,
    research_request: ResearchRequest,
) -> CampaignCandidateSelectionResponse:
    return CampaignCandidateSelectionResponse(
        id=selection.id,
        campaign_run_id=selection.campaign_run_id,
        company_id=selection.company_id,
        research_request_id=research_request.id,
        source_identity_key=selection.source_identity_key,
        research_batch_id=selection.research_batch_id,
        created_at=selection.created_at,
    )


def campaign_recommended_batch_response(
    selections: list[tuple[CampaignCandidateSelection, ResearchRequest]],
) -> CampaignRecommendedBatchResponse:
    research_batch_id = selections[0][0].research_batch_id
    if research_batch_id is None:
        raise CampaignWorkflowError("The research batch has no durable identifier.")
    return CampaignRecommendedBatchResponse(
        research_batch_id=research_batch_id,
        selections=[
            campaign_candidate_selection_response(selection, research_request)
            for selection, research_request in selections
        ]
    )


def remaining_campaign_run_candidates(
    db: Session,
    campaign_run: CampaignRun,
) -> list[PreparedDiscoveryOpportunity]:
    try:
        snapshot = CampaignCandidatePoolSnapshot.model_validate(
            campaign_run.candidate_pool_snapshot
        )
    except ValueError as error:
        raise CampaignWorkflowError(
            "This historical campaign run has no durable candidate pool."
        ) from error
    selected_keys = set(
        db.scalars(
            select(CampaignCandidateSelection.source_identity_key).where(
                CampaignCandidateSelection.campaign_run_id == campaign_run.id
            )
        ).all()
    )
    return [
        opportunity
        for opportunity in snapshot.candidates
        if _opportunity_source_key(opportunity) not in selected_keys
    ]


def campaign_research_queue_response(
    db: Session,
    campaign_run: CampaignRun,
) -> CampaignResearchQueueResponse:
    snapshot = CampaignCandidatePoolSnapshot.model_validate(
        campaign_run.candidate_pool_snapshot
    )
    remaining = remaining_campaign_run_candidates(db, campaign_run)
    return CampaignResearchQueueResponse(
        campaign_id=campaign_run.campaign_id,
        campaign_run_id=campaign_run.id,
        criteria=campaign_run.criteria_snapshot,
        model_selection=campaign_run.model_selection_snapshot,
        pool_count=len(snapshot.candidates),
        selected_count=len(snapshot.candidates) - len(remaining),
        remaining_count=len(remaining),
        candidates=remaining,
    )


def research_batch_summary_for_request(
    db: Session,
    request_id: uuid.UUID,
    user_id: uuid.UUID,
) -> CampaignResearchBatchSummary | None:
    anchor = db.scalar(
        select(CampaignCandidateSelection)
        .join(ResearchRequest)
        .join(CampaignRun)
        .join(Campaign)
        .where(
            ResearchRequest.id == request_id,
            Campaign.user_id == user_id,
        )
    )
    if anchor is None or anchor.research_batch_id is None:
        return None
    selections = list(
        db.scalars(
            select(CampaignCandidateSelection)
            .options(selectinload(CampaignCandidateSelection.research_request))
            .where(
                CampaignCandidateSelection.campaign_run_id == anchor.campaign_run_id,
                CampaignCandidateSelection.research_batch_id == anchor.research_batch_id,
            )
            .order_by(CampaignCandidateSelection.created_at, CampaignCandidateSelection.id)
        ).all()
    )
    request_ids = [
        selection.research_request.id
        for selection in selections
        if selection.research_request is not None
    ]
    qualification_rows = db.scalars(
        select(OpportunityQualification).where(
            OpportunityQualification.research_request_id.in_(request_ids)
        )
    ).all()
    states_by_request: dict[uuid.UUID, list[OpportunityQualificationState]] = {}
    for row in qualification_rows:
        states_by_request.setdefault(row.research_request_id, []).append(
            OpportunityQualificationState(row.state)
        )
    counts = {key: 0 for key in ("qualified", "not_a_fit", "needs_review", "failed", "pending")}
    members = []
    for selection in selections:
        research_request = selection.research_request
        if research_request is None:
            continue
        states = states_by_request.get(research_request.id, [])
        if research_request.status is ResearchStatus.FAILED:
            outcome = "failed"
        elif states:
            outcome = aggregate_verdict(states).value
        elif (
            research_request.status is ResearchStatus.COMPLETED
            and research_request.evidence_gate_state is EvidenceGateState.NEEDS_REVIEW
        ):
            outcome = "needs_review"
        else:
            outcome = "pending"
        counts[outcome] += 1
        members.append(
            CampaignResearchBatchMember(
                selection_id=selection.id,
                research_request_id=research_request.id,
                company_name=str(selection.candidate_snapshot.get("company_name") or "Prospect"),
                outcome=outcome,
            )
        )
    campaign_run = db.get(CampaignRun, anchor.campaign_run_id)
    if campaign_run is None:
        return None
    return CampaignResearchBatchSummary(
        research_batch_id=anchor.research_batch_id,
        campaign_id=campaign_run.campaign_id,
        campaign_run_id=campaign_run.id,
        remaining_count=len(remaining_campaign_run_candidates(db, campaign_run)),
        members=members,
        **counts,
    )


def _opportunity_source_key(opportunity: PreparedDiscoveryOpportunity) -> str:
    candidate = opportunity.candidate_input.candidate
    return f"{candidate.source_provider}:{candidate.source_record_id}"


def _campaign_research_objective(
    campaign_run: CampaignRun,
    selection: CampaignCandidateSelection,
    company_name: str,
) -> dict:
    criteria = campaign_run.criteria_snapshot
    return {
        "campaign_id": str(campaign_run.campaign_id),
        "campaign_run_id": str(campaign_run.id),
        "campaign_candidate_selection_id": str(selection.id),
        "business_name": company_name,
        "goal": criteria.get("goal"),
        "offering": criteria.get("offering"),
        "desired_outcome": criteria.get("desired_outcome"),
        "industry": criteria.get("business_category"),
        "location": criteria.get("location"),
    }
