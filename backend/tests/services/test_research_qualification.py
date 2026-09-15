import uuid

import pytest

from app.models.company import Company
from app.models.research_request import ResearchRequest
from app.schemas.agent_outputs import WebsiteResearchOutput
from app.schemas.opportunity_qualification import OpportunityQualificationRunRequest
from app.services import research_qualification
from app.services.opportunity_qualification import OpportunityQualificationError


class FakeSession:
    def __init__(self):
        self.commits = 0
        self.factual_evidence_created = False

    def commit(self):
        self.commits += 1

    def refresh(self, value):
        return value


def context(model_id="web_conversion.mobile_performance"):
    user_id = uuid.uuid4()
    company = Company(id=uuid.uuid4(), user_id=user_id, name="Glow Salon")
    request = ResearchRequest(
        id=uuid.uuid4(),
        company_id=company.id,
        user_id=user_id,
        opportunity_model_selection={
            "model_ids": [model_id],
            "confirmed_by_user": True,
        },
    )
    return FakeSession(), request, company


def output():
    return WebsiteResearchOutput(
        website_status="verified",
        findings=[],
        evidence_gaps=[],
        caveats=[],
    )


def test_web_research_creates_evidence_and_persists_output_before_qualification(monkeypatch):
    db, request, company = context()
    order = []

    def run(*_args):
        order.append("website")
        db.factual_evidence_created = True
        return output()

    def qualify(*_args):
        assert db.factual_evidence_created is True
        assert request.specialist_outputs["website"]["website_status"] == "verified"
        order.append("qualification")
        return ["decision"]

    monkeypatch.setattr(research_qualification, "run_website_research_agent", run)
    monkeypatch.setattr(research_qualification, "qualify_research_request", qualify)

    result = research_qualification.research_then_qualify(
        db, request, company, None, OpportunityQualificationRunRequest()
    )

    assert result == ["decision"]
    assert order == ["website", "qualification"]


def test_non_web_scope_skips_website_research(monkeypatch):
    db, request, company = context("social_presence.dormant_official_presence")
    monkeypatch.setattr(
        research_qualification,
        "run_website_research_agent",
        lambda *_: pytest.fail("website research must be skipped"),
    )
    monkeypatch.setattr(
        research_qualification, "qualify_research_request", lambda *_: ["decision"]
    )

    assert research_qualification.research_then_qualify(
        db, request, company, None, OpportunityQualificationRunRequest()
    ) == ["decision"]


def test_missing_manual_scope_is_not_guessed(monkeypatch):
    db, request, company = context()
    request.opportunity_model_selection = None
    monkeypatch.setattr(
        research_qualification,
        "qualify_research_request",
        lambda *_: pytest.fail("qualification must not run"),
    )

    with pytest.raises(OpportunityQualificationError, match="persisted"):
        research_qualification.research_then_qualify(
            db, request, company, None, OpportunityQualificationRunRequest()
        )


def test_invalid_specialist_output_prevents_qualification(monkeypatch):
    db, request, company = context()
    monkeypatch.setattr(
        research_qualification,
        "run_website_research_agent",
        lambda *_: {"website_status": "verified", "findings": [{"evidence_keys": ["missing"]}]},
    )
    monkeypatch.setattr(
        research_qualification,
        "qualify_research_request",
        lambda *_: pytest.fail("qualification must not run"),
    )

    with pytest.raises(ValueError):
        research_qualification.research_then_qualify(
            db, request, company, None, OpportunityQualificationRunRequest()
        )
