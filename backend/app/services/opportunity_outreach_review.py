import re

from pydantic import ValidationError

from app.schemas.agent_outputs import BriefReviewOutput, OpportunityOutreachOutput
from app.schemas.opportunity_models import ServiceFamily
from app.schemas.opportunity_outreach import OpportunityOutreachHandoff
from app.schemas.opportunity_outreach_review import OpportunityOutreachReviewHandoff
from app.schemas.prospect_evidence_brief import OutreachChannel
from app.services.aggregate_verdict import AggregateVerdict, aggregate_verdict
from app.services.opportunity_model_catalog import get_opportunity_model
from app.services.opportunity_outreach import validate_opportunity_outreach_output


class OpportunityOutreachReviewError(ValueError):
    pass


class OpportunityOutreachRejectedError(OpportunityOutreachReviewError):
    def __init__(self, issues):
        self.issues = tuple(issues)
        details = "; ".join(
            f"{issue.issue_type}: {issue.reason}" for issue in self.issues
        )
        super().__init__(
            "Opportunity + Outreach review rejected the second candidate"
            + (f": {details}" if details else ".")
        )


REVIEWABLE_FIELDS = {
    "opportunity_summary",
    "pitch_angle",
    "personalization_basis",
    "forbidden_claims",
    "outreach_drafts",
    "caveats",
}
INDEXED_PERSONALIZATION = re.compile(r"personalization_basis\[(\d+)]")
CHANNEL_DRAFT = re.compile(r"outreach_drafts\[([^]]+)]")


def build_opportunity_outreach_review_handoff(
    context: OpportunityOutreachHandoff | dict,
    candidate: OpportunityOutreachOutput | dict,
) -> OpportunityOutreachReviewHandoff:
    try:
        trusted_context = OpportunityOutreachHandoff.model_validate(context)
        _validate_context(trusted_context)
        validated_candidate = validate_opportunity_outreach_output(
            candidate, trusted_context
        )
    except (ValueError, ValidationError) as error:
        raise OpportunityOutreachReviewError(
            "A trusted QUALIFIED context and validated Opportunity/Outreach candidate are required."
        ) from error
    return OpportunityOutreachReviewHandoff(
        context=trusted_context.model_copy(deep=True),
        candidate=validated_candidate.model_copy(deep=True),
    )


def validate_review_output(
    output: BriefReviewOutput | dict,
    handoff: OpportunityOutreachReviewHandoff,
) -> BriefReviewOutput:
    try:
        validated = BriefReviewOutput.model_validate(output)
    except ValidationError as error:
        raise OpportunityOutreachReviewError("Reviewer output is invalid.") from error
    for issue in validated.issues:
        if issue.field is not None and not _is_reviewable_field(
            issue.field, handoff.candidate
        ):
            raise OpportunityOutreachReviewError(
                f"Reviewer issue field is not reviewable: {issue.field}"
            )
    return validated


def _validate_context(context: OpportunityOutreachHandoff) -> None:
    if context.aggregate_verdict is not AggregateVerdict.QUALIFIED:
        raise OpportunityOutreachReviewError("Reviewer context must be QUALIFIED.")
    if aggregate_verdict([item.state for item in context.qualifications]) is not context.aggregate_verdict:
        raise OpportunityOutreachReviewError("Reviewer context aggregate contradicts qualification rows.")
    evidence_keys = [item.key for item in context.evidence]
    if len(evidence_keys) != len(set(evidence_keys)):
        raise OpportunityOutreachReviewError("Reviewer context contains duplicate evidence keys.")
    available = set(evidence_keys)
    if any(
        not set(item.supporting_evidence_keys) <= available
        for item in context.qualifications
    ):
        raise OpportunityOutreachReviewError("Reviewer qualifications cite unavailable evidence.")
    families = {
        get_opportunity_model(item.opportunity_model_id).service_family
        for item in context.qualifications
    }
    if ServiceFamily.WEB_CONVERSION in families and context.website_research is None:
        raise OpportunityOutreachReviewError("Required Website Research output is missing.")
    if ServiceFamily.SOCIAL_PRESENCE_CONTENT in families and context.social_research is None:
        raise OpportunityOutreachReviewError("Required Social Research output is missing.")
    for specialist in (context.website_research, context.social_research):
        if specialist is not None and any(
            not set(finding.evidence_keys) <= available
            for finding in specialist.findings
        ):
            raise OpportunityOutreachReviewError("Specialist output cites unavailable evidence.")
    if len(context.available_verified_channels) != len(set(context.available_verified_channels)):
        raise OpportunityOutreachReviewError("Reviewer context contains duplicate channels.")


def _is_reviewable_field(
    field: str,
    candidate: OpportunityOutreachOutput,
) -> bool:
    if field in REVIEWABLE_FIELDS:
        return True
    personalization = INDEXED_PERSONALIZATION.fullmatch(field)
    if personalization:
        return int(personalization.group(1)) < len(candidate.personalization_basis)
    draft = CHANNEL_DRAFT.fullmatch(field)
    if not draft:
        return False
    try:
        channel = OutreachChannel(draft.group(1))
    except ValueError:
        return False
    return channel in {item.channel for item in candidate.outreach_drafts}
