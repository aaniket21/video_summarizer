import pytest
import pytest_asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.db.session import Base
from app.db.models import JobModel, JobStatus
from app.db.repository import SQLAlchemyJobRepository
from uuid import UUID

# Use a test database
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture
async def db_session():
    # Use a specific set of echo=False for cleaner test output
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as session:
        yield session
    
    await engine.dispose()

@pytest.mark.asyncio
async def test_job_repository_create(db_session):
    repo = SQLAlchemyJobRepository(db_session)
    job = await repo.create(user_id="user123", video_url="https://youtube.com/v1")
    
    assert job.id is not None
    assert isinstance(job.id, UUID)
    assert job.user_id == "user123"
    assert job.status == JobStatus.PENDING

@pytest.mark.asyncio
async def test_job_repository_get_by_id(db_session):
    repo = SQLAlchemyJobRepository(db_session)
    created_job = await repo.create(user_id="user123", video_url="https://youtube.com/v1")
    
    fetched_job = await repo.get_by_id(created_job.id)
    assert fetched_job is not None
    assert fetched_job.id == created_job.id
    assert fetched_job.video_url == "https://youtube.com/v1"

@pytest.mark.asyncio
async def test_job_repository_list_by_user(db_session):
    repo = SQLAlchemyJobRepository(db_session)
    await repo.create(user_id="user1", video_url="v1")
    await repo.create(user_id="user1", video_url="v2")
    await repo.create(user_id="user2", video_url="v3")
    
    user1_jobs = await repo.list_by_user("user1")
    assert len(user1_jobs) == 2
    
    user2_jobs = await repo.list_by_user("user2")
    assert len(user2_jobs) == 1

@pytest.mark.asyncio
async def test_job_repository_update_status(db_session):
    repo = SQLAlchemyJobRepository(db_session)
    job = await repo.create(user_id="user1", video_url="v1")
    
    updated = await repo.update_status(job.id, JobStatus.PROCESSING, progress=0.5)
    assert updated.status == JobStatus.PROCESSING
    assert updated.progress == 0.5

@pytest.mark.asyncio
async def test_job_repository_update_result(db_session):
    repo = SQLAlchemyJobRepository(db_session)
    job = await repo.create(user_id="user1", video_url="v1")
    
    updated = await repo.update_result(
        job.id, 
        transcript="Hello world", 
        summary="Greetings", 
        metadata={"duration": 100}
    )
    assert updated.status == JobStatus.COMPLETED
    assert updated.transcript == "Hello world"
    assert updated.summary == "Greetings"
    assert updated.metadata_json == {"duration": 100}

@pytest.mark.asyncio
async def test_job_repository_delete(db_session):
    repo = SQLAlchemyJobRepository(db_session)
    job = await repo.create(user_id="user1", video_url="v1")
    
    deleted = await repo.delete(job.id)
    assert deleted is True
    
    fetched = await repo.get_by_id(job.id)
    assert fetched is None
