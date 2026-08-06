import aiosqlite
import logging
from datetime import datetime

DB_PATH = "database.db"

async def create_table() -> None:
    """Baza va users jadvali yaratiladi (agar mavjud bo'lmasa)."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Foydalanuvchilar jadvali
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id  BIGINT  UNIQUE NOT NULL,
                full_name    TEXT,
                referrer_id  BIGINT,
                usage_count  INTEGER DEFAULT 0,
                joined_date  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Eski bazaga ustunlarni qo'shish (agar bo'lmasa xato bermay o'tkazib yuboradi)
        try:
            await db.execute("ALTER TABLE users ADD COLUMN referrer_id BIGINT")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE users ADD COLUMN usage_count INTEGER DEFAULT 0")
        except Exception:
            pass

        
        # Eslatmalar jadvali
        await db.execute('''
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                text TEXT,
                run_date TIMESTAMP,
                is_done INTEGER DEFAULT 0
            )
        ''')
        # Obunalar jadvali (premium)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                user_id     BIGINT PRIMARY KEY,
                plan        TEXT DEFAULT 'free',
                expires_at  DATETIME
            )
        ''')

        # To'lovlar jadvali
        await db.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         BIGINT NOT NULL,
                amount          INTEGER NOT NULL,
                plan            TEXT,
                provider        TEXT,
                transaction_id  TEXT UNIQUE,
                status          TEXT DEFAULT 'pending',
                created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
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
            "SELECT telegram_id, full_name, joined_date FROM users ORDER BY id DESC LIMIT ?", 
            (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {"id": row[0], "name": row[1], "date": row[2]} 
                for row in rows
            ]

