import uuid

import pytest
from sqlalchemy import select

from app.integrations.search_provider import CollectedSource
from app.models.research_report import ResearchReport
from app.models.research_request import ResearchRequest
from app.repositories.research_sources import create_research_sources
from app.schemas.evidence_gate import EvidenceGateState, SourceAdmissionState


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
    def test_generic_unscoped_creation_route_is_removed(
        self, auth_client, owned_company
    ):
        resp = auth_client.post(f"/companies/{owned_company.id}/research-requests")
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

    def test_failed_modern_request_retries_with_original_scope(
        self, auth_client, test_user, owned_company, db, monkeypatch
    ):
        calls = []
        monkeypatch.setattr(
            "app.api.routes.research_requests.run_research",
            lambda request_id: calls.append(request_id),
        )
        original = ResearchRequest(
            company_id=owned_company.id,
            user_id=test_user.id,
            status="failed",
            error_message="Provider failed.",
            objective={"mode": "known_prospect", "offering": "Website development"},
            opportunity_model_selection={
                "model_ids": ["web_conversion.no_verified_web_presence"],
                "confirmed_by_user": True,
            },
            specialist_outputs={"website": {"stale": True}},
            website_check_states={"mobile_performance": {"state": "unavailable"}},
        )
        db.add(original)
        db.commit()
        db.refresh(original)

        response = auth_client.post(f"/research-requests/{original.id}/retry")

        assert response.status_code == 201
        body = response.json()
        assert body["id"] != str(original.id)
        assert body["objective"] == original.objective
        assert body["opportunity_model_selection"] == original.opportunity_model_selection
        assert body["status"] == "pending"
        assert body["error_message"] is None
        assert body["specialist_outputs"] is None
        assert body["website_check_states"] is None
        assert body["social_check_states"] is None
        assert calls == [uuid.UUID(body["id"])]

    @pytest.mark.parametrize("request_status", ["pending", "running", "completed"])
    def test_only_failed_requests_can_be_retried(
        self, auth_client, test_user, owned_company, db, request_status
    ):
        request = ResearchRequest(
            company_id=owned_company.id,
            user_id=test_user.id,
            status=request_status,
            objective={"mode": "known_prospect"},
            opportunity_model_selection={
                "model_ids": ["web_conversion.mobile_performance"],
                "confirmed_by_user": True,
            },
        )
        db.add(request)
        db.commit()
        response = auth_client.post(f"/research-requests/{request.id}/retry")
        assert response.status_code == 409


class TestReportGeneration:
    def test_generate_on_pending_request_409(
        self, auth_client, owned_pending_request
    ):
        resp = auth_client.post(
            f"/research-requests/{owned_pending_request.id}/reports"
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "conflict"

    def test_unscoped_completed_request_cannot_generate_legacy_report(
        self,
        auth_client,
        owned_completed_request,
        db,
    ):
        sources = create_research_sources(
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
        for source in sources:
            source.admission_state = SourceAdmissionState.ACCEPTED
        db.commit()
        resp = auth_client.post(
            f"/research-requests/{owned_completed_request.id}/reports"
        )
        assert resp.status_code == 409

        saved = db.scalars(
            select(ResearchReport).where(
                ResearchReport.research_request_id == owned_completed_request.id
            )
        ).all()
        assert saved == []

    def test_duplicate_generation_409(self, auth_client, owned_report):
        resp = auth_client.post(
            f"/research-requests/{owned_report.research_request_id}/reports"
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "conflict"

    def test_generate_is_blocked_until_the_evidence_gate_passes(
        self, auth_client, owned_completed_request, db
    ):
        owned_completed_request.evidence_gate_state = EvidenceGateState.NEEDS_REVIEW
        db.commit()

        resp = auth_client.post(
            f"/research-requests/{owned_completed_request.id}/reports"
        )

        assert resp.status_code == 409


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

    def test_legacy_report_regeneration_is_rejected(
        self, auth_client, owned_report, db
    ):
        resp = auth_client.post(
            f"/reports/{owned_report.id}/regenerate",
            json={"instruction": "focus the outreach on hiring growth"},
        )
        assert resp.status_code == 409

        reports = db.scalars(
            select(ResearchReport).where(
                ResearchReport.research_request_id
                == owned_report.research_request_id
            )
        ).all()
        assert reports == [owned_report]

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
