import uuid
from datetime import UTC, datetime

import pytest

from app.integrations.pagespeed import MobilePerformanceMeasurement, PageSpeedProviderError
from app.integrations.website_metadata import WebsiteConversionSnapshot
from app.models.campaign_candidate_selection import CampaignCandidateSelection
from app.models.campaign_run import CampaignRun
from app.models.company import Company
from app.models.research_evidence import ResearchEvidence
from app.models.research_request import ResearchRequest, ResearchStatus
from app.schemas.evidence_gate import EvidenceGateState
from app.schemas.website_audit import WebsiteAuditState, WebsiteCheckState
from app.services.website_audit import (
    WebsiteAuditError,
    audit_research_website,
    inspect_verified_website_conversion_paths,
    measure_verified_website_mobile_performance,
)


NOW = datetime(2026, 9, 8, tzinfo=UTC)


class FakeSession:
    def __init__(self, run=None, scalar_results=(), scalars_results=()):
        self.run = run
        self.scalar_results = list(scalar_results)
        self.scalars_results = list(scalars_results)
        self.added = []
        self.committed = False

    def scalar(self, _statement):
        return self.scalar_results.pop(0)

    def scalars(self, _statement):
        return iter(self.scalars_results.pop(0))

    def get(self, model, _value):
        return self.run if model is CampaignRun else None

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.committed = True

    def refresh(self, value):
        return value


class StubProvider:
    def __init__(self, measurement=None, error=None):
        self.measurement = measurement
        self.error = error
        self.urls = []

    def measure_mobile(self, website_url: str):
        self.urls.append(website_url)
        if self.error:
            raise self.error
        return self.measurement


class StubWebsiteCollector:
    def __init__(self, links):
        self.links = links
        self.urls = []

    def collect_conversion_snapshot(self, website):
        self.urls.append(website)
        return WebsiteConversionSnapshot(url=website, links=self.links)


def research_request(verified_website=True):
    return ResearchRequest(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        status=ResearchStatus.COMPLETED,
        evidence_gate_state=EvidenceGateState.READY_FOR_DEEPER_RESEARCH,
        objective={
            "location": "Lahore",
            "resolved_target": {
                "business_name": "Glow Salon",
                "website": "https://glow.example/" if verified_website else None,
                "identity_state": "verified" if verified_website else "needs_review",
                "source": {"source_url": "https://glow.example/about"},
            },
        },
    )


def company(request):
    return Company(id=request.company_id, user_id=request.user_id, name="Glow Salon")


def campaign_scope(request, model_ids, business_category="restaurants_cafes"):
    run = CampaignRun(
        id=uuid.uuid4(),
        campaign_id=uuid.uuid4(),
        criteria_snapshot={"business_category": business_category},
        model_selection_snapshot={"model_ids": model_ids, "confirmed_by_user": True},
        provider_summary={},
        discovered_candidate_count=1,
    )
    selection = CampaignCandidateSelection(
        id=uuid.uuid4(),
        campaign_run_id=run.id,
        company_id=request.company_id,
        source_identity_key="test:business",
        candidate_snapshot={},
        shortlist_snapshot={},
        evidence_snapshot=[],
    )
    request.campaign_candidate_selection_id = selection.id
    return run, selection


def measurement():
    return MobilePerformanceMeasurement(
        final_url="https://glow.example/",
        score=43.0,
        retrieved_at=NOW,
    )


class TestMobilePerformanceCapability:
    def test_unverified_website_never_reaches_pagespeed(self):
        request = research_request(verified_website=False)
        run, selection = campaign_scope(request, ["web_conversion.mobile_performance"])
        provider = StubProvider(measurement())

        result = measure_verified_website_mobile_performance(
            FakeSession(run), request, company(request), selection, request.user_id, provider
        )

        assert result.state is WebsiteCheckState.UNAVAILABLE
        assert provider.urls == []

    def test_mobile_check_requires_selected_mobile_model(self):
        request = research_request()
        run, selection = campaign_scope(
            request, ["web_conversion.restaurant_customer_path"]
        )
        provider = StubProvider(measurement())

        result = measure_verified_website_mobile_performance(
            FakeSession(run), request, company(request), selection, request.user_id, provider
        )

        assert result.state is WebsiteCheckState.NOT_PERMITTED
        assert provider.urls == []

    def test_verified_mobile_model_persists_canonical_evidence(self):
        request = research_request()
        run, selection = campaign_scope(request, ["web_conversion.mobile_performance"])
        provider = StubProvider(measurement())
        db = FakeSession(run, scalar_results=[None], scalars_results=[[]])

        result = measure_verified_website_mobile_performance(
            db, request, company(request), selection, request.user_id, provider
        )

        assert result.state is WebsiteCheckState.EVIDENCE_FOUND
        assert provider.urls == ["https://glow.example/"]
        evidence = db.added[0]
        assert isinstance(evidence, ResearchEvidence)
        assert evidence.signal_type == "website_mobile_performance_measured"
        assert evidence.numeric_value == 43.0
        assert evidence.source_provider == "pagespeed_insights"
        assert evidence.source_identity_key == "pagespeed:https://glow.example/"

    def test_existing_valid_measurement_skips_pagespeed(self):
        request = research_request()
        run, selection = campaign_scope(request, ["web_conversion.mobile_performance"])
        existing = ResearchEvidence(
            signal_type="website_mobile_performance_measured",
            numeric_value=43.0,
            source_identity_key="pagespeed:https://glow.example/",
        )
        provider = StubProvider(measurement())

        result = measure_verified_website_mobile_performance(
            FakeSession(run, scalars_results=[[existing]]),
            request,
            company(request),
            selection,
            request.user_id,
            provider,
        )

        assert result.state is WebsiteCheckState.ALREADY_AVAILABLE
        assert provider.urls == []


class TestConversionPathCapability:
    def test_conversion_inspection_requires_verified_website(self):
        request = research_request(verified_website=False)
        run, selection = campaign_scope(
            request, ["web_conversion.restaurant_customer_path"]
        )
        collector = StubWebsiteCollector(())

        result = inspect_verified_website_conversion_paths(
            FakeSession(run), request, company(request), selection, request.user_id, collector
        )

        assert result.state is WebsiteCheckState.UNAVAILABLE
        assert collector.urls == []

    def test_conversion_inspection_requires_supported_selected_model(self):
        request = research_request()
        run, selection = campaign_scope(request, ["web_conversion.mobile_performance"])
        collector = StubWebsiteCollector(())

        result = inspect_verified_website_conversion_paths(
            FakeSession(run), request, company(request), selection, request.user_id, collector
        )

        assert result.state is WebsiteCheckState.NOT_PERMITTED
        assert collector.urls == []

    def test_conversion_gap_persists_existing_deterministic_signal(self):
        request = research_request()
        run, selection = campaign_scope(
            request, ["web_conversion.restaurant_customer_path"]
        )
        db = FakeSession(run, scalar_results=[None], scalars_results=[[]])

        result = inspect_verified_website_conversion_paths(
            db,
            request,
            company(request),
            selection,
            request.user_id,
            StubWebsiteCollector(()),
        )

        assert result.state is WebsiteCheckState.EVIDENCE_FOUND
        assert db.added[0].signal_type == "website_restaurant_primary_path_not_observed"

    def test_no_qualifying_gap_is_distinct_from_evidence(self):
        request = research_request()
        run, selection = campaign_scope(
            request, ["web_conversion.restaurant_customer_path"]
        )
        collector = StubWebsiteCollector(
            (
                ("https://glow.example/menu", "Menu"),
                ("https://glow.example/contact", "Contact"),
            )
        )

        result = inspect_verified_website_conversion_paths(
            FakeSession(run, scalars_results=[[]]),
            request,
            company(request),
            selection,
            request.user_id,
            collector,
        )

        assert result.state is WebsiteCheckState.NO_GAP_OBSERVED


class TestWebsiteAuditCompatibility:
    def test_existing_wrapper_delegates_to_selected_capability(self):
        request = research_request()
        run, selection = campaign_scope(request, ["web_conversion.mobile_performance"])
        db = FakeSession(run, scalar_results=[None, request], scalars_results=[[]])
        provider = StubProvider(measurement())

        result = audit_research_website(db, request, company(request), selection, provider)

        assert result.website_audit_state is WebsiteAuditState.COMPLETED
        assert provider.urls == ["https://glow.example/"]

    def test_provider_failure_remains_unavailable(self):
        request = research_request()
        run, selection = campaign_scope(request, ["web_conversion.mobile_performance"])
        db = FakeSession(run, scalar_results=[request], scalars_results=[[]])
        provider = StubProvider(error=PageSpeedProviderError("PageSpeed quota reached."))

        result = audit_research_website(db, request, company(request), selection, provider)

        assert result.website_audit_state is WebsiteAuditState.UNAVAILABLE
        assert "quota" in result.website_audit_reason

    def test_shared_guard_enforces_user_context_and_evidence_gate(self):
        request = research_request()
        run, selection = campaign_scope(request, ["web_conversion.mobile_performance"])

        with pytest.raises(WebsiteAuditError, match="not available"):
            measure_verified_website_mobile_performance(
                FakeSession(run),
                request,
                company(request),
                selection,
                uuid.uuid4(),
                StubProvider(measurement()),
            )

        request.evidence_gate_state = EvidenceGateState.NEEDS_REVIEW
        with pytest.raises(WebsiteAuditError, match="Accepted evidence"):
            audit_research_website(FakeSession(run), request, company(request), selection)
