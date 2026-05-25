from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from .models import ApiKeyModel, WebhookModel


class IntegrationsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_api_keys(self, user_id: str) -> List[ApiKeyModel]:
        result = await self.session.execute(
            select(ApiKeyModel).where(ApiKeyModel.user_id == user_id)
        )
        return list(result.scalars().all())

    async def create_api_key(
        self,
        user_id: str,
        label: str,
        key_prefix: str,
        key_hash: str,
        team_id: Optional[UUID],
    ) -> ApiKeyModel:
        record = ApiKeyModel(
            user_id=user_id,
            label=label,
            key_prefix=key_prefix,
            key_hash=key_hash,
            team_id=team_id,
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def delete_api_key(self, api_key_id: UUID, user_id: str) -> bool:
        result = await self.session.execute(
            select(ApiKeyModel).where(ApiKeyModel.id == api_key_id, ApiKeyModel.user_id == user_id)
        )
        record = result.scalar_one_or_none()
        if not record:
            return False
        await self.session.delete(record)
        await self.session.commit()
        return True

    async def list_webhooks(self, user_id: str) -> List[WebhookModel]:
        result = await self.session.execute(
            select(WebhookModel).where(WebhookModel.user_id == user_id)
        )
        return list(result.scalars().all())

    async def create_webhook(
        self,
        user_id: str,
        url: str,
        events: List[str],
        secret: str,
        team_id: Optional[UUID],
    ) -> WebhookModel:
        record = WebhookModel(
            user_id=user_id,
            url=url,
            events=events,
            secret=secret,
            team_id=team_id,
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def delete_webhook(self, webhook_id: UUID, user_id: str) -> bool:
        result = await self.session.execute(
            select(WebhookModel).where(WebhookModel.id == webhook_id, WebhookModel.user_id == user_id)
        )
        record = result.scalar_one_or_none()
        if not record:
            return False
        await self.session.delete(record)
        await self.session.commit()
        return True
