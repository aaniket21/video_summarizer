import pytest
import pytest_asyncio
import os
import json
import hmac
import hashlib
import time
from uuid import UUID
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.db.session import Base, get_db
from backend.app.db.models import JobStatus
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Use a test database
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
    # Mocking HS256 JWT for Supabase
    secret = "test-secret"
    os.environ["SUPABASE_JWT_SECRET"] = secret
    
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": "user-123",
        "role": "authenticated",
        "exp": int(time.time()) + 3600
    }
    
    import base64
    def b64url(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().strip("=")

    h_b64 = b64url(header)
    p_b64 = b64url(payload)
    
    signing_input = f"{h_b64}.{p_b64}".encode()
    sig = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).decode().strip("=")
    
    token = f"{h_b64}.{p_b64}.{sig_b64}"
    return {"Authorization": f"Bearer {token}"}

@pytest.mark.asyncio
async def test_api_create_job(test_db, auth_header):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/jobs", 
            json={"video_url": "https://youtube.com/watch?v=123"},
            headers=auth_header
        )
    
    assert response.status_code == 201
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "pending"

@pytest.mark.asyncio
async def test_api_get_job(test_db, auth_header):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Create first
        create_res = await ac.post(
            "/api/v1/jobs", 
            json={"video_url": "https://youtube.com/watch?v=123"},
            headers=auth_header
        )
        job_id = create_res.json()["job_id"]
        
        # Get
        get_res = await ac.get(f"/api/v1/jobs/{job_id}", headers=auth_header)
        assert get_res.status_code == 200
        assert get_res.json()["id"] == job_id

@pytest.mark.asyncio
async def test_api_list_jobs(test_db, auth_header):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post("/api/v1/jobs", json={"video_url": "v1"}, headers=auth_header)
        await ac.post("/api/v1/jobs", json={"video_url": "v2"}, headers=auth_header)
        
        res = await ac.get("/api/v1/jobs", headers=auth_header)
        assert res.status_code == 200
        assert len(res.json()["items"]) == 2


@pytest.mark.asyncio
async def test_api_list_jobs_returns_total_count(test_db, auth_header):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post("/api/v1/jobs", json={"video_url": "v1"}, headers=auth_header)
        await ac.post("/api/v1/jobs", json={"video_url": "v2"}, headers=auth_header)
        await ac.post("/api/v1/jobs", json={"video_url": "v3"}, headers=auth_header)

        res = await ac.get("/api/v1/jobs", params={"limit": 2}, headers=auth_header)
        assert res.status_code == 200
        payload = res.json()
        assert len(payload["items"]) == 2
        assert payload["total"] == 3

@pytest.mark.asyncio
async def test_api_delete_job(test_db, auth_header):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        create_res = await ac.post("/api/v1/jobs", json={"video_url": "v1"}, headers=auth_header)
        job_id = create_res.json()["job_id"]
        
        res = await ac.delete(f"/api/v1/jobs/{job_id}", headers=auth_header)
        assert res.status_code == 200
        assert res.json()["status"] == "cancelled"

@pytest.mark.asyncio
async def test_api_unauthorized(test_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/jobs")
        assert res.status_code == 401
