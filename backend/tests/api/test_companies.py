import uuid


class TestCompanyOwnership:
    def test_create_company_scopes_to_current_user(self, auth_client, test_user):
        resp = auth_client.post("/companies", json={"name": "Acme Corp"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Acme Corp"
        assert body["website"] is None

    def test_blank_name_rejected(self, auth_client):
        resp = auth_client.post("/companies", json={"name": "   "})
        assert resp.status_code == 422

    def test_owner_sees_company(self, auth_client, owned_company):
        resp = auth_client.get("/companies")
        assert resp.status_code == 200
        assert any(c["id"] == str(owned_company.id) for c in resp.json())

    def test_foreign_user_gets_404_not_forbidden(self, foreign_client, owned_company):
        resp = foreign_client.get(f"/companies/{owned_company.id}")
        assert resp.status_code == 404

    def test_unknown_company_404(self, auth_client):
        resp = auth_client.get(f"/companies/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_owner_can_delete_company(self, auth_client, owned_company):
        resp = auth_client.delete(f"/companies/{owned_company.id}")
        assert resp.status_code in {200, 204}

    def test_foreign_user_cannot_delete(self, foreign_client, owned_company):
        resp = foreign_client.delete(f"/companies/{owned_company.id}")
        assert resp.status_code == 404
