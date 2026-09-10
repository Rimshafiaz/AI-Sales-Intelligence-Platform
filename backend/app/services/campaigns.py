import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.campaign_prospect import CampaignProspect, CampaignProspectState

from app.models.campaign import Campaign
from app.models.campaign_candidate_selection import CampaignCandidateSelection
from app.models.campaign_run import CampaignRun, CampaignRunStatus
from app.models.company import Company
from app.models.research_request import ResearchRequest, ResearchStatus
from app.models.user import User
from app.schemas.campaign import (
    CampaignCandidateSelectionCreate,
    CampaignCandidateSelectionResponse,
    CampaignCreate,
    CampaignRecommendedBatchCreate,
    CampaignRecommendedBatchResponse,
    CampaignResponse,
    CampaignRunCreate,
    CampaignRunResponse,
)


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


def list_campaigns_for_user(db: Session, user_id: uuid.UUID) -> list[Campaign]:
    statement = (
        select(Campaign)
        .where(Campaign.user_id == user_id)
        .order_by(Campaign.created_at.desc())
    )
    return list(db.scalars(statement).all())


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
    ruled_out = {
        prospect.source_identity_key
        for prospect in db.scalars(
            select(CampaignProspect).where(
                CampaignProspect.campaign_run_id == campaign_run.id,
                CampaignProspect.workflow_state == CampaignProspectState.NOT_A_FIT,
            )
        ).all()
    }
    selection_data = []
    skipped = 0
    for opportunity in batch_data.opportunities:
        queue_model_ids = {reason.model_id for reason in opportunity.queue_entry.reasons}
        if not queue_model_ids <= selected_model_ids:
            raise CampaignWorkflowError(
                "The recommended candidate does not match this campaign's Opportunity Models."
            )
        source_identity_key = (
            f"{opportunity.candidate_input.candidate.source_provider}:"
            f"{opportunity.candidate_input.candidate.source_record_id}"
        )
        if source_identity_key in ruled_out:
            skipped += 1
            continue
        selection_data.append(
            CampaignCandidateSelectionCreate(
                candidate_input=opportunity.candidate_input,
                shortlist_entry=opportunity.shortlist_entry,
            )
        )
    if skipped and not selection_data:
        raise CampaignWorkflowError(
            "Every selected prospect was already researched and ruled out for this campaign."
        )
    if skipped:
        raise CampaignWorkflowError(
            "Some selected prospects were already researched and ruled out for "
            "this campaign. Deselect them and try again."
        )
    return create_candidate_selections_and_research_requests(
        db,
        campaign_run,
        current_user,
        selection_data,
    )


def create_candidate_selections_and_research_requests(
    db: Session,
    campaign_run: CampaignRun,
    current_user: User,
    selections_data: list[CampaignCandidateSelectionCreate],
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


def campaign_response(campaign: Campaign) -> CampaignResponse:
    return CampaignResponse(
        id=campaign.id,
        title=campaign.title,
        goal=campaign.goal,
        criteria=campaign.discovery_criteria,
        model_selection=campaign.model_selection,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
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
        created_at=selection.created_at,
    )


def campaign_recommended_batch_response(
    selections: list[tuple[CampaignCandidateSelection, ResearchRequest]],
) -> CampaignRecommendedBatchResponse:
    return CampaignRecommendedBatchResponse(
        selections=[
            campaign_candidate_selection_response(selection, research_request)
            for selection, research_request in selections
        ]
    )


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
