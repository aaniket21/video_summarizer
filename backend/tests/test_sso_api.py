import base64
import hashlib
import hmac
import json
import os
import time

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from backend.app.main import app
from backend.app.db.session import Base, get_db

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def test_db():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def override_get_db():
        async with Session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    yield Session
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.fixture
def auth_header():
    secret = "test-secret"
    os.environ["SUPABASE_JWT_SECRET"] = secret

    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": "user-123",
        "email": "owner@example.com",
        "role": "authenticated",
        "exp": int(time.time()) + 3600,
    }

    def b64url(data: dict) -> str:
        raw = json.dumps(data).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").strip("=")

    h_b64 = b64url(header)
    p_b64 = b64url(payload)

    signing_input = f"{h_b64}.{p_b64}".encode("ascii")
    sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).decode("ascii").strip("=")

    token = f"{h_b64}.{p_b64}.{sig_b64}"
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_team_sso_roundtrip(test_db, auth_header):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        team_res = await ac.post(
            "/api/v1/teams",
            json={"name": "Acme", "seat_count": 5},
            headers=auth_header,
        )

        assert team_res.status_code == 201
        team_id = team_res.json()["id"]

        update_res = await ac.put(
            f"/api/v1/teams/{team_id}/sso",
            json={
                "provider": "google",
                "domain": "acme.edu",
                "client_id": "client-123",
                "is_enabled": True,
            },
            headers=auth_header,
        )

        assert update_res.status_code == 200
        payload = update_res.json()
        assert payload["provider"] == "google"
        assert payload["domain"] == "acme.edu"
        assert payload["is_enabled"] is True

        get_res = await ac.get(
            f"/api/v1/teams/{team_id}/sso",
            headers=auth_header,
        )

        assert get_res.status_code == 200
        get_payload = get_res.json()
        assert get_payload["provider"] == "google"
        assert get_payload["domain"] == "acme.edu"
        assert get_payload["client_id"] == "client-123"
        assert get_payload["is_enabled"] is True
