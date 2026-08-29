# Opportunity Scoring Rubric

## Purpose

This rubric defines how the Strategy Agent should judge the strength of a sales
opportunity from supplied evidence. It is a decision policy, not a mathematical
scoring formula.

## Score Bands

### 0-39 - do_not_prioritize

Use when the available evidence does not justify prioritizing the company.
Typical conditions include weak or missing evidence, stale or irrelevant
signals, no credible pain-point support, or an opportunity based mainly on
speculation.

### 40-69 - consider

Use when meaningful opportunity signals exist, but the evidence is incomplete,
mixed, indirect, or insufficient for strong prioritization.

### 70-100 - prioritize

Use when multiple relevant, current, and credible signals indicate a strong
sales opportunity, including credible support for a potential pain point. A
high score requires evidence; company size, success, or reputation alone is
not sufficient.

Scores in each band should normally use the matching contact recommendation:

- 0-39 -> `do_not_prioritize`
- 40-69 -> `consider`
- 70-100 -> `prioritize`

## Positive Signals

Consider expansion or significant growth, recent funding or investment,
relevant hiring, stated technical scale or complexity, and credible pain-point
support. Signals must be relevant to a potential sales opportunity, not merely
facts about the company.

## Score-Lowering Conditions

Lower the opportunity score when evidence is weak or missing, signals are
stale or irrelevant, a claimed pain point is unsupported, or the opportunity
depends primarily on speculation. Do not compensate for missing evidence by
inventing assumptions.

## Evidence and Inference

Every score reason must cite supplied evidence and explain why the cited signal
matters to the potential sales opportunity. Distinguish facts directly supported
by evidence from reasonable inferences and unsupported speculation. Do not
present an inference or hypothesis as an established company fact.

Do not invent company facts, pain points, buying intent, budgets, or other
unsupported information.

## Recency and Relevance

Prefer evidence that is recent, directly relevant to the opportunity, and
specific rather than generic. Older evidence may still be useful, but should
carry less weight when it may no longer represent the company's current
situation.

## Signal Combination

Evaluate signals together rather than independently. Multiple relevant signals
that reinforce one another provide stronger evidence than a single isolated
signal. Multiple weak or unrelated signals do not automatically constitute
strong evidence. A credible pain-point hypothesis is especially important when
assigning a high score. The score must reflect the strength of the overall
opportunity case, not simply the number of positive signals.

## Avoid False Precision

Do not assign fixed point values to individual signals. The score represents
evidence-based judgment within the defined bands; its reasons and citations are
more important than artificial mathematical precision.
