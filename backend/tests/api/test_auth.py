import uuid

from fastapi.testclient import TestClient

from app.main import app


class TestAuthentication:
    def test_missing_token_rejected(self):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/me")
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "unauthorized"

    def test_garbage_token_rejected(self):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/me", headers={"Authorization": "Bearer not-a-real-token"}
        )
        assert resp.status_code == 401

    def test_malformed_header_rejected(self):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/me", headers={"Authorization": "Basic abc"})
        assert resp.status_code in {401, 403}

    def test_error_envelope_has_request_id(self):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/me")
        body = resp.json()["error"]
        assert body["request_id"] == resp.headers["X-Request-ID"]

    def test_health_is_public(self):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/health")
        assert resp.status_code == 200
