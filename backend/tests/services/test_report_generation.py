from types import SimpleNamespace

from app.models.research_report import ReportKind
from app.services import report_generation


def test_deep_qualified_request_uses_prospect_evidence_brief(monkeypatch):
    request = SimpleNamespace(campaign_candidate_selection_id=None)
    company = object()
    handoffs = object()
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
        "run_prospect_evidence_brief_crew",
        lambda received_handoffs: brief if received_handoffs is handoffs else None,
    )

    report, report_kind = report_generation._generate_report(
        object(),
        request,
        company,
    )

    assert report is brief
    assert report_kind is ReportKind.PROSPECT_EVIDENCE_BRIEF
    assert calls[0][1:3] == (request, company)


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
