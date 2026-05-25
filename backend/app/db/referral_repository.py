from __future__ import annotations

import secrets
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import ReferralCodeModel, ReferralRedemptionModel, ReferralCreditModel


class ReferralRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_code_for_user(self, user_id: str) -> Optional[ReferralCodeModel]:
        result = await self.session.execute(
            select(ReferralCodeModel).where(ReferralCodeModel.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_code_by_value(self, code: str) -> Optional[ReferralCodeModel]:
        result = await self.session.execute(
            select(ReferralCodeModel).where(ReferralCodeModel.code == code)
        )
        return result.scalar_one_or_none()

    async def create_or_get_code(self, user_id: str) -> ReferralCodeModel:
        existing = await self.get_code_for_user(user_id)
        if existing:
            return existing

        for _ in range(5):
            code = secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:10]
            if not code:
                continue
            collision = await self.get_code_by_value(code)
            if collision:
                continue
            record = ReferralCodeModel(user_id=user_id, code=code)
            self.session.add(record)
            await self.session.commit()
            await self.session.refresh(record)
            return record

        record = ReferralCodeModel(user_id=user_id, code=secrets.token_hex(5))
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def get_redemption_for_user(self, referred_user_id: str) -> Optional[ReferralRedemptionModel]:
        result = await self.session.execute(
            select(ReferralRedemptionModel).where(
                ReferralRedemptionModel.referred_user_id == referred_user_id
            )
        )
        return result.scalar_one_or_none()

    async def record_redemption(
        self,
        referrer_user_id: str,
        referred_user_id: str,
        code: str,
    ) -> ReferralRedemptionModel:
        record = ReferralRedemptionModel(
            referrer_user_id=referrer_user_id,
            referred_user_id=referred_user_id,
            code=code,
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def get_credit(self, user_id: str) -> Optional[ReferralCreditModel]:
        result = await self.session.execute(
            select(ReferralCreditModel).where(ReferralCreditModel.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def add_bonus_minutes(self, user_id: str, minutes: int) -> ReferralCreditModel:
        record = await self.get_credit(user_id)
        if record:
            record.bonus_minutes += minutes
            await self.session.commit()
            await self.session.refresh(record)
            return record

        record = ReferralCreditModel(user_id=user_id, bonus_minutes=minutes)
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return record
