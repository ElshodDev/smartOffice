from __future__ import annotations

from services.database import (
    get_recent_users,
    get_user_profile,
    get_users_count,
)


class SqliteIdentityReadAdapter:
    async def get_profile(self, telegram_id: int) -> dict | None:
        return await get_user_profile(telegram_id)

    async def get_user_count(self) -> int:
        return await get_users_count()

    async def get_recent_users(self, limit: int) -> list[dict]:
        return await get_recent_users(limit)
