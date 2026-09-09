from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.campaign_prospect import CampaignProspect, CampaignProspectNextAction
from app.models.outreach_attempt import (
    OutreachAttempt,
    OutreachChannel,
    OutreachStatus,
)
from app.models.user import User
from app.repositories.dashboard import (
    list_actionable_outreach,
    list_actionable_prospects,
    list_follow_ups_due,
    list_recent_outreach,
    list_recent_prospects,
    pipeline_counts_for_user,
)
from app.schemas.dashboard import (
    ActivityEvent,
    DashboardAction,
    DashboardSummaryResponse,
    PipelineSummary,
)


FOLLOW_UP_AFTER_DAYS = 5
ACTION_LIMIT = 10
ACTIVITY_LIMIT = 10
FETCH_LIMIT = 20

ACTION_PRIORITY = {
    "research_prospect": 0,
    "collect_evidence": 1,
    "prepare_outreach": 2,
    "approve_outreach": 3,
    "send_linkedin": 4,
    "follow_up": 5,
    "awaiting_gmail": 6,
}


def get_dashboard_summary_for_user(
    db: Session,
    current_user: User,
    now: datetime | None = None,
) -> DashboardSummaryResponse:
    current_time = now or datetime.now(UTC)
    counts = pipeline_counts_for_user(db, current_user.id)
    prospect_rows = list_actionable_prospects(db, current_user.id, FETCH_LIMIT)
    outreach_rows = list_actionable_outreach(db, current_user.id, FETCH_LIMIT)
    due_rows = list_follow_ups_due(
        db,
        current_user.id,
        current_time - timedelta(days=FOLLOW_UP_AFTER_DAYS),
        ACTION_LIMIT,
    )

    prospects_with_active_outreach = {attempt.campaign_prospect_id for attempt, _, _ in outreach_rows}
    prospect_actions = [
        _prospect_action(prospect, campaign_title)
        for prospect, campaign_title in prospect_rows
        if not (
            prospect.next_action is CampaignProspectNextAction.PREPARE_OUTREACH
            and prospect.id in prospects_with_active_outreach
        )
    ]
    outreach_actions = [
        _outreach_action(attempt, prospect, campaign_title)
        for attempt, prospect, campaign_title in outreach_rows
    ]
    needs_attention = sorted(
        [*prospect_actions, *outreach_actions],
        key=lambda action: ACTION_PRIORITY[action.action_type],
    )[:ACTION_LIMIT]
    follow_ups = [
        _follow_up_action(attempt, prospect, campaign_title, current_time)
        for attempt, prospect, campaign_title in due_rows
    ]
    next_best_action = min(
        [*needs_attention, *follow_ups],
        key=lambda action: ACTION_PRIORITY[action.action_type],
        default=None,
    )

    recent_activity = _recent_activity(db, current_user)
    return DashboardSummaryResponse(
        pipeline=PipelineSummary(
            prospects_saved=counts[0],
            needs_research=counts[1],
            ready_for_outreach=counts[2],
            contacted=counts[3],
            replied=counts[4],
            interested=counts[5],
        ),
        needs_attention=needs_attention,
        follow_ups_due=follow_ups,
        recent_activity=recent_activity,
        next_best_action=next_best_action,
    )


def _prospect_action(prospect: CampaignProspect, campaign_title: str) -> DashboardAction:
    action_type = prospect.next_action.value
    reasons = {
        "research_prospect": "This saved prospect is ready for deeper research.",
        "collect_evidence": "More evidence is required before qualification.",
        "prepare_outreach": "A likely opportunity is ready for an outreach draft.",
    }
    return DashboardAction(
        action_type=action_type,
        campaign_id=prospect.campaign_id,
        campaign_title=campaign_title,
        prospect_id=prospect.id,
        prospect_name=_prospect_name(prospect),
        reason=reasons[action_type],
        reference_at=prospect.updated_at,
    )


def _outreach_action(
    attempt: OutreachAttempt,
    prospect: CampaignProspect,
    campaign_title: str,
) -> DashboardAction:
    if attempt.status is OutreachStatus.DRAFT:
        action_type = "approve_outreach"
        reason = f"Review and approve the {attempt.channel.value} draft."
    elif attempt.channel is OutreachChannel.LINKEDIN:
        action_type = "send_linkedin"
        reason = "This approved LinkedIn message is ready for manual sending."
    else:
        action_type = "awaiting_gmail"
        reason = "This approved email is waiting for Gmail connection and sending."
    return DashboardAction(
        action_type=action_type,
        campaign_id=prospect.campaign_id,
        campaign_title=campaign_title,
        prospect_id=prospect.id,
        prospect_name=_prospect_name(prospect),
        outreach_attempt_id=attempt.id,
        channel=attempt.channel,
        reason=reason,
        reference_at=attempt.updated_at,
    )


def _follow_up_action(
    attempt: OutreachAttempt,
    prospect: CampaignProspect,
    campaign_title: str,
    now: datetime,
) -> DashboardAction:
    days_since_send = max(FOLLOW_UP_AFTER_DAYS, (now - attempt.sent_at).days)
    return DashboardAction(
        action_type="follow_up",
        campaign_id=prospect.campaign_id,
        campaign_title=campaign_title,
        prospect_id=prospect.id,
        prospect_name=_prospect_name(prospect),
        outreach_attempt_id=attempt.id,
        channel=attempt.channel,
        reason=f"No reply has been recorded {days_since_send} days after sending.",
        reference_at=attempt.sent_at,
    )


def _recent_activity(db: Session, current_user: User) -> list[ActivityEvent]:
    events = [
        ActivityEvent(
            event_type="prospect_saved",
            campaign_title=campaign_title,
            prospect_id=prospect.id,
            prospect_name=_prospect_name(prospect),
            occurred_at=prospect.created_at,
        )
        for prospect, campaign_title in list_recent_prospects(
            db, current_user.id, ACTIVITY_LIMIT
        )
    ]
    events.extend(
        _outreach_activity(attempt, prospect, campaign_title)
        for attempt, prospect, campaign_title in list_recent_outreach(
            db, current_user.id, ACTIVITY_LIMIT
        )
    )
    return sorted(events, key=lambda event: event.occurred_at, reverse=True)[:ACTIVITY_LIMIT]


def _outreach_activity(
    attempt: OutreachAttempt,
    prospect: CampaignProspect,
    campaign_title: str,
) -> ActivityEvent:
    if attempt.replied_at is not None:
        event_type = "outreach_replied"
        occurred_at = attempt.replied_at
    elif attempt.status is OutreachStatus.CLOSED and attempt.outcome_recorded_at is not None:
        event_type = "outreach_closed"
        occurred_at = attempt.outcome_recorded_at
    elif attempt.sent_at is not None:
        event_type = "outreach_sent"
        occurred_at = attempt.sent_at
    elif attempt.approved_at is not None:
        event_type = "outreach_approved"
        occurred_at = attempt.approved_at
    else:
        event_type = "outreach_draft_created"
        occurred_at = attempt.created_at
    return ActivityEvent(
        event_type=event_type,
        campaign_title=campaign_title,
        prospect_id=prospect.id,
        prospect_name=_prospect_name(prospect),
        channel=attempt.channel,
        occurred_at=occurred_at,
    )


def _prospect_name(prospect: CampaignProspect) -> str:
    name = prospect.candidate_snapshot.get("company_name")
    return name.strip() if isinstance(name, str) and name.strip() else "Unnamed business"
