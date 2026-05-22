from typing import List, Optional, Protocol, Dict, Any
from uuid import UUID
from sqlalchemy import select, update, delete, desc
from sqlalchemy.ext.asyncio import AsyncSession
from .models import JobModel, JobStatus

class JobRepository(Protocol):
    async def create(self, user_id: str, video_url: str) -> JobModel: ...
    async def get_by_id(self, job_id: UUID) -> Optional[JobModel]: ...
    async def list_by_user(
        self, 
        user_id: str, 
        limit: int = 10, 
        offset: int = 0,
        status: Optional[JobStatus] = None
    ) -> List[JobModel]: ...
    async def update_status(self, job_id: UUID, status: JobStatus, progress: float = 0.0, error: Optional[str] = None) -> Optional[JobModel]: ...
    async def update_result(self, job_id: UUID, transcript: str, summary: str, metadata: Dict[str, Any]) -> Optional[JobModel]: ...
    async def delete(self, job_id: UUID) -> bool: ...

class SQLAlchemyJobRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: str, video_url: str) -> JobModel:
        job = JobModel(user_id=user_id, video_url=video_url)
        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def get_by_id(self, job_id: UUID) -> Optional[JobModel]:
        result = await self.session.execute(
            select(JobModel).where(JobModel.id == job_id)
        )
        return result.scalar_one_or_none()

    async def list_by_user(
        self, 
        user_id: str, 
        limit: int = 10, 
        offset: int = 0,
        status: Optional[JobStatus] = None
    ) -> List[JobModel]:
        query = select(JobModel).where(JobModel.user_id == user_id).order_by(desc(JobModel.created_at))
        
        if status:
            query = query.where(JobModel.status == status)
            
        query = query.limit(limit).offset(offset)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_status(self, job_id: UUID, status: JobStatus, progress: float = 0.0, error: Optional[str] = None) -> Optional[JobModel]:
        job = await self.get_by_id(job_id)
        if not job:
            return None
        
        job.status = status
        job.progress = progress
        if error:
            job.error_message = error
            
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def update_result(self, job_id: UUID, transcript: str, summary: str, metadata: Dict[str, Any]) -> Optional[JobModel]:
        job = await self.get_by_id(job_id)
        if not job:
            return None
        
        job.status = JobStatus.COMPLETED
        job.progress = 1.0
        job.transcript = transcript
        job.summary = summary
        job.metadata_json = metadata
            
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def delete(self, job_id: UUID) -> bool:
        job = await self.get_by_id(job_id)
        if not job:
            return False
        
        await self.session.delete(job)
        await self.session.commit()
        return True
