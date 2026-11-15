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


MIGRATIONS: tuple[Migration, ...] = (_migration_1, _migration_2)


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
