import logging
from typing import Any, Awaitable, Callable, Dict
from cachetools import TTLCache
from aiogram import BaseMiddleware
from aiogram.types import Message
from config import ADMIN_ID

# Har bir user uchun 1.5 soniyali TTL cache (maksimum 10_000 foydalanuvchi)
RATE_LIMIT = 1.5  # sekund
cache: TTLCache = TTLCache(maxsize=10_000, ttl=RATE_LIMIT)

try:
    _ADMIN_ID = int(ADMIN_ID) if ADMIN_ID else None
except (ValueError, TypeError):
    _ADMIN_ID = None


class ThrottlingMiddleware(BaseMiddleware):
    """
    Anti-Spam (Throttle) Middleware.
    Har bir foydalanuvchi RATE_LIMIT soniyada bir marta xabar yubora oladi.
    Admin har doim o'tkazib yuboriladi.
    """

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id if event.from_user else None

        if user_id is None:
            return await handler(event, data)

        # Admin uchun throttling yo'q
        if user_id == _ADMIN_ID:
            return await handler(event, data)

        if user_id in cache:
            logging.debug(f"Throttle: user {user_id} xabari rad etildi.")
            return

        cache[user_id] = True
        return await handler(event, data)

