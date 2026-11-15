import aiosqlite
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from services.migrations import apply_migrations

DB_PATH = "database.db"

async def create_table() -> None:
    """Apply all pending, versioned database migrations."""
    async with aiosqlite.connect(DB_PATH) as db:
        await apply_migrations(db)
        await db.commit()
    logging.info("Database: barcha jadvallar tayyor.")

async def add_user(telegram_id: int, full_name: str, referrer_id: int = None) -> bool:
    """Yangi foydalanuvchini bazaga qo'shadi. Agar yangi bo'lsa True qaytaradi."""
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO users (telegram_id, full_name, referrer_id, joined_date) VALUES (?, ?, ?, ?)",
                (telegram_id, full_name, referrer_id, datetime.now())
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

async def increment_usage(telegram_id: int) -> int:
    """Foydalanuvchining usage_count qiymatini 1 ga oshiradi va yangi qiymatni qaytaradi."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET usage_count = usage_count + 1 WHERE telegram_id = ?", (telegram_id,))
        await db.commit()
        async with db.execute("SELECT usage_count FROM users WHERE telegram_id = ?", (telegram_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def get_users_count() -> int:
    """Bazadagi jami foydalanuvchilar sonini qaytaradi."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            row = await cursor.fetchone()
        return row[0] if row else 0

async def add_reminder(user_id: int, text: str, run_date_str: str):
    """Yangi eslatma qo'shish (run_date_str: YYYY-MM-DD HH:MM:SS)"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO reminders (user_id, text, run_date, is_done) VALUES (?, ?, ?, 0)", 
                         (user_id, text, run_date_str))
        await db.commit()

async def get_due_reminders():
    """Vaqti kelgan (yoki o'tib ketgan) bajarilmagan eslatmalarni olish"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, user_id, text FROM reminders WHERE is_done = 0 AND run_date <= datetime('now', 'localtime')") as cursor:
            return await cursor.fetchall()

async def mark_reminder_done(reminder_id: int):
    """Eslatmani bajarilgan deb belgilash"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE reminders SET is_done = 1 WHERE id = ?", (reminder_id,))
        await db.commit()

async def get_all_users() -> list[int]:
    """Bazadagi barcha foydalanuvchilarning telegram_id larini qaytaradi."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT telegram_id FROM users") as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

async def get_recent_users(limit: int = 50) -> list[dict]:
    """Oxirgi qo'shilgan foydalanuvchilar ro'yxatini qaytaradi."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT telegram_id, full_name, joined_date, usage_count FROM users ORDER BY id DESC LIMIT ?", 
            (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {"id": row[0], "name": row[1], "date": row[2], "usage": row[3] or 0} 
                for row in rows
            ]

async def get_user_profile(telegram_id: int) -> dict | None:
    """Bitta foydalanuvchining to'liq profilini qaytaradi."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT telegram_id, full_name, joined_date, usage_count, referrer_id FROM users WHERE telegram_id = ?",
            (telegram_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "name": row[1],
                "joined_date": row[2],
                "usage_count": row[3] or 0,
                "referrer_id": row[4],
            }


def _hash_form_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def create_form_session(
    user_id: int, filename: str, ttl: timedelta = timedelta(hours=2)
) -> str:
    """Create a short-lived bearer token for one user's form file."""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + ttl
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO form_sessions
                (token_hash, user_id, filename, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (_hash_form_token(token), user_id, filename, expires_at.isoformat()),
        )
        await db.commit()
    return token


async def get_form_session(token: str) -> dict | None:
    """Return an active form session without exposing its bearer token."""
    if not token:
        return None

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT user_id, filename, expires_at, used_at
            FROM form_sessions
            WHERE token_hash = ?
            """,
            (_hash_form_token(token),),
        ) as cursor:
            row = await cursor.fetchone()

    if not row or row[3]:
        return None
    try:
        expires_at = datetime.fromisoformat(row[2])
    except (TypeError, ValueError):
        return None
    if expires_at <= datetime.now(timezone.utc):
        return None
    return {"user_id": row[0], "filename": row[1]}


async def consume_form_session(token: str, user_id: int, filename: str) -> bool:
    """Atomically mark a valid form session as used."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            UPDATE form_sessions
            SET used_at = ?
            WHERE token_hash = ?
              AND user_id = ?
              AND filename = ?
              AND used_at IS NULL
              AND expires_at > ?
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                _hash_form_token(token),
                user_id,
                filename,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        await db.commit()
        return cursor.rowcount == 1


async def cleanup_expired_form_sessions() -> list[str]:
    """Delete expired/consumed sessions and return their file names."""
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT filename FROM form_sessions
            WHERE expires_at <= ? OR used_at IS NOT NULL
            """,
            (now,),
        ) as cursor:
            filenames = [row[0] for row in await cursor.fetchall()]
        await db.execute(
            "DELETE FROM form_sessions WHERE expires_at <= ? OR used_at IS NOT NULL",
            (now,),
        )
        await db.commit()
    return filenames
