from __future__ import annotations

from typing import Protocol


class IdentityReadPort(Protocol):
    async def get_profile(self, telegram_id: int) -> dict | None: ...

    async def get_user_count(self) -> int: ...

    async def get_recent_users(self, limit: int) -> list[dict]: ...
