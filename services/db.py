"""
Ma'lumotlar bazasi qatlami: SQLite (standart) yoki PostgreSQL (masalan, Neon).

- DATABASE_URL muhit o'zgaruvchisi bo'lsa → PostgreSQL (asyncpg, ulanishlar havzasi bilan).
- Bo'lmasa → SQLite fayli (avvalgidek).

So'rovlar bir xil yoziladi: parametrlar uchun "?" ishlatiladi, PostgreSQL uchun avtomatik
"$1, $2..." ga o'giriladi. Shuning uchun qolgan kod qaysi baza ishlayotganini bilmaydi.
"""
import logging
import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import aiosqlite

# asyncpg ulanish satrida qabul qiladigan parametrlar (Neon "channel_binding=require" kabi
# qo'shimchalar qo'shadi — ular serverga sozlama sifatida yuborilib, xato berishi mumkin)
_PG_URL_PARAMS = {"sslmode", "sslrootcert", "sslcert", "sslkey", "connect_timeout", "target_session_attrs"}


def database_url() -> str:
    return os.getenv("DATABASE_URL", "").strip()


def clean_pg_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme == "postgres":
        parts = parts._replace(scheme="postgresql")
    query = [(k, v) for k, v in parse_qsl(parts.query) if k in _PG_URL_PARAMS]
    return urlunsplit(parts._replace(query=urlencode(query)))


def _to_pg(sql: str) -> str:
    out, n = [], 0
    for ch in sql:
        if ch == "?":
            n += 1
            out.append(f"${n}")
        else:
            out.append(ch)
    return "".join(out)


def _rowcount(status: str) -> int:
    """asyncpg holat satri: 'UPDATE 1', 'INSERT 0 1', 'DELETE 3' → oxirgi son."""
    try:
        return int(status.split()[-1])
    except (ValueError, IndexError, AttributeError):
        return 0


class SqliteBackend:
    dialect = "sqlite"

    def __init__(self, path: str):
        self.path = path

    async def execute(self, sql: str, *args) -> int:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(sql, args)
            await db.commit()
            return cursor.rowcount

    async def executemany(self, sql: str, rows: list[tuple]) -> None:
        if not rows:
            return
        async with aiosqlite.connect(self.path) as db:
            await db.executemany(sql, rows)
            await db.commit()

    async def fetchall(self, sql: str, *args) -> list[tuple]:
        async with aiosqlite.connect(self.path) as db:
            async with db.execute(sql, args) as cursor:
                return [tuple(row) for row in await cursor.fetchall()]

    async def fetchone(self, sql: str, *args) -> tuple | None:
        rows = await self.fetchall(sql, *args)
        return rows[0] if rows else None

    async def migrate(self) -> None:
        from services.migrations import apply_migrations
        async with aiosqlite.connect(self.path) as db:
            await apply_migrations(db)
            await db.commit()


class PostgresBackend:
    dialect = "postgres"

    def __init__(self, url: str):
        self.url = clean_pg_url(url)
        self._pool = None

    async def _get_pool(self):
        if self._pool is None:
            import asyncpg
            self._pool = await asyncpg.create_pool(
                self.url,
                min_size=0, max_size=5,
                # Bo'sh ulanishlar 60 soniyadan keyin yopiladi — Neon bazasi uxlay oladi (tekin limit tejaladi)
                max_inactive_connection_lifetime=60,
                # Neon pooler (PgBouncer) bilan ishlash uchun tayyorlangan so'rovlar keshi o'chiriladi
                statement_cache_size=0,
                command_timeout=30,
            )
        return self._pool

    async def execute(self, sql: str, *args) -> int:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            return _rowcount(await conn.execute(_to_pg(sql), *args))

    async def executemany(self, sql: str, rows: list[tuple]) -> None:
        if not rows:
            return
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.executemany(_to_pg(sql), rows)

    async def fetchall(self, sql: str, *args) -> list[tuple]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            return [tuple(row) for row in await conn.fetch(_to_pg(sql), *args)]

    async def fetchone(self, sql: str, *args) -> tuple | None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(_to_pg(sql), *args)
            return tuple(row) if row else None

    async def migrate(self) -> None:
        from services.migrations import apply_pg_migrations
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await apply_pg_migrations(conn)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None


_pg_backend: PostgresBackend | None = None


def get_backend(sqlite_path: str):
    global _pg_backend
    url = database_url()
    if url:
        if _pg_backend is None or _pg_backend.url != clean_pg_url(url):
            _pg_backend = PostgresBackend(url)
        return _pg_backend
    return SqliteBackend(sqlite_path)


def describe() -> str:
    url = database_url()
    if not url:
        return "SQLite (fayl)"
    host = urlsplit(clean_pg_url(url)).hostname or "?"
    return f"PostgreSQL ({host})"


async def close() -> None:
    if _pg_backend is not None:
        await _pg_backend.close()


def warn_if_ephemeral() -> None:
    if not database_url() and os.getenv("RENDER"):
        logging.warning(
            "⚠️ Ma'lumotlar bazasi SQLite fayli — Render'da har deploy'da o'chadi. "
            "Doimiy saqlash uchun DATABASE_URL (masalan, Neon PostgreSQL) qo'shing."
        )
