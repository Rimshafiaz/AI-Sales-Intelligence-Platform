import uuid

import pytest

from app.integrations.search_provider import CollectedSource
from app.models.research_request import ResearchRequest
from app.repositories.research_sources import create_research_sources
from app.schemas.sales_intelligence_report import SalesIntelligenceReport
from tests.conftest import make_valid_report_data


def _fake_crew_result(score: int = 64):
    return SalesIntelligenceReport.model_validate(make_valid_report_data(score=score))


@pytest.fixture
def no_background_runner(monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.research_requests.run_research", lambda request_id: None
    )


@pytest.fixture
def mocked_crew(monkeypatch):
    calls = []

    def fake_crew(company_name, evidence_context, guidance=None):
        calls.append({"company": company_name, "guidance": guidance})
        return _fake_crew_result()

    monkeypatch.setattr(
        "app.services.report_generation.run_sales_intelligence_crew", fake_crew
    )
    return calls


@pytest.fixture
def owned_pending_request(test_user, owned_company, db):
    request = ResearchRequest(
        company_id=owned_company.id,
        user_id=test_user.id,
        status="pending",
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


class TestResearchRequestLifecycle:
    def test_create_request_returns_pending(
        self, auth_client, owned_company, no_background_runner
    ):
        resp = auth_client.post(f"/companies/{owned_company.id}/research-requests")
        assert resp.status_code == 202
        assert resp.json()["status"] == "pending"

    def test_request_for_unknown_company_404(self, auth_client, no_background_runner):
        resp = auth_client.post(f"/companies/{uuid.uuid4()}/research-requests")
        assert resp.status_code == 404

    def test_owner_reads_status_foreign_scoping_holds(
        self, auth_client, owned_pending_request
    ):
        assert auth_client.get(
            f"/research-requests/{owned_pending_request.id}"
        ).status_code == 200
        assert auth_client.get(
            f"/research-requests/{uuid.uuid4()}"
        ).status_code == 404


class TestReportGeneration:
    def test_generate_on_pending_request_409(
        self, auth_client, owned_pending_request
    ):
        resp = auth_client.post(
            f"/research-requests/{owned_pending_request.id}/reports"
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "conflict"

    def test_generate_on_completed_request_saves_report(
        self, auth_client, owned_completed_request, mocked_crew, db
    ):
        create_research_sources(
            db=db,
            research_request_id=owned_completed_request.id,
            sources=[
                CollectedSource(
                    url="https://example.com/about",
                    title="About",
                    excerpt="Example Corp makes widgets.",
                )
            ],
        )
        resp = auth_client.post(
            f"/research-requests/{owned_completed_request.id}/reports"
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["review_status"] == "draft"
        assert body["opportunity_score"] == 64
        assert body["contact_recommendation"] == "consider"
        assert len(mocked_crew) == 1
        assert mocked_crew[0]["company"].startswith("TestCorp-")

    def test_duplicate_generation_409(self, auth_client, owned_report, mocked_crew):
        resp = auth_client.post(
            f"/research-requests/{owned_report.research_request_id}/reports"
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "conflict"

    def test_generate_without_sources_fails_safe(
        self, auth_client, owned_completed_request, mocked_crew
    ):
        resp = auth_client.post(
            f"/research-requests/{owned_completed_request.id}/reports"
        )
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "service_unavailable"
        assert mocked_crew == []


class TestReportReview:
    def test_detail_contains_report_and_sources(
        self, auth_client, owned_report, db
    ):
        create_research_sources(
            db=db,
            research_request_id=owned_report.research_request_id,
            sources=[
                CollectedSource(
                    url="https://example.com/news",
                    title="News",
                    excerpt="Example Corp expands.",
                )
            ],
        )
        resp = auth_client.get(f"/reports/{owned_report.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["report"]["opportunity_score"] == 72
        assert len(body["sources"]) >= 1

    def test_approve_sets_status_and_is_idempotent(
        self, auth_client, owned_report
    ):
        first = auth_client.post(f"/reports/{owned_report.id}/approve")
        assert first.status_code == 200
        assert first.json()["review_status"] == "approved"
        stamped_at = first.json()["approved_at"]
        assert stamped_at is not None

        second = auth_client.post(f"/reports/{owned_report.id}/approve")
        assert second.status_code == 200
        assert second.json()["approved_at"] == stamped_at

    def test_patch_edits_allowed_fields_and_reverts_to_draft(
        self, auth_client, owned_report
    ):
        auth_client.post(f"/reports/{owned_report.id}/approve")
        resp = auth_client.patch(
            f"/reports/{owned_report.id}",
            json={"cold_email": "Updated outreach text."},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["review_status"] == "draft"
        assert body["approved_at"] is None
        assert (
            body["report_data"]["personalized_outreach"]["cold_email"]
            == "Updated outreach text."
        )

    def test_patch_cannot_touch_score(self, auth_client, owned_report):
        resp = auth_client.patch(
            f"/reports/{owned_report.id}", json={"opportunity_score": 99}
        )
        assert resp.status_code == 422

    def test_patch_noop_preserves_status(self, auth_client, owned_report):
        auth_client.post(f"/reports/{owned_report.id}/approve")
        resp = auth_client.patch(
            f"/reports/{owned_report.id}",
            json={"review_note": "A fresh review note."},
        )
        assert resp.status_code == 200
        assert resp.json()["review_status"] == "draft"

    def test_regenerate_creates_second_report(
        self, auth_client, owned_report, mocked_crew
    ):
        resp = auth_client.post(
            f"/reports/{owned_report.id}/regenerate",
            json={"instruction": "focus the outreach on hiring growth"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["id"] != str(owned_report.id)
        assert body["review_status"] == "draft"
        assert mocked_crew[0]["guidance"] == "focus the outreach on hiring growth"

    def test_regenerate_with_blank_instruction_passes_none(
        self, auth_client, owned_report, mocked_crew
    ):
        resp = auth_client.post(
            f"/reports/{owned_report.id}/regenerate", json={"instruction": "  "}
        )
        assert resp.status_code == 201
        assert mocked_crew[0]["guidance"] is None

    def test_report_ownership_404(self, foreign_client, owned_report):
        assert (
            foreign_client.get(f"/reports/{owned_report.id}").status_code == 404
        )
        assert (
            foreign_client.post(
                f"/reports/{owned_report.id}/approve"
            ).status_code
            == 404
        )
        assert (
            foreign_client.patch(
                f"/reports/{owned_report.id}", json={"cold_email": "hi"}
            ).status_code
            == 404
        )
        assert (
            foreign_client.post(
                f"/reports/{owned_report.id}/regenerate"
            ).status_code
            == 404
        )
