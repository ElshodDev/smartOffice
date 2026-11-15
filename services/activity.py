"""
📈 Foydalanuvchi faolligi: kim botdan foydalandi va qaysi bo'limlarni ishlatdi.

Har bir xabarda bazaga yozmaslik uchun ma'lumot xotirada yig'iladi va daqiqada bir marta
(faqat yangi narsa bo'lsa) bazaga yoziladi — Neon bazasi bo'sh vaqtda uxlay oladi.

- Foydalanuvchi kuniga bir marta "faol" deb belgilanadi (users.last_active);
  /start bosmagan eski foydalanuvchilar ham shu yo'l bilan bazaga qo'shiladi.
- Bo'lim ishlatilishi: bir bo'limga 30 daqiqa ichidagi barcha bosishlar = 1 marta.
"""
from __future__ import annotations

import logging
import time
from collections import Counter

from services import database
from services.timeutil import now_tashkent, DB_FORMAT

SESSION_SECONDS = 30 * 60

_seen_day: dict[int, str] = {}                  # user_id → oxirgi yozilgan kun
_pending_users: dict[int, str] = {}             # user_id → full_name
_pending_sections: Counter = Counter()          # (user_id, section) → soni
_last_section_hit: dict[tuple[int, str], float] = {}
_banned: set[int] = set()

# Bo'limlar (profil va admin statistikasi uchun). Kalitlar AI yordamchidagi SECTIONS bilan bir xil.
SECTION_TITLES = {
    "excel": "📊 Excel",
    "search": "🔍 Jadvaldan qidirish",
    "pdf": "📄 PDF",
    "word": "📝 Word",
    "docgen": "✍️ Rasmiy hujjat",
    "obyektivka": "📋 Obyektivka",
    "blanka": "🖊 Blanka to'ldirish",
    "translate": "🔤 Tarjimon va Alifbo",
    "format": "📁 Format o'zgartirish",
    "scan": "📸 Hujjat skaneri",
    "ocr": "🖼 Rasmdan matn (OCR)",
    "qr": "🔳 QR kod",
    "reminders": "⏰ Eslatmalar",
    "ai": "🤖 AI Yordamchi",
}


def record_user(user_id: int, full_name: str) -> None:
    today = now_tashkent().strftime("%Y-%m-%d")
    if _seen_day.get(user_id) != today:
        _seen_day[user_id] = today
        _pending_users[user_id] = full_name or ""


def record_section(user_id: int, section: str) -> None:
    if section not in SECTION_TITLES:
        return
    now = time.monotonic()
    key = (user_id, section)
    last = _last_section_hit.get(key)
    _last_section_hit[key] = now
    if last is None or now - last > SESSION_SECONDS:
        _pending_sections[key] += 1


def pending_sections_for(user_id: int) -> dict[str, int]:
    return {sec: n for (uid, sec), n in _pending_sections.items() if uid == user_id}


async def flush() -> None:
    """Yig'ilganlarni bazaga yozadi. Xato bo'lsa — keyingi safar qayta urinadi."""
    global _pending_sections
    if not _pending_users and not _pending_sections:
        return
    now = now_tashkent().strftime(DB_FORMAT)
    users = dict(_pending_users)
    sections = _pending_sections
    _pending_users.clear()
    _pending_sections = Counter()
    try:
        if users:
            await database.touch_users([(uid, name, now) for uid, name in users.items()])
        if sections:
            await database.add_section_uses([(uid, sec, n, now) for (uid, sec), n in sections.items()])
    except Exception as e:
        logging.error(f"Faollikni bazaga yozishda xato (keyinroq qayta uriniladi): {e}")
        for uid, name in users.items():
            _pending_users.setdefault(uid, name)
        _pending_sections.update(sections)
    # Xotira cheksiz o'smasin
    if len(_last_section_hit) > 50_000:
        cutoff = time.monotonic() - SESSION_SECONDS
        for key in [k for k, t in _last_section_hit.items() if t < cutoff]:
            del _last_section_hit[key]
    if len(_seen_day) > 100_000:
        _seen_day.clear()


# ── Admin tomonidan bloklanganlar ───────────────────────────────────────────
async def load_banned() -> None:
    _banned.clear()
    _banned.update(await database.get_banned_ids())


def is_banned(user_id: int) -> bool:
    return user_id in _banned


async def set_banned(user_id: int, banned: bool) -> bool:
    ok = await database.set_banned(user_id, banned)
    if ok:
        (_banned.add if banned else _banned.discard)(user_id)
    return ok
