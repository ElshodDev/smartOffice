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


# ── Faollik va bo'limlar statistikasi ───────────────────────────────────────
# services/activity.py xotirada yig'adi va daqiqada bir marta shu funksiyalar bilan yozadi.
async def touch_users(rows: list[tuple[int, str, str]]) -> None:
    """(telegram_id, full_name, now_str): yangi bo'lsa qo'shadi, bor bo'lsa oxirgi faollikni yangilaydi."""
    await _db().executemany(
        "INSERT INTO users (telegram_id, full_name, joined_date, last_active) VALUES (?, ?, ?, ?) "
        "ON CONFLICT (telegram_id) DO UPDATE SET last_active = excluded.last_active, "
        "full_name = excluded.full_name, bot_blocked = 0",
        [(uid, name, now, now) for uid, name, now in rows],
    )
    await _db().executemany(
        "INSERT INTO daily_activity (day, user_id) VALUES (?, ?) ON CONFLICT (day, user_id) DO NOTHING",
        [(now[:10], uid) for uid, _, now in rows],
    )


async def add_section_uses(rows: list[tuple[int, str, int, str]]) -> None:
    """(user_id, section, uses, now_str)."""
    await _db().executemany(
        "INSERT INTO user_sections (user_id, section, uses, first_used, last_used) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT (user_id, section) DO UPDATE SET uses = user_sections.uses + excluded.uses, "
        "last_used = excluded.last_used",
        [(uid, sec, n, now, now) for uid, sec, n, now in rows],
    )
    totals: dict[int, int] = {}
    for uid, _, n, _ in rows:
        totals[uid] = totals.get(uid, 0) + n
    await _db().executemany(
        "UPDATE users SET usage_count = COALESCE(usage_count, 0) + ? WHERE telegram_id = ?",
        [(n, uid) for uid, n in totals.items()],
    )


async def get_user_sections(telegram_id: int) -> dict[str, int]:
    rows = await _db().fetchall("SELECT section, uses FROM user_sections WHERE user_id = ?", telegram_id)
    return {r[0]: r[1] for r in rows}


async def count_referrals(telegram_id: int) -> int:
    row = await _db().fetchone("SELECT COUNT(*) FROM users WHERE referrer_id = ?", telegram_id)
    return row[0] if row else 0


async def count_active_reminders(telegram_id: int) -> int:
    row = await _db().fetchone("SELECT COUNT(*) FROM reminders WHERE user_id = ? AND is_done = 0", telegram_id)
    return row[0] if row else 0


async def user_exists(telegram_id: int) -> bool:
    return await _db().fetchone("SELECT 1 FROM users WHERE telegram_id = ?", telegram_id) is not None


async def _count(sql: str, *args) -> int:
    row = await _db().fetchone(sql, *args)
    return int(row[0] or 0) if row else 0


async def admin_stats(day_start: str, week_start: str, month_start: str) -> dict:
    """Sanalar — Toshkent vaqti, DB_FORMAT ("YYYY-MM-DD HH:MM:SS")."""
    return {
        "total": await _count("SELECT COUNT(*) FROM users"),
        "new_day": await _count("SELECT COUNT(*) FROM users WHERE joined_date >= ?", day_start),
        "new_week": await _count("SELECT COUNT(*) FROM users WHERE joined_date >= ?", week_start),
        "new_month": await _count("SELECT COUNT(*) FROM users WHERE joined_date >= ?", month_start),
        "active_day": await _count("SELECT COUNT(*) FROM users WHERE last_active >= ?", day_start),
        "active_week": await _count("SELECT COUNT(*) FROM users WHERE last_active >= ?", week_start),
        "active_month": await _count("SELECT COUNT(*) FROM users WHERE last_active >= ?", month_start),
        "blocked": await _count("SELECT COUNT(*) FROM users WHERE bot_blocked = 1"),
        "banned": await _count("SELECT COUNT(*) FROM users WHERE is_banned = 1"),
        "referred": await _count("SELECT COUNT(*) FROM users WHERE referrer_id IS NOT NULL"),
        "reminders": await _count("SELECT COUNT(*) FROM reminders WHERE is_done = 0"),
    }


async def top_sections(since: str | None = None, limit: int = 10) -> list[tuple[str, int, int]]:
    """(bo'lim, foydalanuvchilar soni, jami ishlatish) — `since` dan beri faol bo'lganlar."""
    where, args = ("WHERE last_used >= ?", (since,)) if since else ("", ())
    rows = await _db().fetchall(
        f"SELECT section, COUNT(*), SUM(uses) FROM user_sections {where} "
        "GROUP BY section ORDER BY COUNT(*) DESC, SUM(uses) DESC LIMIT ?", *args, limit,
    )
    return [(r[0], int(r[1]), int(r[2] or 0)) for r in rows]


async def top_referrers(limit: int = 5) -> list[tuple[int, str, int]]:
    rows = await _db().fetchall(
        "SELECT r.referrer_id, COALESCE(u.full_name, ''), COUNT(*) AS n FROM users r "
        "LEFT JOIN users u ON u.telegram_id = r.referrer_id "
        "WHERE r.referrer_id IS NOT NULL GROUP BY r.referrer_id, u.full_name ORDER BY n DESC LIMIT ?", limit,
    )
    return [(r[0], r[1], int(r[2])) for r in rows]


async def get_broadcast_targets() -> list[int]:
    """Xabar tarqatish uchun: botni bloklamagan va admin bloklamagan foydalanuvchilar."""
    rows = await _db().fetchall(
        "SELECT telegram_id FROM users WHERE COALESCE(bot_blocked, 0) = 0 AND COALESCE(is_banned, 0) = 0"
    )
    return [r[0] for r in rows]


async def mark_bot_blocked(ids: list[int]) -> None:
    await _db().executemany("UPDATE users SET bot_blocked = 1 WHERE telegram_id = ?", [(i,) for i in ids])


async def set_banned(telegram_id: int, banned: bool) -> bool:
    return await _db().execute(
        "UPDATE users SET is_banned = ? WHERE telegram_id = ?", 1 if banned else 0, telegram_id
    ) > 0


async def get_banned_ids() -> set[int]:
    return {r[0] for r in await _db().fetchall("SELECT telegram_id FROM users WHERE is_banned = 1")}


_USER_COLUMNS = ("telegram_id, full_name, joined_date, last_active, usage_count, referrer_id, "
                 "COALESCE(is_banned, 0), COALESCE(bot_blocked, 0)")


def _user_row(r) -> dict:
    return {"id": r[0], "name": r[1] or "", "joined": str(r[2] or ""), "last_active": str(r[3] or ""),
            "usage": r[4] or 0, "referrer_id": r[5], "banned": bool(r[6]), "blocked": bool(r[7])}


async def find_users(query: str, limit: int = 10) -> list[dict]:
    """ID bo'yicha aniq yoki ism bo'yicha qidiradi."""
    query = query.strip().lstrip("@")
    if query.isdigit():
        rows = await _db().fetchall(f"SELECT {_USER_COLUMNS} FROM users WHERE telegram_id = ?", int(query))
    else:
        rows = await _db().fetchall(
            f"SELECT {_USER_COLUMNS} FROM users WHERE LOWER(full_name) LIKE ? ORDER BY last_active DESC LIMIT ?",
            f"%{query.lower()}%", limit,
        )
    return [_user_row(r) for r in rows]


async def export_users() -> list[dict]:
    rows = await _db().fetchall(f"SELECT {_USER_COLUMNS} FROM users ORDER BY id")
    return [_user_row(r) for r in rows]


# ── Web ilova (admin paneli) ────────────────────────────────────────────────
async def daily_series(since_day: str) -> dict[str, dict[str, int]]:
    """{"YYYY-MM-DD": {"new": N, "active": M}} — since_day dan bugungacha (bo'sh kunlar yo'q)."""
    series: dict[str, dict[str, int]] = {}
    for day, n in await _db().fetchall(
        "SELECT substr(joined_date, 1, 10) AS d, COUNT(*) FROM users WHERE joined_date >= ? GROUP BY d", since_day
    ):
        series.setdefault(str(day), {"new": 0, "active": 0})["new"] = int(n)
    for day, n in await _db().fetchall(
        "SELECT day, COUNT(*) FROM daily_activity WHERE day >= ? GROUP BY day", since_day
    ):
        series.setdefault(str(day), {"new": 0, "active": 0})["active"] = int(n)
    return series


async def returning_users(since: str) -> int:
    """`since` dan oldin qo'shilib, shu davrda yana faol bo'lganlar (qaytib kelganlar)."""
    return await _count("SELECT COUNT(*) FROM users WHERE last_active >= ? AND joined_date < ?", since, since)


_USER_SORTS = {
    "active": "COALESCE(last_active, '') DESC",
    "joined": "id DESC",
    "usage": "COALESCE(usage_count, 0) DESC",
}


async def list_users(query: str = "", sort: str = "active", limit: int = 50, offset: int = 0) -> tuple[int, list[dict]]:
    order = _USER_SORTS.get(sort, _USER_SORTS["active"])
    query = query.strip().lstrip("@")
    if query.isdigit():
        where, args = "WHERE CAST(telegram_id AS TEXT) LIKE ?", (f"{query}%",)
    elif query:
        where, args = "WHERE LOWER(full_name) LIKE ?", (f"%{query.lower()}%",)
    else:
        where, args = "", ()
    total = await _count(f"SELECT COUNT(*) FROM users {where}", *args)
    rows = await _db().fetchall(
        f"SELECT {_USER_COLUMNS} FROM users {where} ORDER BY {order}, id DESC LIMIT ? OFFSET ?",
        *args, max(1, min(limit, 200)), max(0, offset),
    )
    return total, [_user_row(r) for r in rows]


# ── Bir martalik belgilar (tanishuv, maslahatlar, qaytish eslatmasi) ───────
async def set_flag(telegram_id: int, flag: str) -> bool:
    """Belgi qo'yadi. Yangi bo'lsa True (oldin qo'yilgan bo'lsa False)."""
    return await _db().execute(
        "INSERT INTO user_flags (user_id, flag, created) VALUES (?, ?, ?) ON CONFLICT (user_id, flag) DO NOTHING",
        telegram_id, flag, now_tashkent().strftime(DB_FORMAT),
    ) == 1


async def has_flag(telegram_id: int, flag: str) -> bool:
    return await _db().fetchone("SELECT 1 FROM user_flags WHERE user_id = ? AND flag = ?", telegram_id, flag) is not None


async def count_flags(telegram_id: int, prefix: str) -> int:
    return await _count("SELECT COUNT(*) FROM user_flags WHERE user_id = ? AND flag LIKE ?", telegram_id, prefix + "%")


async def flag_stats(prefix: str, since: str) -> list[tuple[str, int]]:
    """Masalan, "onb:" — yangi kelganlar tanishuvda nimani tanlagani."""
    rows = await _db().fetchall(
        "SELECT flag, COUNT(*) FROM user_flags WHERE flag LIKE ? AND created >= ? GROUP BY flag ORDER BY COUNT(*) DESC",
        prefix + "%", since,
    )
    return [(r[0][len(prefix):], int(r[1])) for r in rows]


async def onboarding_stats(since: str, now: str) -> dict:
    """`since` dan beri qo'shilganlar: birinchi sutkada bo'lim ishlatganlar va keyingi kunlarda qaytganlar."""
    from datetime import datetime as _dt
    rows = await _db().fetchall(
        "SELECT u.telegram_id, u.joined_date, MIN(s.first_used) FROM users u "
        "LEFT JOIN user_sections s ON s.user_id = u.telegram_id "
        "WHERE u.joined_date >= ? GROUP BY u.telegram_id, u.joined_date", since,
    )
    last_days = dict(await _db().fetchall(
        "SELECT d.user_id, MAX(d.day) FROM daily_activity d JOIN users u ON u.telegram_id = d.user_id "
        "WHERE u.joined_date >= ? GROUP BY d.user_id", since,
    ))

    def parse(value):
        try:
            return _dt.fromisoformat(str(value)[:19])
        except (TypeError, ValueError):
            return None

    now_dt = parse(now)
    joined = activated = eligible = returned = 0
    for uid, joined_date, first_used in rows:
        j = parse(joined_date)
        if j is None:
            continue
        joined += 1
        f = parse(first_used)
        if f is not None and (f - j).total_seconds() <= 86400:
            activated += 1
        # "Qaytdi" — qo'shilgan kunidan keyingi istalgan kunda yana faol bo'ldi (kamida 1 kun o'tganlar orasida)
        if now_dt and (now_dt - j).days >= 1:
            eligible += 1
            if str(last_days.get(uid) or "") > str(joined_date)[:10]:
                returned += 1
    return {"joined": joined, "activated": activated, "eligible": eligible, "returned": returned}


async def users_to_nudge(joined_after: str, inactive_before: str, limit: int = 500) -> list[tuple[int, str]]:
    """Yaqinda qo'shilib, keyin qaytmaganlar — hali eslatma olmagan, botni bloklamagan."""
    rows = await _db().fetchall(
        "SELECT telegram_id, COALESCE(full_name, '') FROM users "
        "WHERE joined_date >= ? AND COALESCE(last_active, joined_date) < ? "
        "AND COALESCE(bot_blocked, 0) = 0 AND COALESCE(is_banned, 0) = 0 "
        "AND telegram_id NOT IN (SELECT user_id FROM user_flags WHERE flag = 'nudge') "
        "ORDER BY joined_date, telegram_id LIMIT ?",
        joined_after, inactive_before, limit,
    )
    return [(r[0], r[1]) for r in rows]
