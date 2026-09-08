import uuid
from datetime import UTC, datetime

import pytest

from app.integrations.pagespeed import MobilePerformanceMeasurement, PageSpeedProviderError
from app.models.company import Company
from app.models.research_evidence import ResearchEvidence
from app.models.research_request import ResearchRequest
from app.models.research_request import ResearchStatus
from app.schemas.evidence_gate import EvidenceGateState
from app.schemas.website_audit import WebsiteAuditState
from app.services.website_audit import WebsiteAuditError, audit_research_website


NOW = datetime(2026, 9, 8, tzinfo=UTC)


class FakeSession:
    def __init__(self, scalar_results):
        self.scalar_results = list(scalar_results)
        self.added = []
        self.committed = False

    def scalar(self, statement):
        return self.scalar_results.pop(0)

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


def research_request(verified_website=True):
    request = ResearchRequest(
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
    return request


def company(request):
    return Company(id=request.company_id, user_id=request.user_id, name="Glow Salon")


class TestWebsiteAudit:
    def test_saves_observed_mobile_measurement_with_provenance(self):
        request = research_request()
        db = FakeSession([None, request])
        provider = StubProvider(
            MobilePerformanceMeasurement(
                final_url="https://glow.example/",
                score=43.0,
                retrieved_at=NOW,
            )
        )

        result = audit_research_website(db, request, company(request), None, provider)

        assert result.website_audit_state is WebsiteAuditState.COMPLETED
        assert db.committed is True
        assert provider.urls == ["https://glow.example/"]
        evidence = db.added[0]
        assert isinstance(evidence, ResearchEvidence)
        assert evidence.signal_type == "website_mobile_performance_measured"
        assert evidence.evidence_type == "observed"
        assert evidence.numeric_value == 43.0
        assert evidence.source_provider == "pagespeed_insights"
        assert evidence.source_identity_key == "pagespeed:https://glow.example/"
        assert evidence.source_url == "https://glow.example/"
        assert "43/100" in evidence.supporting_value

    def test_does_not_treat_missing_verified_website_as_poor_performance(self):
        request = research_request(verified_website=False)
        db = FakeSession([request])

        result = audit_research_website(db, request, company(request), None)

        assert result.website_audit_state is WebsiteAuditState.UNAVAILABLE
        assert result.website_audit_reason == "No verified official website is available to audit."
        assert db.added == []

    def test_provider_failure_is_unavailable_not_negative_evidence(self):
        request = research_request()
        db = FakeSession([request])
        provider = StubProvider(error=PageSpeedProviderError("PageSpeed quota or rate limit was reached."))

        result = audit_research_website(db, request, company(request), None, provider)

        assert result.website_audit_state is WebsiteAuditState.UNAVAILABLE
        assert "quota or rate limit" in result.website_audit_reason
        assert db.added == []

    def test_requires_the_evidence_gate_before_audit(self):
        request = research_request()
        request.evidence_gate_state = EvidenceGateState.NEEDS_REVIEW

        with pytest.raises(WebsiteAuditError, match="Accepted evidence"):
            audit_research_website(FakeSession([]), request, company(request), None)
