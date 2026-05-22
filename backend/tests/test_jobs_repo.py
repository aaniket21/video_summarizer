import asyncio

from backend.app.db.repositories.jobs import JobRepository
from backend.app.db.session import async_session_maker, init_db


def test_job_repo_persists_across_instances():
    async def run() -> None:
        await init_db()
        async with async_session_maker() as session:
            repo = JobRepository(session)
            job = await repo.create_job(title="Persist")
            job_id = job["job_id"]

        async with async_session_maker() as session:
            repo = JobRepository(session)
            fetched = await repo.get_job(job_id)
            assert fetched is not None
            assert fetched["job_id"] == job_id

    asyncio.run(run())
