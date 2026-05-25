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


def make_auth_header(user_id: str, email: str) -> dict:
    secret = "test-secret"
    os.environ["SUPABASE_JWT_SECRET"] = secret

    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "email": email,
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
async def test_referral_flow_awards_minutes(test_db):
    owner_header = make_auth_header("user-123", "owner@example.com")
    friend_header = make_auth_header("user-456", "friend@example.com")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        create_res = await ac.post("/api/v1/referrals/code", headers=owner_header)
        assert create_res.status_code == 201
        create_payload = create_res.json()
        assert create_payload["code"]

        get_res = await ac.get("/api/v1/referrals/code", headers=owner_header)
        assert get_res.status_code == 200
        assert get_res.json()["code"] == create_payload["code"]

        redeem_res = await ac.post(
            "/api/v1/referrals/redeem",
            json={"code": create_payload["code"]},
            headers=friend_header,
        )
        assert redeem_res.status_code == 200
        redeem_payload = redeem_res.json()
        assert redeem_payload["referrer_bonus"] == 60
        assert redeem_payload["referred_bonus"] == 60

        owner_credits = await ac.get("/api/v1/referrals/credits", headers=owner_header)
        assert owner_credits.status_code == 200
        assert owner_credits.json()["bonus_minutes"] == 60

        friend_credits = await ac.get("/api/v1/referrals/credits", headers=friend_header)
        assert friend_credits.status_code == 200
        assert friend_credits.json()["bonus_minutes"] == 60
