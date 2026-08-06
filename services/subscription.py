"""
Obuna (premium) xizmatini boshqarish.
"""
import aiosqlite
from datetime import datetime, timedelta

DB_PATH = "database.db"

PLANS = {
    "ai": {
        "name": "🤖 AI Yordamchi (30 kun)",
        "price": 9900,   # tiyin (0.01 so'm)
        "days": 30,
    },
    "report": {
        "name": "📋 Hisobot Generator (30 kun)",
        "price": 4900,
        "days": 30,
    },
    "full": {
        "name": "💎 Full Premium (30 kun)",
        "price": 19900,
        "days": 30,
    },
}


async def activate_premium(user_id: int, plan: str, days: int) -> None:
    """Foydalanuvchiga premium beradi yoki uzaytiradi."""
    expires = datetime.now() + timedelta(days=days)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO subscriptions (user_id, plan, expires_at)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                   plan = excluded.plan,
                   expires_at = excluded.expires_at
            """,
            (user_id, plan, expires.strftime("%Y-%m-%d %H:%M:%S"))
        )
        await db.commit()


async def is_premium(user_id: int) -> bool:
    """Foydalanuvchi premium obunasi faolmi?"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT expires_at FROM subscriptions WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
    if not row:
        return False
    expires = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
    return datetime.now() < expires


async def get_expiry(user_id: int) -> str | None:
    """Premium tugash sanasini qaytaradi."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT expires_at FROM subscriptions WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
    if not row:
        return None
    expires = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
    if datetime.now() >= expires:
        return None
    return expires.strftime("%d.%m.%Y")


async def save_payment(user_id: int, amount: int, plan: str,
                       provider: str, transaction_id: str) -> None:
    """To'lovni bazaga yozib qo'yadi."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR IGNORE INTO payments
               (user_id, amount, plan, provider, transaction_id, status)
               VALUES (?, ?, ?, ?, ?, 'pending')
            """,
            (user_id, amount, plan, provider, transaction_id)
        )
        await db.commit()


async def confirm_payment(transaction_id: str) -> dict | None:
    """To'lovni tasdiqlaydi va abona ma'lumotini qaytaradi."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id, plan FROM payments WHERE transaction_id = ? AND status = 'pending'",
            (transaction_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            return None
        await db.execute(
            "UPDATE payments SET status = 'paid' WHERE transaction_id = ?",
            (transaction_id,)
        )
        await db.commit()
    return {"user_id": row[0], "plan": row[1]}
