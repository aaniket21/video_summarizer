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
    payload = {"sub": "user-123", "role": "authenticated", "exp": int(time.time()) + 3600}

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


class _DummyStripeCustomer:
    def __init__(self, customer_id: str):
        self.id = customer_id


class _DummyStripeCheckoutSession:
    def __init__(self, url: str):
        self.url = url


class _DummyStripePortalSession:
    def __init__(self, url: str):
        self.url = url


class _DummyStripe:
    api_key = ""

    class Customer:
        @staticmethod
        def create(**_kwargs):
            return _DummyStripeCustomer("cus_test_123")

    class checkout:
        class Session:
            @staticmethod
            def create(**_kwargs):
                return _DummyStripeCheckoutSession("https://stripe.test/checkout")

    class billing_portal:
        class Session:
            @staticmethod
            def create(**_kwargs):
                return _DummyStripePortalSession("https://stripe.test/portal")


@pytest.mark.asyncio
async def test_billing_checkout_requires_auth(test_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/billing/checkout", json={"plan": "student"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_billing_checkout_returns_url(test_db, auth_header, monkeypatch):
    from backend.app import main as main_module

    monkeypatch.setattr(main_module, "stripe", _DummyStripe)
    os.environ["STRIPE_SECRET_KEY"] = "sk_test"
    os.environ["STRIPE_STUDENT_PRICE_ID"] = "price_student"
    os.environ["STRIPE_SUCCESS_URL"] = "https://app.test/success"
    os.environ["STRIPE_CANCEL_URL"] = "https://app.test/cancel"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/billing/checkout", json={"plan": "student"}, headers=auth_header)

    assert res.status_code == 200
    payload = res.json()
    assert payload["url"] == "https://stripe.test/checkout"


@pytest.mark.asyncio
async def test_billing_checkout_supports_pro_plan(test_db, auth_header, monkeypatch):
    from backend.app import main as main_module

    monkeypatch.setattr(main_module, "stripe", _DummyStripe)
    os.environ["STRIPE_SECRET_KEY"] = "sk_test"
    os.environ["STRIPE_PRO_PRICE_ID"] = "price_pro"
    os.environ["STRIPE_SUCCESS_URL"] = "https://app.test/success"
    os.environ["STRIPE_CANCEL_URL"] = "https://app.test/cancel"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/billing/checkout", json={"plan": "pro"}, headers=auth_header)

    assert res.status_code == 200
    payload = res.json()
    assert payload["url"] == "https://stripe.test/checkout"


@pytest.mark.asyncio
async def test_billing_portal_returns_url(test_db, auth_header, monkeypatch):
    from backend.app import main as main_module

    monkeypatch.setattr(main_module, "stripe", _DummyStripe)
    os.environ["STRIPE_SECRET_KEY"] = "sk_test"
    os.environ["STRIPE_STUDENT_PRICE_ID"] = "price_student"
    os.environ["STRIPE_SUCCESS_URL"] = "https://app.test/success"
    os.environ["STRIPE_CANCEL_URL"] = "https://app.test/cancel"
    os.environ["STRIPE_PORTAL_RETURN_URL"] = "https://app.test/account"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post("/api/v1/billing/checkout", json={"plan": "student"}, headers=auth_header)
        res = await ac.post("/api/v1/billing/portal", headers=auth_header)

    assert res.status_code == 200
    payload = res.json()
    assert payload["url"] == "https://stripe.test/portal"
