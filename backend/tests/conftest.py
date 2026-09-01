import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.api.dependencies.current_user import get_current_user
from app.db.session import SessionLocal
from app.integrations.search_provider import CollectedSource
from app.main import app
from app.models.company import Company
from app.models.research_report import ResearchReport
from app.models.research_request import ResearchRequest
from app.models.research_source import ResearchSource
from app.models.user import User
from app.repositories.research_sources import create_research_sources


def make_valid_report_data(score: int = 72) -> dict:
    citation = {"source_url": "https://example.com", "supporting_excerpt": "evidence"}
    finding = {
        "statement": "Example Corp sells widgets.",
        "citations": [citation],
        "is_inference": False,
        "rationale": "Stated on the official site.",
    }
    inference_finding = {
        "statement": "Growth suggests budget availability.",
        "citations": [citation],
        "is_inference": True,
        "rationale": "Funding signals imply capacity.",
    }
    return {
        "executive_summary": finding,
        "company_profile": {"company_summary": finding},
        "technologies": [],
        "business_signals": [],
        "opportunity_assessment": {
            "score": score,
            "reasons": [inference_finding],
        },
        "contact_recommendation": {
            "recommendation": "consider",
            "rationale": inference_finding,
        },
        "confidence": {"score": 55, "rationale": "Evidence is limited but consistent."},
        "pain_points": [],
        "strategy": {
            "recommended_strategy": inference_finding,
            "recommended_sales_angle": inference_finding,
            "suggested_value_proposition": inference_finding,
        },
        "suggested_decision_makers": [],
        "personalized_outreach": {
            "cold_email": "Hi, quick note about widget integration.",
            "linkedin_message": "Hi! Loved your latest launch - connecting to share an idea.",
            "personalization_rationale": inference_finding,
        },
        "caveats": ["Public information only."],
    }


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_user():
    user = User(id=uuid.uuid4(), email=f"test-{uuid.uuid4().hex}@example.com")
    session = SessionLocal()
    try:
        session.add(user)
        session.commit()
        yield user
    finally:
        _delete_user_data(user.id)
        session.close()


def _delete_user_data(user_id: uuid.UUID) -> None:
    session = SessionLocal()
    try:
        request_ids = select(ResearchRequest.id).where(
            ResearchRequest.user_id == user_id
        )
        session.execute(
            delete(ResearchSource).where(
                ResearchSource.research_request_id.in_(request_ids)
            )
        )
        session.execute(
            delete(ResearchReport).where(ResearchReport.user_id == user_id)
        )
        session.execute(
            delete(ResearchRequest).where(ResearchRequest.user_id == user_id)
        )
        session.execute(delete(Company).where(Company.user_id == user_id))
        session.execute(delete(User).where(User.id == user_id))
        session.commit()
    finally:
        session.close()


@pytest.fixture
def auth_client(test_user):
    app.dependency_overrides[get_current_user] = lambda: test_user
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def foreign_client():
    foreign_user = User(id=uuid.uuid4(), email=f"foreign-{uuid.uuid4().hex}@example.com")
    app.dependency_overrides[get_current_user] = lambda: foreign_user
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def owned_company(test_user, db):
    company = Company(
        user_id=test_user.id,
        name=f"TestCorp-{uuid.uuid4().hex[:8]}",
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


@pytest.fixture
def owned_completed_request(test_user, owned_company, db):
    request = ResearchRequest(
        company_id=owned_company.id,
        user_id=test_user.id,
        status="completed",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


@pytest.fixture
def owned_report(test_user, owned_company, owned_completed_request, db):
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
    report = ResearchReport(
        research_request_id=owned_completed_request.id,
        company_id=owned_company.id,
        user_id=test_user.id,
        report_data=make_valid_report_data(score=72),
        opportunity_score=72,
        contact_recommendation="consider",
        generated_at=datetime.now(timezone.utc),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
