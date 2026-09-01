import uuid
from datetime import datetime, timezone

import pytest

from app.repositories.research_reports import create_research_report
from tests.conftest import make_valid_report_data


@pytest.fixture
def history_reports(test_user, owned_completed_request, owned_company, db):
    first = create_research_report(
        db=db,
        research_request_id=owned_completed_request.id,
        company_id=owned_company.id,
        user_id=test_user.id,
        report_data=make_valid_report_data(score=40),
        opportunity_score=40,
        contact_recommendation="do_not_prioritize",
        generated_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )
    second = create_research_report(
        db=db,
        research_request_id=owned_completed_request.id,
        company_id=owned_company.id,
        user_id=test_user.id,
        report_data=make_valid_report_data(score=90),
        opportunity_score=90,
        contact_recommendation="prioritize",
        generated_at=datetime(2026, 8, 2, tzinfo=timezone.utc),
    )
    return [first, second]


class TestReportHistory:
    def test_list_returns_newest_first_without_payload(
        self, auth_client, history_reports
    ):
        resp = auth_client.get("/reports")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert body["items"][0]["generated_at"] >= body["items"][1]["generated_at"]
        assert all("report_data" not in item for item in body["items"])

    def test_pagination_bounds(self, auth_client, history_reports):
        page_one = auth_client.get("/reports", params={"page": 1, "page_size": 1}).json()
        page_two = auth_client.get("/reports", params={"page": 2, "page_size": 1}).json()
        assert len(page_one["items"]) == 1 and page_one["total"] == 2
        assert len(page_two["items"]) == 1 and page_two["total"] == 2
        assert page_one["items"][0]["id"] != page_two["items"][0]["id"]

    def test_status_filter(self, auth_client, history_reports):
        resp = auth_client.get("/reports", params={"report_status": "draft"})
        assert resp.json()["total"] == 2

    def test_score_filter(self, auth_client, history_reports):
        resp = auth_client.get("/reports", params={"min_score": 85})
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["opportunity_score"] == 90

    def test_company_partial_filter(self, auth_client, history_reports):
        resp = auth_client.get("/reports", params={"company": "TestCorp"})
        assert resp.json()["total"] == 2
        resp = auth_client.get("/reports", params={"company": "no-such-company"})
        assert resp.json()["total"] == 0

    def test_inverted_ranges_422(self, auth_client, history_reports):
        resp = auth_client.get(
            "/reports", params={"from_date": "2026-08-02", "to_date": "2026-08-01"}
        )
        assert resp.status_code == 422
        resp = auth_client.get("/reports", params={"min_score": 90, "max_score": 40})
        assert resp.status_code == 422

    def test_foreign_history_is_empty(self, foreign_client, history_reports):
        resp = foreign_client.get("/reports")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
        assert resp.json()["items"] == []


class TestDashboard:
    def test_summary_matches_seeded_data(self, auth_client, history_reports):
        resp = auth_client.get("/dashboard/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["reports_generated"] == 2
        assert body["companies_researched"] == 1
        assert body["average_opportunity_score"] == 65.0

    def test_zero_state_for_new_user(self, foreign_client):
        resp = foreign_client.get("/dashboard/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["reports_generated"] == 0
        assert body["companies_researched"] == 0
        assert body["most_researched_industries"] == []
        assert body["average_opportunity_score"] is None
        assert body["recent_activity"] == []

    def test_activity_feed_lists_events(self, auth_client, history_reports):
        resp = auth_client.get("/dashboard/summary")
        events = resp.json()["recent_activity"]
        event_types = {e["event_type"] for e in events}
        assert "report_generated" in event_types
        assert "research_requested" in event_types
        timestamps = [e["occurred_at"] for e in events]
        assert timestamps == sorted(timestamps, reverse=True)
        assert len(events) <= 10
