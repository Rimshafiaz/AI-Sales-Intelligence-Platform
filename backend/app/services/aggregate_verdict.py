"""The single source of truth for the campaign-level opportunity verdict.

Precedence (model-specific qualification rows are always the input):

    ANY model LIKELY            -> QUALIFIED
    NO LIKELY + any unresolved  -> NEEDS_REVIEW
    ALL models NOT_ELIGIBLE     -> NOT_A_FIT

One model being NOT_ELIGIBLE never disqualifies the prospect while another
selected model remains unresolved. Every consumer (brief headline, campaign
prospect state, outreach eligibility, batch filtering, badges) must reuse this
function instead of re-deriving precedence locally.
"""

from enum import Enum

from app.schemas.opportunity_qualification import OpportunityQualificationState


class AggregateVerdict(str, Enum):
    QUALIFIED = "qualified"
    NEEDS_REVIEW = "needs_review"
    NOT_A_FIT = "not_a_fit"


# The qualification enum has one unresolved state; the evidence gate's
# NEEDS_REVIEW lives upstream of qualification and never reaches this verdict.
UNRESOLVED_STATES = {
    OpportunityQualificationState.INSUFFICIENT_EVIDENCE,
}


def aggregate_verdict(
    states: list[OpportunityQualificationState],
) -> AggregateVerdict:
    if not states:
        return AggregateVerdict.NEEDS_REVIEW
    if any(state is OpportunityQualificationState.LIKELY for state in states):
        return AggregateVerdict.QUALIFIED
    if all(state is OpportunityQualificationState.NOT_ELIGIBLE for state in states):
        return AggregateVerdict.NOT_A_FIT
    return AggregateVerdict.NEEDS_REVIEW


AGGREGATE_VERDICT_HEADLINES: dict[AggregateVerdict, str] = {
    AggregateVerdict.QUALIFIED: "Qualified opportunity",
    AggregateVerdict.NEEDS_REVIEW: "Needs review",
    AggregateVerdict.NOT_A_FIT: "Not a fit for this goal",
}


def aggregate_headline(verdict: AggregateVerdict) -> str:
    return AGGREGATE_VERDICT_HEADLINES[verdict]
