from __future__ import annotations

from dataclasses import dataclass

from src.modules.identity.application.ports import IdentityReadPort


@dataclass(frozen=True, slots=True)
class IdentityQueryService:
    repository: IdentityReadPort

    async def get_own_profile(self, telegram_id: int) -> dict | None:
        return await self.repository.get_profile(telegram_id)

    async def get_admin_statistics(self, limit: int = 200) -> dict:
        return {
            "count": await self.repository.get_user_count(),
            "users": await self.repository.get_recent_users(limit),
        }
