import uuid
from datetime import UTC, datetime

import pytest

from app.ai.tools import website_research
from app.models.campaign_candidate_selection import CampaignCandidateSelection
from app.models.campaign_run import CampaignRun
from app.models.company import Company
from app.models.research_evidence import ResearchEvidence
from app.models.research_request import ResearchRequest, ResearchStatus
from app.schemas.evidence_gate import EvidenceGateState
from app.schemas.opportunity_models import EvidenceSignalType
from app.schemas.website_audit import WebsiteAuditState, WebsiteCheckResult, WebsiteCheckState
from app.schemas.website_research import (
    GroundedWebsiteEvidenceResult,
    VerifiedWebsiteTargetResult,
    WebsiteCapabilityResult,
)
from app.services.website_audit import WebsiteAuditError


NOW = datetime(2026, 9, 14, tzinfo=UTC)


class FakeSession:
    def __init__(self, run, evidence=()):
        self.run = run
        self.evidence = list(evidence)
        self.commit_calls = 0

    def get(self, model, _value):
        return self.run if model is CampaignRun else None

    def scalars(self, _statement):
        return iter(self.evidence)

    def commit(self):
        self.commit_calls += 1

    def refresh(self, value):
        return value


def context(model_ids=("web_conversion.mobile_performance",), verified=True):
    user_id = uuid.uuid4()
    company = Company(id=uuid.uuid4(), user_id=user_id, name="Glow Salon")
    selection = CampaignCandidateSelection(
        id=uuid.uuid4(),
        campaign_run_id=uuid.uuid4(),
        company_id=company.id,
        source_identity_key="places:glow",
        candidate_snapshot={},
        shortlist_snapshot={},
        evidence_snapshot=[],
    )
    request = ResearchRequest(
        id=uuid.uuid4(),
        company_id=company.id,
        user_id=user_id,
        campaign_candidate_selection_id=selection.id,
        status=ResearchStatus.COMPLETED,
        evidence_gate_state=EvidenceGateState.READY_FOR_DEEPER_RESEARCH,
        website_audit_state=WebsiteAuditState.NOT_RUN,
        objective={
            "resolved_target": {
                "business_name": company.name,
                "website": "https://glow.example/" if verified else None,
                "identity_state": "verified" if verified else "needs_review",
                "source": {
                    "provider": "official_website",
                    "source_url": "https://glow.example/about",
                    "retrieved_at": NOW.isoformat(),
                },
            }
        },
    )
    run = CampaignRun(
        id=selection.campaign_run_id,
        campaign_id=uuid.uuid4(),
        criteria_snapshot={"business_category": "restaurants_cafes"},
        model_selection_snapshot={
            "model_ids": list(model_ids),
            "confirmed_by_user": True,
        },
        provider_summary={},
        discovered_candidate_count=1,
    )
    return FakeSession(run), request, company, selection, user_id


def tools_by_name(bound_tools):
    return {item.name: item for item in bound_tools}


class TestBoundWebsiteResearchTools:
    def test_tools_have_no_llm_controlled_arguments(self):
        db, request, company, selection, user_id = context()
        tools = website_research.build_website_research_tools(
            db, request, company, selection, user_id
        )

        assert len(tools) == 4
        assert all(not item.args_schema.model_fields for item in tools)
        with pytest.raises(TypeError):
            tools[0].run(url="https://attacker.example")

    def test_factory_rejects_another_user_context(self):
        db, request, company, selection, _user_id = context()

        with pytest.raises(WebsiteAuditError, match="not available"):
            website_research.build_website_research_tools(
                db, request, company, selection, uuid.uuid4()
            )

    def test_target_tool_reads_persisted_target_without_resolution(self, monkeypatch):
        db, request, company, selection, user_id = context()

        def forbidden_resolution(*_args, **_kwargs):
            raise AssertionError("website resolution must not run")

        monkeypatch.setattr(
            "app.services.company_resolution.CompanyWebsiteResolver.resolve",
            forbidden_resolution,
        )
        target_tool = tools_by_name(
            website_research.build_website_research_tools(
                db, request, company, selection, user_id
            )
        )["get_verified_website_target"]

        result = VerifiedWebsiteTargetResult.model_validate_json(target_tool.run())

        assert result.website_status == "verified"
        assert str(result.official_website).rstrip("/") == "https://glow.example"

    def test_mobile_tool_delegates_with_bound_context(self, monkeypatch):
        db, request, company, selection, user_id = context()
        received = []

        def measure(*args):
            received.append(args)
            return WebsiteCheckResult(
                WebsiteCheckState.EVIDENCE_FOUND,
                "measurement saved",
                EvidenceSignalType.WEBSITE_MOBILE_PERFORMANCE_MEASURED,
                43.0,
                "pagespeed:https://glow.example/",
            )

        monkeypatch.setattr(website_research, "measure_mobile_performance", measure)
        mobile_tool = tools_by_name(
            website_research.build_website_research_tools(
                db, request, company, selection, user_id
            )
        )["measure_verified_website_mobile_performance"]

        result = WebsiteCapabilityResult.model_validate_json(mobile_tool.run())

        assert received == [(db, request, company, selection, user_id)]
        assert result.numeric_value == 43.0

    def test_conversion_tool_delegates_with_bound_context(self, monkeypatch):
        db, request, company, selection, user_id = context(
            ("web_conversion.restaurant_customer_path",)
        )
        received = []

        def inspect(*args):
            received.append(args)
            return WebsiteCheckResult(
                WebsiteCheckState.NO_GAP_OBSERVED,
                "no qualifying gap",
            )

        monkeypatch.setattr(website_research, "inspect_conversion_paths", inspect)
        conversion_tool = tools_by_name(
            website_research.build_website_research_tools(
                db, request, company, selection, user_id
            )
        )["inspect_verified_website_conversion_paths"]

        result = WebsiteCapabilityResult.model_validate_json(conversion_tool.run())

        assert received == [(db, request, company, selection, user_id)]
        assert result.state is WebsiteCheckState.NO_GAP_OBSERVED

    def test_unselected_capability_remains_not_permitted(self):
        db, request, company, selection, user_id = context(
            ("web_conversion.restaurant_customer_path",)
        )
        mobile_tool = tools_by_name(
            website_research.build_website_research_tools(
                db, request, company, selection, user_id
            )
        )["measure_verified_website_mobile_performance"]

        result = WebsiteCapabilityResult.model_validate_json(mobile_tool.run())

        assert result.state is WebsiteCheckState.NOT_PERMITTED

    def test_unverified_target_cannot_reach_network_checks(self, monkeypatch):
        db, request, company, selection, user_id = context(
            (
                "web_conversion.mobile_performance",
                "web_conversion.restaurant_customer_path",
            ),
            verified=False,
        )

        def forbidden(*_args, **_kwargs):
            raise AssertionError("network call must not run")

        monkeypatch.setattr(
            "app.services.website_audit.create_pagespeed_provider", forbidden
        )
        monkeypatch.setattr(
            "app.services.website_audit.WebsiteMetadataCollector.collect_conversion_snapshot",
            forbidden,
        )
        tools = tools_by_name(
            website_research.build_website_research_tools(
                db, request, company, selection, user_id
            )
        )

        mobile = WebsiteCapabilityResult.model_validate_json(
            tools["measure_verified_website_mobile_performance"].run()
        )
        conversion = WebsiteCapabilityResult.model_validate_json(
            tools["inspect_verified_website_conversion_paths"].run()
        )

        assert mobile.state is WebsiteCheckState.UNAVAILABLE
        assert conversion.state is WebsiteCheckState.UNAVAILABLE

    def test_evidence_reader_filters_nonwebsite_evidence_and_is_read_only(self):
        db, request, company, selection, user_id = context()
        db.evidence = [
            ResearchEvidence(
                id=uuid.uuid4(),
                research_request_id=request.id,
                signal_type="website_mobile_performance_measured",
                evidence_type="observed",
                supporting_value="PageSpeed measured 43/100.",
                numeric_value=43.0,
                source_provider="pagespeed_insights",
                source_identity_key="pagespeed:https://glow.example/",
                source_url="https://glow.example/",
                retrieved_at=NOW,
                captured_at=NOW,
            ),
            ResearchEvidence(
                id=uuid.uuid4(),
                research_request_id=request.id,
                signal_type="social_dormancy_measured",
                evidence_type="observed",
                supporting_value="Latest post was 90 days ago.",
                numeric_value=90.0,
                source_provider="social_profile",
                source_identity_key="social:test",
                source_url="https://instagram.com/glow",
                retrieved_at=NOW,
                captured_at=NOW,
            ),
        ]
        original_snapshot = dict(db.run.model_selection_snapshot)
        evidence_tool = tools_by_name(
            website_research.build_website_research_tools(
                db, request, company, selection, user_id
            )
        )["read_grounded_website_evidence"]

        result = GroundedWebsiteEvidenceResult.model_validate_json(evidence_tool.run())

        assert EvidenceSignalType.WEBSITE_MOBILE_PERFORMANCE_MEASURED in {
            item.signal_type for item in result.evidence
        }
        assert all(item.signal_type.value != "social_dormancy_measured" for item in result.evidence)
        assert db.commit_calls == 0
        assert db.run.model_selection_snapshot == original_snapshot
