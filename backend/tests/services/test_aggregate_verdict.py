from app.schemas.opportunity_qualification import OpportunityQualificationState
from app.services.aggregate_verdict import (
    AggregateVerdict,
    aggregate_headline,
    aggregate_verdict,
)


def states(*items: OpportunityQualificationState) -> list[OpportunityQualificationState]:
    return list(items)


def test_any_likely_qualifies_even_with_disqualified_and_unresolved_models():
    verdict = aggregate_verdict(
        states(
            OpportunityQualificationState.NOT_ELIGIBLE,
            OpportunityQualificationState.INSUFFICIENT_EVIDENCE,
            OpportunityQualificationState.LIKELY,
        )
    )
    assert verdict is AggregateVerdict.QUALIFIED
    assert aggregate_headline(verdict) == "Qualified opportunity"


def test_al_ghani_shape_is_needs_review_not_not_a_fit():
    verdict = aggregate_verdict(
        states(
            OpportunityQualificationState.NOT_ELIGIBLE,
            OpportunityQualificationState.NOT_ELIGIBLE,
            OpportunityQualificationState.INSUFFICIENT_EVIDENCE,
        )
    )
    assert verdict is AggregateVerdict.NEEDS_REVIEW
    assert aggregate_headline(verdict) == "Needs review"


def test_all_not_eligible_is_not_a_fit():
    verdict = aggregate_verdict(
        states(
            OpportunityQualificationState.NOT_ELIGIBLE,
            OpportunityQualificationState.NOT_ELIGIBLE,
            OpportunityQualificationState.NOT_ELIGIBLE,
        )
    )
    assert verdict is AggregateVerdict.NOT_A_FIT
    assert aggregate_headline(verdict) == "Not a fit for this goal"


def test_single_not_eligible_model_with_no_others_is_not_a_fit():
    verdict = aggregate_verdict(states(OpportunityQualificationState.NOT_ELIGIBLE))
    assert verdict is AggregateVerdict.NOT_A_FIT


def test_unresolved_only_is_needs_review():
    verdict = aggregate_verdict(states(OpportunityQualificationState.INSUFFICIENT_EVIDENCE))
    assert verdict is AggregateVerdict.NEEDS_REVIEW


def test_empty_states_default_to_needs_review():
    assert aggregate_verdict([]) is AggregateVerdict.NEEDS_REVIEW
