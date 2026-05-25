from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, delete, update, or_
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    TeamModel,
    TeamMemberModel,
    TeamRole,
    CollectionModel,
    SsoProviderModel,
)


class TeamRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_team(
        self,
        owner_user_id: str,
        name: str,
        seat_count: int = 3,
        plan: str = "team",
    ) -> TeamModel:
        team = TeamModel(
            owner_user_id=owner_user_id,
            name=name,
            seat_count=seat_count,
            plan=plan,
        )
        self.session.add(team)
        await self.session.commit()
        await self.session.refresh(team)
        return team

    async def get_team(self, team_id: UUID) -> Optional[TeamModel]:
        result = await self.session.execute(select(TeamModel).where(TeamModel.id == team_id))
        return result.scalar_one_or_none()

    async def list_teams_for_user(self, user_id: str, email: Optional[str]) -> List[TeamModel]:
        query = select(TeamModel).where(TeamModel.owner_user_id == user_id)
        if email:
            query = query.union(
                select(TeamModel)
                .join(TeamMemberModel, TeamMemberModel.team_id == TeamModel.id)
                .where(or_(TeamMemberModel.user_id == user_id, TeamMemberModel.email == email))
            )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_members(self, team_id: UUID) -> List[TeamMemberModel]:
        result = await self.session.execute(
            select(TeamMemberModel).where(TeamMemberModel.team_id == team_id)
        )
        return list(result.scalars().all())

    async def get_member_for_user(
        self,
        team_id: UUID,
        user_id: str,
        email: Optional[str],
    ) -> Optional[TeamMemberModel]:
        query = select(TeamMemberModel).where(TeamMemberModel.team_id == team_id)
        if email:
            query = query.where(or_(TeamMemberModel.user_id == user_id, TeamMemberModel.email == email))
        else:
            query = query.where(TeamMemberModel.user_id == user_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def add_member(
        self,
        team_id: UUID,
        email: str,
        role: TeamRole,
        user_id: Optional[str] = None,
    ) -> TeamMemberModel:
        member = TeamMemberModel(
            team_id=team_id,
            email=email,
            role=role,
            user_id=user_id,
            status="invited",
        )
        self.session.add(member)
        await self.session.commit()
        await self.session.refresh(member)
        return member

    async def update_member_role(self, member_id: UUID, role: TeamRole) -> Optional[TeamMemberModel]:
        result = await self.session.execute(
            select(TeamMemberModel).where(TeamMemberModel.id == member_id)
        )
        member = result.scalar_one_or_none()
        if not member:
            return None
        member.role = role
        await self.session.commit()
        await self.session.refresh(member)
        return member

    async def remove_member(self, member_id: UUID) -> bool:
        result = await self.session.execute(
            select(TeamMemberModel).where(TeamMemberModel.id == member_id)
        )
        member = result.scalar_one_or_none()
        if not member:
            return False
        await self.session.delete(member)
        await self.session.commit()
        return True

    async def list_collections(self, team_id: UUID) -> List[CollectionModel]:
        result = await self.session.execute(
            select(CollectionModel).where(CollectionModel.team_id == team_id)
        )
        return list(result.scalars().all())

    async def create_collection(
        self,
        team_id: UUID,
        name: str,
        description: Optional[str],
        created_by: str,
    ) -> CollectionModel:
        collection = CollectionModel(
            team_id=team_id,
            name=name,
            description=description,
            created_by=created_by,
        )
        self.session.add(collection)
        await self.session.commit()
        await self.session.refresh(collection)
        return collection

    async def get_sso_provider(self, team_id: UUID) -> Optional[SsoProviderModel]:
        result = await self.session.execute(
            select(SsoProviderModel).where(SsoProviderModel.team_id == team_id)
        )
        return result.scalar_one_or_none()

    async def upsert_sso_provider(
        self,
        team_id: UUID,
        provider: str,
        domain: str,
        client_id: Optional[str],
        is_enabled: bool,
    ) -> SsoProviderModel:
        existing = await self.get_sso_provider(team_id)
        if existing:
            existing.provider = provider
            existing.domain = domain
            existing.client_id = client_id
            existing.is_enabled = is_enabled
            await self.session.commit()
            await self.session.refresh(existing)
            return existing

        record = SsoProviderModel(
            team_id=team_id,
            provider=provider,
            domain=domain,
            client_id=client_id,
            is_enabled=is_enabled,
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return record
