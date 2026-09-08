import uuid
from datetime import UTC, datetime

import pytest

from app.models.company import Company
from app.models.research_request import ResearchStatus
from app.models.user import User
from app.schemas.opportunity_models import EvidenceSource, IdentityState
from app.schemas.research_request import KnownProspectResearchRequest
from app.services.company_resolution import ResolvedCompany
from app.services.research_requests import (
    KnownProspectResolutionError,
    confirm_known_prospect,
)


NOW = datetime(2026, 9, 8, tzinfo=UTC)


class FakeSession:
    def __init__(self, scalar_results=None):
        self.scalar_results = list(scalar_results or [])
        self.added = []
        self.committed = False
        self.rolled_back = False

    def scalar(self, statement):
        return self.scalar_results.pop(0)

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.committed = True

    def refresh(self, value):
        if value.created_at is None:
            value.created_at = NOW
        if value.updated_at is None:
            value.updated_at = NOW

    def rollback(self):
        self.rolled_back = True


def request() -> KnownProspectResearchRequest:
    return KnownProspectResearchRequest(
        business_name="Glow Salon",
        goal="Decide whether this salon is worth pitching for a booking website.",
        offering="Website redesign and booking setup",
        desired_outcome="Decide whether to research this prospect further.",
        location="Lahore",
    )


def resolution(state=IdentityState.VERIFIED) -> ResolvedCompany:
    return ResolvedCompany(
        company_name="Glow Salon",
        location="Lahore",
        website="https://glowsalon.com",
        identity_state=state,
        source=EvidenceSource(
            provider="tavily",
            source_url="https://glowsalon.com",
            retrieved_at=NOW,
        ),
        reason="A test identity decision.",
    )


class TestKnownProspectConfirmation:
    def test_creates_a_pending_request_with_goal_and_identity_snapshot(self):
        db = FakeSession(scalar_results=[None, None])
        user = User(id=uuid.uuid4(), email="owner@example.com")

        research_request = confirm_known_prospect(db, user, request(), resolution())

        assert db.committed is True
        assert research_request.status is ResearchStatus.PENDING
        assert research_request.started_at is None
        assert research_request.objective["goal"] == request().goal
        assert research_request.objective["desired_outcome"] == request().desired_outcome
        assert research_request.objective["resolved_target"]["identity_state"] == "verified"
        assert len(db.added) == 2

    def test_reuses_an_owned_company_with_the_same_verified_website(self):
        company = Company(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            name="Glow Salon",
            website="https://glowsalon.com",
            identity_key="website:glowsalon.com",
        )
        db = FakeSession(scalar_results=[company, None])
        user = User(id=company.user_id, email="owner@example.com")

        research_request = confirm_known_prospect(db, user, request(), resolution())

        assert research_request.company_id == company.id
        assert db.added == [research_request]

    def test_reuses_a_campaign_company_with_the_same_verified_website(self):
        company = Company(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            name="Glow Salon",
            website="https://glowsalon.com",
            identity_key="open_places:place-123",
        )
        db = FakeSession(scalar_results=[company, None])
        user = User(id=company.user_id, email="owner@example.com")

        research_request = confirm_known_prospect(db, user, request(), resolution())

        assert research_request.company_id == company.id
        assert db.added == [research_request]

    def test_rejects_a_duplicate_pending_request(self):
        company = Company(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            name="Glow Salon",
            website="https://glowsalon.com",
            identity_key="website:glowsalon.com",
        )
        db = FakeSession(scalar_results=[company, uuid.uuid4()])
        user = User(id=company.user_id, email="owner@example.com")

        with pytest.raises(KnownProspectResolutionError, match="already has a pending"):
            confirm_known_prospect(db, user, request(), resolution())

        assert db.added == []

    def test_rejects_an_unverified_identity_before_any_database_write(self):
        db = FakeSession()
        user = User(id=uuid.uuid4(), email="owner@example.com")

        with pytest.raises(KnownProspectResolutionError, match="verified business identity"):
            confirm_known_prospect(
                db,
                user,
                request(),
                resolution(IdentityState.NEEDS_REVIEW),
            )

        assert db.added == []
