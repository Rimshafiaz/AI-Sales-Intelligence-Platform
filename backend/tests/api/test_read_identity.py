import uuid

import pytest
from fastapi.testclient import TestClient
from jwt import (
    ExpiredSignatureError,
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidSignatureError,
)

from app.api.dependencies.auth import get_verified_claims
from app.api.dependencies.current_user import get_authenticated_identity, get_current_user
from app.main import app
from app.models.campaign import Campaign
from app.models.user import User


def test_verified_identity_requires_no_database_session():
    user_id = uuid.uuid4()

    identity = get_authenticated_identity(
        {"sub": str(user_id), "email": "reader@example.com"}
    )

    assert identity.id == user_id
    assert identity.email == "reader@example.com"


def test_malformed_verified_sub_is_rejected():
    app.dependency_overrides[get_verified_claims] = lambda: {
        "sub": "not-a-uuid",
        "email": "reader@example.com",
    }
    try:
        response = TestClient(app, raise_server_exceptions=False).get(
            "/campaigns", headers={"Authorization": "Bearer verified-by-override"}
        )
    finally:
        app.dependency_overrides.pop(get_verified_claims, None)

    assert response.status_code == 401


@pytest.mark.parametrize(
    "verification_error",
    [
        InvalidSignatureError(),
        InvalidIssuerError(),
        InvalidAudienceError(),
        ExpiredSignatureError(),
    ],
)
def test_verified_identity_keeps_jwt_rejections(monkeypatch, verification_error):
    def reject(_token):
        raise verification_error

    monkeypatch.setattr("app.api.dependencies.auth.verify_supabase_token", reject)
    response = TestClient(app, raise_server_exceptions=False).get(
        "/campaigns", headers={"Authorization": "Bearer rejected-token"}
    )

    assert response.status_code == 401


def test_first_time_read_is_empty_and_does_not_create_user(db, test_user):
    db.add(
        Campaign(
            user_id=test_user.id,
            title="Another user's campaign",
            discovery_criteria={},
            model_selection={},
        )
    )
    db.commit()
    first_time_id = uuid.uuid4()
    app.dependency_overrides[get_verified_claims] = lambda: {
        "sub": str(first_time_id),
        "email": "first-read@example.com",
    }
    try:
        response = TestClient(app, raise_server_exceptions=False).get(
            "/campaigns", headers={"Authorization": "Bearer verified-by-override"}
        )
    finally:
        app.dependency_overrides.pop(get_verified_claims, None)

    db.expire_all()
    assert response.status_code == 200
    assert response.json() == []
    assert db.get(User, first_time_id) is None


def test_mutations_keep_database_backed_identity_dependency():
    routes = [
        nested
        for route in app.routes
        for nested in getattr(getattr(route, "original_router", None), "routes", [route])
    ]
    mutation_routes = [
        route
        for route in routes
        if getattr(route, "methods", set()) & {"POST", "PATCH", "DELETE"}
        and route.path != "/integrations/gmail/callback"
    ]

    assert mutation_routes
    for route in mutation_routes:
        dependencies = {dependency.call for dependency in route.dependant.dependencies}
        assert get_current_user in dependencies
        assert get_authenticated_identity not in dependencies
