from types import SimpleNamespace

import pytest

from app.models.campaign_prospect import CampaignProspectNextAction, CampaignProspectState
from app.models.research_report import ReportKind
from app.schemas.opportunity_qualification import OpportunityQualificationState
from app.services.aggregate_verdict import AggregateVerdict
from app.services import report_generation


def test_deep_qualified_request_uses_prospect_evidence_brief(monkeypatch):
    request = SimpleNamespace(campaign_candidate_selection_id=None)
    company = object()
    handoffs = SimpleNamespace(
        evidence_quality_review=SimpleNamespace(
            context=SimpleNamespace(
                qualifications=[SimpleNamespace(state=OpportunityQualificationState.LIKELY)]
            )
        )
    )
    opportunity_handoff = object()
    opportunity_output = object()
    brief = object()
    calls = []

    monkeypatch.setattr(report_generation, "requires_deep_qualification", lambda _: True)
    monkeypatch.setattr(
        report_generation,
        "build_prospect_evidence_brief_handoffs",
        lambda db, received_request, received_company, selection: calls.append(
            (db, received_request, received_company, selection)
        ) or handoffs,
    )
    monkeypatch.setattr(
        report_generation,
        "build_opportunity_outreach_handoff",
        lambda db, received_request, received_company, selection, brief_handoffs: (
            calls.append("handoff") or opportunity_handoff
        ),
    )
    monkeypatch.setattr(
        report_generation,
        "run_opportunity_outreach_agent",
        lambda received: calls.append("agent") or opportunity_output,
    )
    monkeypatch.setattr(
        report_generation,
        "run_prospect_evidence_brief_crew",
        lambda received_handoffs, received_output: (
            brief
            if received_handoffs is handoffs and received_output is opportunity_output
            else None
        ),
    )

    report, report_kind = report_generation._generate_report(
        object(),
        request,
        company,
    )

    assert report is brief
    assert report_kind is ReportKind.PROSPECT_EVIDENCE_BRIEF
    assert calls[0][1:3] == (request, company)
    assert calls.count("handoff") == 1
    assert calls.count("agent") == 1


@pytest.mark.parametrize(
    "state",
    [
        OpportunityQualificationState.INSUFFICIENT_EVIDENCE,
        OpportunityQualificationState.NOT_ELIGIBLE,
    ],
)
def test_nonqualified_brief_skips_opportunity_outreach_agent(monkeypatch, state):
    request = SimpleNamespace(campaign_candidate_selection_id=None)
    handoffs = SimpleNamespace(
        evidence_quality_review=SimpleNamespace(
            context=SimpleNamespace(qualifications=[SimpleNamespace(state=state)])
        )
    )
    calls = []
    monkeypatch.setattr(report_generation, "requires_deep_qualification", lambda _: True)
    monkeypatch.setattr(
        report_generation,
        "build_prospect_evidence_brief_handoffs",
        lambda *_: handoffs,
    )
    monkeypatch.setattr(
        report_generation,
        "build_opportunity_outreach_handoff",
        lambda *_args, **_kwargs: calls.append("handoff"),
    )
    monkeypatch.setattr(
        report_generation,
        "run_opportunity_outreach_agent",
        lambda *_: calls.append("agent"),
    )
    monkeypatch.setattr(
        report_generation,
        "run_prospect_evidence_brief_crew",
        lambda received, output: (received, output),
    )

    report, kind = report_generation._generate_report(object(), request, object())

    assert report == (handoffs, None)
    assert kind is ReportKind.PROSPECT_EVIDENCE_BRIEF
    assert calls == []


def test_invalid_qualified_output_stops_before_report_assembly(monkeypatch):
    request = SimpleNamespace(campaign_candidate_selection_id=None)
    handoffs = SimpleNamespace(
        evidence_quality_review=SimpleNamespace(
            context=SimpleNamespace(
                qualifications=[SimpleNamespace(state=OpportunityQualificationState.LIKELY)]
            )
        )
    )
    assembled = False
    monkeypatch.setattr(report_generation, "requires_deep_qualification", lambda _: True)
    monkeypatch.setattr(
        report_generation, "build_prospect_evidence_brief_handoffs", lambda *_: handoffs
    )
    monkeypatch.setattr(
        report_generation, "build_opportunity_outreach_handoff", lambda *_args, **_kwargs: object()
    )
    monkeypatch.setattr(
        report_generation,
        "run_opportunity_outreach_agent",
        lambda _handoff: (_ for _ in ()).throw(ValueError("invalid grounded output")),
    )

    def assemble(*_):
        nonlocal assembled
        assembled = True

    monkeypatch.setattr(report_generation, "run_prospect_evidence_brief_crew", assemble)

    with pytest.raises(ValueError, match="invalid grounded output"):
        report_generation._generate_report(object(), request, object())
    assert assembled is False


def test_standard_request_keeps_legacy_report_generation(monkeypatch):
    request = SimpleNamespace(id="request", user_id="user")
    company = SimpleNamespace(name="Example Corp")
    sources = [object()]
    legacy_report = object()
    calls = []

    monkeypatch.setattr(report_generation, "requires_deep_qualification", lambda _: False)
    monkeypatch.setattr(report_generation, "list_research_sources_for_user", lambda **_: sources)
    monkeypatch.setattr(report_generation, "build_research_evidence_context", lambda _: "evidence")
    monkeypatch.setattr(report_generation, "_objective_context_from_request", lambda _: "objective")
    monkeypatch.setattr(
        report_generation,
        "run_sales_intelligence_crew",
        lambda **kwargs: calls.append(kwargs) or legacy_report,
    )

    report, report_kind = report_generation._generate_report(
        object(),
        request,
        company,
        "focus on mobile",
    )

    assert report is legacy_report
    assert report_kind is ReportKind.LEGACY_SALES_INTELLIGENCE
    assert calls == [
        {
            "company_name": "Example Corp",
            "evidence_context": "evidence",
            "guidance": "focus on mobile",
            "objective_context": "objective",
        }
    ]


@pytest.mark.parametrize(
    ("verdict", "workflow_state", "next_action"),
    [
        (
            AggregateVerdict.QUALIFIED,
            CampaignProspectState.READY_FOR_OUTREACH,
            CampaignProspectNextAction.PREPARE_OUTREACH,
        ),
        (
            AggregateVerdict.NEEDS_REVIEW,
            CampaignProspectState.NEEDS_RESEARCH,
            CampaignProspectNextAction.COLLECT_EVIDENCE,
        ),
        (
            AggregateVerdict.NOT_A_FIT,
            CampaignProspectState.NOT_A_FIT,
            CampaignProspectNextAction.NO_ACTION,
        ),
    ],
)
def test_campaign_state_uses_report_aggregate(
    monkeypatch, verdict, workflow_state, next_action
):
    class Brief:
        aggregate_verdict = verdict

    prospect = SimpleNamespace(workflow_state=None, next_action=None)
    selection = SimpleNamespace(campaign_run_id="run", source_identity_key="source")

    class Db:
        def get(self, *_):
            return selection

        def scalar(self, _statement):
            return prospect

        def commit(self):
            pass

    monkeypatch.setattr(report_generation, "ProspectEvidenceBrief", Brief)
    report_generation._sync_campaign_prospect_state(
        Db(),
        SimpleNamespace(campaign_candidate_selection_id="selection"),
        Brief(),
    )

    assert prospect.workflow_state is workflow_state
    assert prospect.next_action is next_action
