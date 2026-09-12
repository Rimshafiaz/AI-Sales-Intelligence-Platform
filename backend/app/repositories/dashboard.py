from datetime import datetime
from uuid import UUID

from sqlalchemy import func, literal, select, union_all
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


def list_dashboard_prospects(
    db: Session,
    user_id: UUID,
    actionable_limit: int,
    recent_limit: int,
) -> list[tuple[str, CampaignProspect, str]]:
    actionable = (
        select(
            CampaignProspect.id.label("prospect_id"),
            literal("actionable").label("purpose"),
            func.row_number()
            .over(order_by=CampaignProspect.updated_at.desc())
            .label("position"),
        )
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
        .limit(actionable_limit)
    )
    recent = (
        select(
            CampaignProspect.id.label("prospect_id"),
            literal("recent").label("purpose"),
            func.row_number()
            .over(order_by=CampaignProspect.created_at.desc())
            .label("position"),
        )
        .join(Campaign)
        .where(Campaign.user_id == user_id)
        .order_by(CampaignProspect.created_at.desc())
        .limit(recent_limit)
    )
    selected = union_all(actionable, recent).subquery()
    statement = (
        select(selected.c.purpose, CampaignProspect, Campaign.title)
        .join(CampaignProspect, CampaignProspect.id == selected.c.prospect_id)
        .join(Campaign, CampaignProspect.campaign_id == Campaign.id)
        .order_by(selected.c.purpose, selected.c.position)
    )
    return list(db.execute(statement).all())


def list_dashboard_outreach(
    db: Session,
    user_id: UUID,
    sent_before: datetime,
    actionable_limit: int,
    follow_up_limit: int,
    recent_limit: int,
) -> list[tuple[str, OutreachAttempt, CampaignProspect, str]]:
    actionable = (
        select(
            OutreachAttempt.id.label("attempt_id"),
            literal("actionable").label("purpose"),
            func.row_number()
            .over(order_by=OutreachAttempt.updated_at.desc())
            .label("position"),
        )
        .join(CampaignProspect, OutreachAttempt.campaign_prospect_id == CampaignProspect.id)
        .join(Campaign, CampaignProspect.campaign_id == Campaign.id)
        .where(
            OutreachAttempt.user_id == user_id,
            OutreachAttempt.status.in_([OutreachStatus.DRAFT, OutreachStatus.APPROVED]),
        )
        .order_by(OutreachAttempt.updated_at.desc())
        .limit(actionable_limit)
    )
    follow_up = (
        select(
            OutreachAttempt.id.label("attempt_id"),
            literal("follow_up").label("purpose"),
            func.row_number()
            .over(order_by=OutreachAttempt.sent_at.asc())
            .label("position"),
        )
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
        .limit(follow_up_limit)
    )
    recent = (
        select(
            OutreachAttempt.id.label("attempt_id"),
            literal("recent").label("purpose"),
            func.row_number()
            .over(order_by=OutreachAttempt.updated_at.desc())
            .label("position"),
        )
        .join(CampaignProspect, OutreachAttempt.campaign_prospect_id == CampaignProspect.id)
        .join(Campaign, CampaignProspect.campaign_id == Campaign.id)
        .where(OutreachAttempt.user_id == user_id)
        .order_by(OutreachAttempt.updated_at.desc())
        .limit(recent_limit)
    )
    selected = union_all(actionable, follow_up, recent).subquery()
    statement = (
        select(
            selected.c.purpose,
            OutreachAttempt,
            CampaignProspect,
            Campaign.title,
        )
        .join(OutreachAttempt, OutreachAttempt.id == selected.c.attempt_id)
        .join(CampaignProspect, OutreachAttempt.campaign_prospect_id == CampaignProspect.id)
        .join(Campaign, CampaignProspect.campaign_id == Campaign.id)
        .order_by(selected.c.purpose, selected.c.position)
    )
    return list(db.execute(statement).all())
