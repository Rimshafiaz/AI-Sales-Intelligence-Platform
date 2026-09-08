import re

from app.schemas.agent_outputs import BriefReviewerOutput
from app.schemas.prospect_evidence_brief import ProspectEvidenceBrief, ProspectEvidenceBriefHandoffs


FORBIDDEN_COMMERCIAL_CLAIMS = (
    r"\bhas (?:the )?budget\b",
    r"\bcan afford\b",
    r"\bis losing customers\b",
    r"\bloses customers\b",
    r"\bwill increase revenue\b",
    r"\bwill generate revenue\b",
    r"\bneeds (?:a |an |the )?(?:website|redesign|service|freelancer)\b",
    r"\bwants (?:a |an |the )?(?:website|redesign|service|freelancer)\b",
    r"\binternal workflow\b",
)


class ProspectEvidenceBriefReviewError(ValueError):
    pass


def require_approved_prospect_evidence_brief(
    handoffs: ProspectEvidenceBriefHandoffs,
    brief: ProspectEvidenceBrief,
    reviewer: BriefReviewerOutput,
) -> ProspectEvidenceBrief:
    if not reviewer.approved:
        raise ProspectEvidenceBriefReviewError(
            "Evidence reviewer rejected the Prospect Evidence Brief: "
            + "; ".join(reviewer.issues)
        )
    if brief.objective != handoffs.evidence_quality_review.context.objective:
        raise ProspectEvidenceBriefReviewError("The brief changed the user's stated objective.")
    if brief.prospect != handoffs.evidence_quality_review.context.prospect:
        raise ProspectEvidenceBriefReviewError("The brief changed the verified prospect identity.")
    if brief.evidence != handoffs.evidence_quality_review.context.evidence:
        raise ProspectEvidenceBriefReviewError("The brief changed the supplied evidence.")
    if brief.sources != handoffs.evidence_quality_review.context.sources:
        raise ProspectEvidenceBriefReviewError("The brief changed the supplied sources.")
    if brief.contacts != handoffs.evidence_quality_review.context.contacts:
        raise ProspectEvidenceBriefReviewError("The brief changed the supplied contact paths.")
    for statement in _claim_statements(brief):
        if any(re.search(pattern, statement, re.IGNORECASE) for pattern in FORBIDDEN_COMMERCIAL_CLAIMS):
            raise ProspectEvidenceBriefReviewError(
                "The brief contains an unsupported commercial claim."
            )
    return brief


def _claim_statements(brief: ProspectEvidenceBrief) -> list[str]:
    statements = [item.statement for item in brief.findings]
    if brief.pitch_angle is not None:
        statements.append(brief.pitch_angle.statement)
    for draft in brief.outreach_drafts:
        statements.append(draft.message)
        statements.extend(item.claim for item in draft.grounding)
    return statements
