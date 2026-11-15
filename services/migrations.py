"""Small, versioned SQLite migration runner.

This is intentionally dependency-light so existing deployments can migrate
without a destructive database reset. It can later be replaced by Alembic
without changing application-facing repository functions.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import aiosqlite

Migration = Callable[[aiosqlite.Connection], Awaitable[None]]


async def _migration_1(db: aiosqlite.Connection) -> None:
    await db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id BIGINT UNIQUE NOT NULL,
            full_name TEXT,
            referrer_id BIGINT,
            usage_count INTEGER DEFAULT 0,
            joined_date DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            run_date TIMESTAMP NOT NULL,
            is_done INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS subscriptions (
            user_id BIGINT PRIMARY KEY,
            plan TEXT DEFAULT 'free',
            expires_at DATETIME
        );
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id BIGINT NOT NULL,
            amount INTEGER NOT NULL,
            plan TEXT,
            provider TEXT,
            transaction_id TEXT UNIQUE,
            status TEXT DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )


async def _migration_2(db: aiosqlite.Connection) -> None:
    async with db.execute("PRAGMA table_info(users)") as cursor:
        columns = {row[1] for row in await cursor.fetchall()}

    if "referrer_id" not in columns:
        await db.execute("ALTER TABLE users ADD COLUMN referrer_id BIGINT")
    if "usage_count" not in columns:
        await db.execute(
            "ALTER TABLE users ADD COLUMN usage_count INTEGER DEFAULT 0"
        )


async def _migration_3(db: aiosqlite.Connection) -> None:
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS form_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_hash TEXT UNIQUE NOT NULL,
            user_id BIGINT NOT NULL,
            filename TEXT NOT NULL,
            expires_at DATETIME NOT NULL,
            used_at DATETIME
        )
        """
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_form_sessions_expiry "
        "ON form_sessions (expires_at)"
    )


async def _migration_4(db: aiosqlite.Connection) -> None:
    """Faollik, bloklash va bo'limlar statistikasi."""
    async with db.execute("PRAGMA table_info(users)") as cursor:
        columns = {row[1] for row in await cursor.fetchall()}
    for name, ddl in (("last_active", "TEXT"), ("is_banned", "INTEGER DEFAULT 0"), ("bot_blocked", "INTEGER DEFAULT 0")):
        if name not in columns:
            await db.execute(f"ALTER TABLE users ADD COLUMN {name} {ddl}")
    await db.executescript(SECTIONS_TABLE_SQL)


SECTIONS_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS user_sections (
        user_id BIGINT NOT NULL,
        section TEXT NOT NULL,
        uses INTEGER NOT NULL DEFAULT 0,
        first_used TEXT,
        last_used TEXT,
        PRIMARY KEY (user_id, section)
    );
    CREATE INDEX IF NOT EXISTS idx_user_sections_last ON user_sections (last_used);
    CREATE INDEX IF NOT EXISTS idx_users_referrer ON users (referrer_id);
"""


MIGRATIONS: tuple[Migration, ...] = (_migration_1, _migration_2, _migration_3, _migration_4)


async def apply_migrations(db: aiosqlite.Connection) -> None:
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    async with db.execute("SELECT version FROM schema_migrations") as cursor:
        applied = {row[0] for row in await cursor.fetchall()}

    for version, migration in enumerate(MIGRATIONS, start=1):
        if version in applied:
            continue
        await migration(db)
        await db.execute(
            "INSERT INTO schema_migrations (version) VALUES (?)", (version,)
        )


# ── PostgreSQL (masalan, Neon) ──────────────────────────────────────────────
# Sanalar SQLite'dagi kabi matn ko'rinishida saqlanadi ("YYYY-MM-DD HH:MM:SS" / ISO),
# shuning uchun ilova kodi ikkala bazada ham bir xil ishlaydi.
PG_MIGRATIONS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS users (
        id BIGSERIAL PRIMARY KEY,
        telegram_id BIGINT UNIQUE NOT NULL,
        full_name TEXT,
        referrer_id BIGINT,
        usage_count INTEGER DEFAULT 0,
        joined_date TEXT
    );
    CREATE TABLE IF NOT EXISTS reminders (
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        text TEXT NOT NULL,
        run_date TEXT NOT NULL,
        is_done INTEGER DEFAULT 0
    );
    CREATE INDEX IF NOT EXISTS idx_reminders_pending ON reminders (is_done, run_date);
    CREATE TABLE IF NOT EXISTS form_sessions (
        id BIGSERIAL PRIMARY KEY,
        token_hash TEXT UNIQUE NOT NULL,
        user_id BIGINT NOT NULL,
        filename TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        used_at TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_form_sessions_expiry ON form_sessions (expires_at);
    """,
    """
    ALTER TABLE users ADD COLUMN IF NOT EXISTS last_active TEXT;
    ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned INTEGER DEFAULT 0;
    ALTER TABLE users ADD COLUMN IF NOT EXISTS bot_blocked INTEGER DEFAULT 0;
    """ + SECTIONS_TABLE_SQL,
)


async def apply_pg_migrations(conn) -> None:
    await conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TIMESTAMPTZ DEFAULT now())"
    )
    applied = {row[0] for row in await conn.fetch("SELECT version FROM schema_migrations")}
    for version, sql in enumerate(PG_MIGRATIONS, start=1):
        if version in applied:
            continue
        async with conn.transaction():
            await conn.execute(sql)
            await conn.execute("INSERT INTO schema_migrations (version) VALUES ($1)", version)
