"""
Botning ma'lumotlar bazasi funksiyalari. Baza turi services/db.py da tanlanadi:
DATABASE_URL bo'lsa — PostgreSQL (Neon), bo'lmasa — SQLite fayli.
"""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from services import db
from services.timeutil import now_tashkent, DB_FORMAT

DB_PATH = "database.db"   # SQLite fayli (DATABASE_URL bo'lmaganda)


def _db():
    return db.get_backend(DB_PATH)


async def create_table() -> None:
    """Barcha migratsiyalarni qo'llaydi (jadvallarni yaratadi/yangilaydi)."""
    await _db().migrate()
    _reset_reminder_cache()
    logging.info(f"Database: {db.describe()} — barcha jadvallar tayyor.")
    db.warn_if_ephemeral()


# ── Foydalanuvchilar ───────────────────────────────────────────────────────
async def add_user(telegram_id: int, full_name: str, referrer_id: int = None) -> bool:
    """Yangi foydalanuvchini qo'shadi. Yangi bo'lsa True."""
    inserted = await _db().execute(
        "INSERT INTO users (telegram_id, full_name, referrer_id, joined_date) VALUES (?, ?, ?, ?) "
        "ON CONFLICT (telegram_id) DO NOTHING",
        telegram_id, full_name, referrer_id, now_tashkent().strftime(DB_FORMAT),
    )
    return inserted == 1


async def increment_usage(telegram_id: int) -> int:
    await _db().execute("UPDATE users SET usage_count = usage_count + 1 WHERE telegram_id = ?", telegram_id)
    row = await _db().fetchone("SELECT usage_count FROM users WHERE telegram_id = ?", telegram_id)
    return row[0] if row else 0


async def get_users_count() -> int:
    row = await _db().fetchone("SELECT COUNT(*) FROM users")
    return row[0] if row else 0


async def get_all_users() -> list[int]:
    return [row[0] for row in await _db().fetchall("SELECT telegram_id FROM users")]


async def get_recent_users(limit: int = 50) -> list[dict]:
    rows = await _db().fetchall(
        "SELECT telegram_id, full_name, joined_date, usage_count FROM users ORDER BY id DESC LIMIT ?", limit
    )
    return [{"id": r[0], "name": r[1], "date": str(r[2] or ""), "usage": r[3] or 0} for r in rows]


async def get_user_profile(telegram_id: int) -> dict | None:
    row = await _db().fetchone(
        "SELECT telegram_id, full_name, joined_date, usage_count, referrer_id FROM users WHERE telegram_id = ?",
        telegram_id,
    )
    if not row:
        return None
    return {"id": row[0], "name": row[1], "joined_date": str(row[2] or ""),
            "usage_count": row[3] or 0, "referrer_id": row[4]}


# ── Eslatmalar ─────────────────────────────────────────────────────────────
# Scheduler har daqiqada eslatmalarni tekshiradi. Har safar bazaga so'rov yubormaslik uchun
# eng yaqin eslatma vaqti xotirada saqlanadi — baza faqat vaqti kelganda yoki o'zgarishdan
# keyin so'raladi. Neon bepul tarifida bu bazaga «uxlash» imkonini beradi (oylik limit tejaladi).
_next_due: str | None = None
_next_due_known = False


def _reset_reminder_cache() -> None:
    global _next_due, _next_due_known
    _next_due, _next_due_known = None, False


async def _refresh_next_due() -> None:
    global _next_due, _next_due_known
    row = await _db().fetchone("SELECT MIN(run_date) FROM reminders WHERE is_done = 0")
    _next_due, _next_due_known = (str(row[0]) if row and row[0] else None), True


async def add_reminder(user_id: int, text: str, run_date_str: str):
    """Yangi eslatma (run_date_str: Toshkent vaqti, 'YYYY-MM-DD HH:MM:SS')."""
    global _next_due
    await _db().execute(
        "INSERT INTO reminders (user_id, text, run_date, is_done) VALUES (?, ?, ?, 0)", user_id, text, run_date_str
    )
    if _next_due_known and (_next_due is None or run_date_str < _next_due):
        _next_due = run_date_str


async def get_due_reminders(now_str: str):
    """Vaqti kelgan bajarilmagan eslatmalar. Hech biri yaqin bo'lmasa — bazaga murojaat qilinmaydi."""
    if not _next_due_known:
        await _refresh_next_due()
    if _next_due is None or _next_due > now_str:
        return []
    rows = await _db().fetchall(
        "SELECT id, user_id, text FROM reminders WHERE is_done = 0 AND run_date <= ? ORDER BY run_date", now_str
    )
    _reset_reminder_cache()   # yuborilgandan keyin keyingi eslatma vaqti qayta o'qiladi
    return rows


async def mark_reminder_done(reminder_id: int):
    await _db().execute("UPDATE reminders SET is_done = 1 WHERE id = ?", reminder_id)


async def get_user_reminders(user_id: int) -> list[tuple]:
    """Foydalanuvchining bajarilmagan eslatmalari: (id, text, run_date), vaqt bo'yicha."""
    rows = await _db().fetchall(
        "SELECT id, text, run_date FROM reminders WHERE user_id = ? AND is_done = 0 ORDER BY run_date", user_id
    )
    return [(r[0], r[1], str(r[2])) for r in rows]


async def delete_reminder(reminder_id: int, user_id: int) -> bool:
    """Faqat egasi o'z eslatmasini o'chira oladi."""
    deleted = await _db().execute("DELETE FROM reminders WHERE id = ? AND user_id = ?", reminder_id, user_id)
    if deleted:
        _reset_reminder_cache()
    return deleted > 0


# ── Blanka tahrirlash seanslari (Web App) ──────────────────────────────────
def _hash_form_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def create_form_session(user_id: int, filename: str, ttl: timedelta = timedelta(hours=2)) -> str:
    """Bitta foydalanuvchining fayli uchun qisqa muddatli token."""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + ttl
    await _db().execute(
        "INSERT INTO form_sessions (token_hash, user_id, filename, expires_at) VALUES (?, ?, ?, ?)",
        _hash_form_token(token), user_id, filename, expires_at.isoformat(),
    )
    return token


async def get_form_session(token: str) -> dict | None:
    if not token:
        return None
    row = await _db().fetchone(
        "SELECT user_id, filename, expires_at, used_at FROM form_sessions WHERE token_hash = ?",
        _hash_form_token(token),
    )
    if not row or row[3]:
        return None
    try:
        expires_at = datetime.fromisoformat(str(row[2]))
    except (TypeError, ValueError):
        return None
    if expires_at <= datetime.now(timezone.utc):
        return None
    return {"user_id": row[0], "filename": row[1]}


async def consume_form_session(token: str, user_id: int, filename: str) -> bool:
    """Yaroqli seansni bir martalik qilib belgilaydi."""
    now = datetime.now(timezone.utc).isoformat()
    updated = await _db().execute(
        "UPDATE form_sessions SET used_at = ? WHERE token_hash = ? AND user_id = ? AND filename = ? "
        "AND used_at IS NULL AND expires_at > ?",
        now, _hash_form_token(token), user_id, filename, now,
    )
    return updated == 1


async def cleanup_expired_form_sessions() -> list[str]:
    """Muddati o'tgan/ishlatilgan seanslarni o'chiradi va ularning fayl nomlarini qaytaradi."""
    now = datetime.now(timezone.utc).isoformat()
    rows = await _db().fetchall(
        "SELECT filename FROM form_sessions WHERE expires_at <= ? OR used_at IS NOT NULL", now
    )
    if rows:
        await _db().execute("DELETE FROM form_sessions WHERE expires_at <= ? OR used_at IS NOT NULL", now)
    return [row[0] for row in rows]
