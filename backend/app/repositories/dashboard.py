from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.campaign_prospect import (
    CampaignProspect,
    CampaignProspectNextAction,
    CampaignProspectState,
)
from app.models.outreach_attempt import OutreachAttempt, OutreachOutcome, OutreachStatus


def pipeline_counts_for_user(db: Session, user_id: UUID) -> tuple[int, int, int, int, int, int]:
    owner_scope = Campaign.user_id == user_id
    prospects_saved = (
        select(func.count(CampaignProspect.id))
        .select_from(CampaignProspect)
        .join(Campaign)
        .where(owner_scope)
        .scalar_subquery()
    )
    needs_research = (
        select(func.count(CampaignProspect.id))
        .select_from(CampaignProspect)
        .join(Campaign)
        .where(
            owner_scope,
            CampaignProspect.next_action.in_(
                [
                    CampaignProspectNextAction.RESEARCH_PROSPECT,
                    CampaignProspectNextAction.COLLECT_EVIDENCE,
                ]
            ),
        )
        .scalar_subquery()
    )
    ready_for_outreach = (
        select(func.count(CampaignProspect.id))
        .select_from(CampaignProspect)
        .join(Campaign)
        .where(owner_scope, CampaignProspect.workflow_state == CampaignProspectState.READY_FOR_OUTREACH)
        .scalar_subquery()
    )
    contacted = (
        select(func.count(func.distinct(OutreachAttempt.campaign_prospect_id)))
        .where(OutreachAttempt.user_id == user_id, OutreachAttempt.sent_at.is_not(None))
        .scalar_subquery()
    )
    replied = (
        select(func.count(func.distinct(OutreachAttempt.campaign_prospect_id)))
        .where(OutreachAttempt.user_id == user_id, OutreachAttempt.replied_at.is_not(None))
        .scalar_subquery()
    )
    interested = (
        select(func.count(func.distinct(OutreachAttempt.campaign_prospect_id)))
        .where(
            OutreachAttempt.user_id == user_id,
            OutreachAttempt.outcome == OutreachOutcome.INTERESTED,
        )
        .scalar_subquery()
    )
    row = db.execute(
        select(
            prospects_saved,
            needs_research,
            ready_for_outreach,
            contacted,
            replied,
            interested,
        )
    ).one()
    return tuple(int(value or 0) for value in row)


def list_actionable_prospects(
    db: Session,
    user_id: UUID,
    limit: int,
) -> list[tuple[CampaignProspect, str]]:
    statement = (
        select(CampaignProspect, Campaign.title)
        .join(Campaign)
        .where(
            Campaign.user_id == user_id,
            CampaignProspect.next_action.in_(
                [
                    CampaignProspectNextAction.RESEARCH_PROSPECT,
                    CampaignProspectNextAction.COLLECT_EVIDENCE,
                    CampaignProspectNextAction.PREPARE_OUTREACH,
                ]
            ),
        )
        .order_by(CampaignProspect.updated_at.desc())
        .limit(limit)
    )
    return list(db.execute(statement).all())


def list_actionable_outreach(
    db: Session,
    user_id: UUID,
    limit: int,
) -> list[tuple[OutreachAttempt, CampaignProspect, str]]:
    statement = (
        select(OutreachAttempt, CampaignProspect, Campaign.title)
        .join(CampaignProspect, OutreachAttempt.campaign_prospect_id == CampaignProspect.id)
        .join(Campaign, CampaignProspect.campaign_id == Campaign.id)
        .where(
            OutreachAttempt.user_id == user_id,
            OutreachAttempt.status.in_([OutreachStatus.DRAFT, OutreachStatus.APPROVED]),
        )
        .order_by(OutreachAttempt.updated_at.desc())
        .limit(limit)
    )
    return list(db.execute(statement).all())


def list_follow_ups_due(
    db: Session,
    user_id: UUID,
    sent_before: datetime,
    limit: int,
) -> list[tuple[OutreachAttempt, CampaignProspect, str]]:
    statement = (
        select(OutreachAttempt, CampaignProspect, Campaign.title)
        .join(CampaignProspect, OutreachAttempt.campaign_prospect_id == CampaignProspect.id)
        .join(Campaign, CampaignProspect.campaign_id == Campaign.id)
        .where(
            OutreachAttempt.user_id == user_id,
            OutreachAttempt.status == OutreachStatus.SENT,
            OutreachAttempt.sent_at <= sent_before,
            OutreachAttempt.replied_at.is_(None),
            OutreachAttempt.outcome.is_(None),
        )
        .order_by(OutreachAttempt.sent_at.asc())
        .limit(limit)
    )
    return list(db.execute(statement).all())


def list_recent_prospects(
    db: Session,
    user_id: UUID,
    limit: int,
) -> list[tuple[CampaignProspect, str]]:
    statement = (
        select(CampaignProspect, Campaign.title)
        .join(Campaign)
        .where(Campaign.user_id == user_id)
        .order_by(CampaignProspect.created_at.desc())
        .limit(limit)
    )
    return list(db.execute(statement).all())


def list_recent_outreach(
    db: Session,
    user_id: UUID,
    limit: int,
) -> list[tuple[OutreachAttempt, CampaignProspect, str]]:
    statement = (
        select(OutreachAttempt, CampaignProspect, Campaign.title)
        .join(CampaignProspect, OutreachAttempt.campaign_prospect_id == CampaignProspect.id)
        .join(Campaign, CampaignProspect.campaign_id == Campaign.id)
        .where(OutreachAttempt.user_id == user_id)
        .order_by(OutreachAttempt.updated_at.desc())
        .limit(limit)
    )
    return list(db.execute(statement).all())
