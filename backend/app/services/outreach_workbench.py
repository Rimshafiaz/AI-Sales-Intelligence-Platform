"""Aggregated read model for the Outreach workbench.

One request returns everything the Outreach page renders: outreach-relevant
prospects grouped by campaign, with their existing attempts and available
grounded draft options. Reuses the same service functions and authorization
rules as the per-prospect routes — no duplicated business logic."""

from collections import defaultdict
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select, tuple_

from app.models.campaign import Campaign
from app.models.campaign_candidate_selection import CampaignCandidateSelection
from app.models.campaign_prospect import CampaignProspect
from app.models.campaign_run import CampaignRun
from app.models.outreach_attempt import OutreachAttempt, OutreachChannel, OutreachStatus
from app.models.research_report import ReportKind, ResearchReport
from app.models.research_request import ResearchRequest
from app.models.user import User
from app.schemas.campaign_prospect import CampaignProspectResponse
from app.schemas.outreach_attempt import OutreachAttemptResponse, OutreachDraftOptionResponse
from app.schemas.opportunity_qualification import OpportunityQualificationState
from app.schemas.prospect_evidence_brief import ProspectEvidenceBrief
from app.services.aggregate_verdict import AggregateVerdict
from app.services.campaign_prospects import campaign_prospect_response
from app.services.outreach_attempts import _contacts_for_channel, _recipient_key


class WorkbenchProspect(BaseModel):
    prospect: CampaignProspectResponse
    qualification_headline: str
    opportunity_reason: str
    pitch_angle: str | None
    attempts: list[OutreachAttemptResponse]
    options: list[OutreachDraftOptionResponse]


class WorkbenchGroup(BaseModel):
    campaign_id: UUID
    campaign_title: str
    prospects: list[WorkbenchProspect]


def outreach_workbench(db, current_user: User) -> list[WorkbenchGroup]:
    campaigns = db.scalars(
        select(Campaign).where(Campaign.user_id == current_user.id)
    ).all()
    campaign_ids = [campaign.id for campaign in campaigns]
    if not campaign_ids:
        return []

    prospects = db.scalars(
        select(CampaignProspect)
        .where(CampaignProspect.campaign_id.in_(campaign_ids))
        .order_by(CampaignProspect.created_at.desc())
    ).all()
    if not prospects:
        return []

    prospect_ids = [prospect.id for prospect in prospects]
    attempts = db.scalars(
        select(OutreachAttempt)
        .where(
            OutreachAttempt.campaign_prospect_id.in_(prospect_ids),
            OutreachAttempt.user_id == current_user.id,
        )
        .order_by(OutreachAttempt.created_at.desc())
    ).all()
    attempts_by_prospect = defaultdict(list)
    for attempt in attempts:
        attempts_by_prospect[attempt.campaign_prospect_id].append(attempt)

    identities = {
        (prospect.campaign_id, prospect.source_identity_key) for prospect in prospects
    }
    report_rows = db.execute(
        select(
            ResearchReport,
            CampaignRun.campaign_id,
            CampaignCandidateSelection.source_identity_key,
        )
        .join(ResearchRequest, ResearchReport.research_request_id == ResearchRequest.id)
        .join(
            CampaignCandidateSelection,
            ResearchRequest.campaign_candidate_selection_id == CampaignCandidateSelection.id,
        )
        .join(CampaignRun, CampaignCandidateSelection.campaign_run_id == CampaignRun.id)
        .where(
            ResearchReport.user_id == current_user.id,
            ResearchReport.report_kind == ReportKind.PROSPECT_EVIDENCE_BRIEF,
            tuple_(
                CampaignRun.campaign_id,
                CampaignCandidateSelection.source_identity_key,
            ).in_(identities),
        )
        .order_by(ResearchReport.generated_at.desc())
    ).all()
    reports_by_identity = defaultdict(list)
    for report, campaign_id, source_identity_key in report_rows:
        reports_by_identity[(campaign_id, source_identity_key)].append(report)

    prospects_by_campaign = defaultdict(list)
    for prospect in prospects:
        report_and_brief = _newest_valid_brief(
            reports_by_identity[(prospect.campaign_id, prospect.source_identity_key)]
        )
        if report_and_brief is None:
            continue
        report, brief = report_and_brief
        if brief.aggregate_verdict is not AggregateVerdict.QUALIFIED:
            continue
        prospect_attempts = attempts_by_prospect[prospect.id]
        prospects_by_campaign[prospect.campaign_id].append(
            WorkbenchProspect(
                prospect=campaign_prospect_response(prospect),
                qualification_headline=brief.aggregate_headline,
                opportunity_reason=brief.verdict.reason,
                pitch_angle=brief.pitch_angle.statement if brief.pitch_angle else None,
                attempts=prospect_attempts,
                options=_draft_options(report, brief, prospect_attempts),
            )
        )

    return [
        WorkbenchGroup(
            campaign_id=campaign.id,
            campaign_title=campaign.title,
            prospects=prospects_by_campaign[campaign.id],
        )
        for campaign in campaigns
        if prospects_by_campaign[campaign.id]
    ]


def _newest_valid_brief(
    reports: list[ResearchReport],
) -> tuple[ResearchReport, ProspectEvidenceBrief] | None:
    for report in reports:
        try:
            return report, ProspectEvidenceBrief.model_validate(report.report_data)
        except ValueError:
            continue
    return None


def _draft_options(
    report: ResearchReport,
    brief: ProspectEvidenceBrief,
    attempts: list[OutreachAttempt],
) -> list[OutreachDraftOptionResponse]:
    active_keys = {
        (
            attempt.research_report_id,
            attempt.channel,
            _recipient_key(attempt.channel, attempt.recipient),
        )
        for attempt in attempts
        if attempt.status
        in {OutreachStatus.DRAFT, OutreachStatus.APPROVED, OutreachStatus.SENDING}
    }
    if brief.verdict.state is not OpportunityQualificationState.LIKELY:
        return []
    options = []
    for draft in brief.outreach_drafts:
        channel = OutreachChannel(draft.channel.value)
        for contact in _contacts_for_channel(brief, channel):
            if (report.id, channel, _recipient_key(channel, contact.value)) in active_keys:
                continue
            options.append(
                OutreachDraftOptionResponse(
                    research_report_id=report.id,
                    channel=channel,
                    recipient=contact.value,
                    subject=draft.subject,
                    body=draft.message,
                )
            )
    return options
