import base64
import hashlib
import hmac
import json
import time

from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def base64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def make_hs256_jwt(payload: dict, secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = base64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = base64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    signature_b64 = base64url_encode(signature)
    return f"{header_b64}.{payload_b64}.{signature_b64}"


def test_profile_missing_jwt_returns_401(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "secret")
    response = client.get("/api/profile")
    assert response.status_code == 401
    assert response.json() == {"error": "Authentication required"}


def test_profile_invalid_jwt_returns_401(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "secret")
    bad_token = make_hs256_jwt({"sub": "user", "exp": int(time.time()) + 3600}, "wrong-secret")
    response = client.get(
        "/api/profile",
        headers={"Authorization": f"Bearer {bad_token}"},
    )
    assert response.status_code == 401
    assert response.json() == {"error": "Invalid or expired token"}


def test_admin_requires_permission_returns_403(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "secret")
    token = make_hs256_jwt({"sub": "user", "role": "user", "exp": int(time.time()) + 3600}, "secret")
    response = client.get(
        "/api/admin",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert response.json() == {"error": "Insufficient permissions"}
