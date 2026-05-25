from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import BillingCustomerModel, StudentVerificationModel


class BillingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_user(self, user_id: str) -> Optional[BillingCustomerModel]:
        result = await self.session.execute(
            select(BillingCustomerModel).where(BillingCustomerModel.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_customer_id(self, stripe_customer_id: str) -> Optional[BillingCustomerModel]:
        result = await self.session.execute(
            select(BillingCustomerModel).where(
                BillingCustomerModel.stripe_customer_id == stripe_customer_id
            )
        )
        return result.scalar_one_or_none()

    async def upsert_customer(self, user_id: str, stripe_customer_id: str) -> BillingCustomerModel:
        existing = await self.get_by_user(user_id)
        if existing:
            existing.stripe_customer_id = stripe_customer_id
            await self.session.commit()
            await self.session.refresh(existing)
            return existing

        record = BillingCustomerModel(
            user_id=user_id,
            stripe_customer_id=stripe_customer_id,
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def update_subscription_by_user(
        self,
        user_id: str,
        plan: Optional[str],
        status: Optional[str],
        stripe_subscription_id: Optional[str] = None,
        current_period_end: Optional[datetime] = None,
    ) -> Optional[BillingCustomerModel]:
        record = await self.get_by_user(user_id)
        if not record:
            return None

        record.plan = plan
        record.status = status
        if stripe_subscription_id is not None:
            record.stripe_subscription_id = stripe_subscription_id
        if current_period_end is not None:
            record.current_period_end = current_period_end

        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def update_subscription_by_customer(
        self,
        stripe_customer_id: str,
        plan: Optional[str],
        status: Optional[str],
        stripe_subscription_id: Optional[str] = None,
        current_period_end: Optional[datetime] = None,
    ) -> Optional[BillingCustomerModel]:
        record = await self.get_by_customer_id(stripe_customer_id)
        if not record:
            return None

        record.plan = plan
        record.status = status
        if stripe_subscription_id is not None:
            record.stripe_subscription_id = stripe_subscription_id
        if current_period_end is not None:
            record.current_period_end = current_period_end

        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def get_student_verification(self, user_id: str) -> Optional[StudentVerificationModel]:
        result = await self.session.execute(
            select(StudentVerificationModel).where(StudentVerificationModel.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create_student_verification(
        self,
        user_id: str,
        reference_id: Optional[str] = None,
    ) -> StudentVerificationModel:
        existing = await self.get_student_verification(user_id)
        if existing:
            existing.status = "pending"
            if reference_id is not None:
                existing.reference_id = reference_id
            await self.session.commit()
            await self.session.refresh(existing)
            return existing

        record = StudentVerificationModel(user_id=user_id, reference_id=reference_id)
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def update_student_verification(
        self,
        user_id: str,
        status: str,
        verified_at: Optional[datetime] = None,
    ) -> Optional[StudentVerificationModel]:
        record = await self.get_student_verification(user_id)
        if not record:
            return None
        record.status = status
        if verified_at is not None:
            record.verified_at = verified_at
        await self.session.commit()
        await self.session.refresh(record)
        return record
