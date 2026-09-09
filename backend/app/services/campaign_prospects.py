from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.campaign_prospect import CampaignProspect, CampaignProspectNextAction, CampaignProspectState
from app.models.campaign_run import CampaignRun
from app.models.user import User
from app.schemas.campaign_prospect import CampaignProspectCreate, CampaignProspectResponse, CampaignProspectUpdate
from app.schemas.discovery_shortlist import DiscoveryShortlistState


class CampaignProspectError(ValueError):
    pass


def save_campaign_prospect(
    db: Session,
    campaign_id: UUID,
    current_user: User,
    request: CampaignProspectCreate,
) -> CampaignProspect:
    campaign = _campaign_for_user(db, campaign_id, current_user.id)
    if campaign is None:
        raise CampaignProspectError("Campaign not found.")
    campaign_run = db.scalar(
        select(CampaignRun).where(
            CampaignRun.id == request.campaign_run_id,
            CampaignRun.campaign_id == campaign.id,
        )
    )
    if campaign_run is None:
        raise CampaignProspectError("Campaign run does not belong to this campaign.")
    candidate = request.candidate_input.candidate
    source_identity_key = f"{candidate.source_provider}:{candidate.source_record_id}"
    existing = db.scalar(
        select(CampaignProspect).where(
            CampaignProspect.campaign_id == campaign.id,
            CampaignProspect.source_identity_key == source_identity_key,
        )
    )
    if existing is not None:
        raise CampaignProspectError("This candidate is already saved in the campaign.")
    prospect = CampaignProspect(
        campaign_id=campaign.id,
        campaign_run_id=campaign_run.id,
        source_identity_key=source_identity_key,
        candidate_index=request.shortlist_entry.candidate_index,
        candidate_snapshot=candidate.model_dump(mode="json"),
        shortlist_snapshot=request.shortlist_entry.model_dump(mode="json"),
        evidence_snapshot=[
            signal.model_dump(mode="json")
            for signal in request.candidate_input.evidence_signals
        ],
        workflow_state=CampaignProspectState.SAVED,
        next_action=_initial_next_action(request.shortlist_entry.state),
    )
    db.add(prospect)
    db.commit()
    db.refresh(prospect)
    return prospect


def list_campaign_prospects(
    db: Session,
    campaign_id: UUID,
    current_user: User,
) -> list[CampaignProspect]:
    if _campaign_for_user(db, campaign_id, current_user.id) is None:
        raise CampaignProspectError("Campaign not found.")
    statement = (
        select(CampaignProspect)
        .where(CampaignProspect.campaign_id == campaign_id)
        .order_by(CampaignProspect.created_at.desc())
    )
    return list(db.scalars(statement).all())


def update_campaign_prospect(
    db: Session,
    campaign_id: UUID,
    prospect_id: UUID,
    current_user: User,
    request: CampaignProspectUpdate,
) -> CampaignProspect:
    prospect = _prospect_for_user(db, campaign_id, prospect_id, current_user.id)
    if prospect is None:
        raise CampaignProspectError("Campaign prospect not found.")
    prospect.workflow_state = request.workflow_state
    prospect.next_action = _next_action_for_state(request.workflow_state)
    db.commit()
    db.refresh(prospect)
    return prospect


def campaign_prospect_response(prospect: CampaignProspect) -> CampaignProspectResponse:
    return CampaignProspectResponse.model_validate(prospect)


def _campaign_for_user(db: Session, campaign_id: UUID, user_id: UUID) -> Campaign | None:
    return db.scalar(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == user_id)
    )


def _prospect_for_user(
    db: Session,
    campaign_id: UUID,
    prospect_id: UUID,
    user_id: UUID,
) -> CampaignProspect | None:
    return db.scalar(
        select(CampaignProspect)
        .join(Campaign)
        .where(
            CampaignProspect.id == prospect_id,
            CampaignProspect.campaign_id == campaign_id,
            Campaign.user_id == user_id,
        )
    )


def _initial_next_action(state: DiscoveryShortlistState) -> CampaignProspectNextAction:
    if state is DiscoveryShortlistState.NEEDS_IDENTITY_REVIEW:
        return CampaignProspectNextAction.COLLECT_EVIDENCE
    if state is DiscoveryShortlistState.NEEDS_EVIDENCE:
        return CampaignProspectNextAction.COLLECT_EVIDENCE
    return CampaignProspectNextAction.RESEARCH_PROSPECT


def _next_action_for_state(state: CampaignProspectState) -> CampaignProspectNextAction:
    if state in {CampaignProspectState.SAVED, CampaignProspectState.NEEDS_RESEARCH}:
        return CampaignProspectNextAction.RESEARCH_PROSPECT
    if state is CampaignProspectState.READY_FOR_OUTREACH:
        return CampaignProspectNextAction.PREPARE_OUTREACH
    return CampaignProspectNextAction.NO_ACTION
