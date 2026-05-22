from datetime import datetime
from uuid import UUID, uuid4
from typing import Optional, List, Dict, Any
from sqlalchemy import String, DateTime, JSON, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .session import Base
import enum

class JobStatus(str, enum.Enum):
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class JobModel(Base):
    __tablename__ = "jobs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(String, index=True)
    video_url: Mapped[str] = mapped_column(String)
    status: Mapped[JobStatus] = mapped_column(SQLEnum(JobStatus), default=JobStatus.PENDING)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Progress and state
    progress: Mapped[float] = mapped_column(default=0.0)
    error_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    # Results
    transcript: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "video_url": self.video_url,
            "status": self.status.value,
            "progress": self.progress,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "error_message": self.error_message,
            "result": {
                "transcript": self.transcript,
                "summary": self.summary,
                "metadata": self.metadata_json
            } if self.status == JobStatus.COMPLETED else None
        }


class BillingCustomerModel(Base):
    __tablename__ = "billing_customers"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(String, index=True)
    stripe_customer_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    plan: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    current_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
