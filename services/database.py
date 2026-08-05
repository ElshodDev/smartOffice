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
                joined_date  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
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
        await db.commit()
    logging.info("Database: 'users' jadvali tayyor.")

async def add_user(telegram_id: int, full_name: str) -> None:
    """Yangi foydalanuvchini bazaga qo'shadi (takroran qo'shilmaydi - IGNORE)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (telegram_id, full_name, joined_date) VALUES (?, ?, ?)",
            (telegram_id, full_name, datetime.now())
        )
        await db.commit()

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
