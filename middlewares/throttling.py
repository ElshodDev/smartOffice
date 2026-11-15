"""
Anti-spam: bir foydalanuvchidan juda tez kelayotgan xabarlarni cheklaydi.

Albom (bir yo'la tanlangan bir nechta rasm/fayl) bitta xabar deb hisoblanadi — aks holda
PDF birlashtirish yoki rasm(lar)→PDF uchun yuborilgan fayllarning faqat birinchisi qabul qilinardi.
"""
import logging
import time
from collections import deque

from aiogram import BaseMiddleware
from aiogram.types import Message
from cachetools import TTLCache

from config import ADMIN_ID

WINDOW = 5.0          # soniya
MAX_EVENTS = 8        # shu oraliqda ruxsat etilgan xabarlar
WARN_EVERY = 10.0     # ogohlantirish ko'pi bilan shuncha soniyada bir marta

_events: TTLCache = TTLCache(maxsize=20_000, ttl=WINDOW * 2)
_groups: TTLCache = TTLCache(maxsize=20_000, ttl=60)
_warned: TTLCache = TTLCache(maxsize=20_000, ttl=WARN_EVERY)

try:
    _ADMIN_ID = int(ADMIN_ID) if ADMIN_ID else None
except (ValueError, TypeError):
    _ADMIN_ID = None


def allow(user_id: int, media_group_id: str | None = None, now: float | None = None) -> bool:
    now = time.monotonic() if now is None else now
    if media_group_id:
        key = (user_id, media_group_id)
        if key in _groups:            # albomning keyingi qismlari — doim o'tadi
            return True
        _groups[key] = True
    times = _events.get(user_id)
    if times is None:
        times = deque()
    while times and now - times[0] > WINDOW:
        times.popleft()
    if len(times) >= MAX_EVENTS:
        _events[user_id] = times
        return False
    times.append(now)
    _events[user_id] = times
    return True


class ThrottlingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Message, data):
        user_id = event.from_user.id if event.from_user else None
        if user_id is None or user_id == _ADMIN_ID:
            return await handler(event, data)
        if not allow(user_id, getattr(event, "media_group_id", None)):
            logging.debug(f"Throttle: user {user_id} xabari rad etildi.")
            if user_id not in _warned:
                _warned[user_id] = True
                try:
                    await event.answer("⏳ Juda tez yuboryapsiz. Bir necha soniya kutib, qaytadan yuboring.")
                except Exception:
                    pass
            return None
        return await handler(event, data)
