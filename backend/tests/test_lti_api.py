import os

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_lti_config_returns_expected_payload(monkeypatch):
    monkeypatch.setenv("LTI_ISSUER", "https://canvas.instructure.com")
    monkeypatch.setenv("LTI_CLIENT_ID", "client-123")
    monkeypatch.setenv("LTI_AUTH_LOGIN_URL", "https://lms.test/oidc/login")
    monkeypatch.setenv("LTI_REDIRECT_URL", "https://api.test/api/v1/lti/launch")
    monkeypatch.setenv("LTI_JWKS_URL", "https://api.test/api/v1/lti/jwks")

    response = client.get("/api/v1/lti/config")
    assert response.status_code == 200
    payload = response.json()
    assert payload["issuer"] == "https://canvas.instructure.com"
    assert payload["client_id"] == "client-123"
    assert payload["auth_login_url"] == "https://lms.test/oidc/login"
    assert payload["redirect_url"] == "https://api.test/api/v1/lti/launch"
    assert payload["jwks_url"] == "https://api.test/api/v1/lti/jwks"


def test_lti_launch_requires_token():
    response = client.post("/api/v1/lti/launch", json={})
    assert response.status_code == 400
    assert response.json() == {"error": "Missing id_token"}
