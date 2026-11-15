"""
🌐 Web ilova API (Telegram imzolagan initData bilan himoyalangan).

GET /api/me                 — foydalanuvchining profili, bo'limlar xaritasi, taklif havolasi
GET /api/admin/dashboard    — admin: statistika, 30 kunlik grafik, mashhur bo'limlar
GET /api/admin/users        — admin: foydalanuvchilar ro'yxati (?q=&sort=active|joined|usage&offset=)
"""
from __future__ import annotations

import logging
from datetime import timedelta

from aiohttp import web

from services import activity, botinfo, database, gemini
from services.alphabet import convert
from services.timeutil import now_tashkent, DB_FORMAT
from src.shared.security.http import require_admin, require_webapp_user
from src.shared.settings import get_settings

# Daraja: amallar soni bo'yicha (bitta bo'limdan 30 daqiqa ichida foydalanish = 1 amal)
LEVELS = [(0, "🌱 Yangi"), (5, "🥉 Faol"), (20, "🥈 Tajribali"), (50, "🥇 Usta"), (100, "💎 Ekspert")]

# Bo'limlar xaritasidagi tartib
MAP_ORDER = ["scan", "docgen", "obyektivka", "translate", "format", "excel", "word", "pdf",
             "ocr", "blanka", "search", "reminders", "qr"]


def level_info(uses: int) -> dict:
    current = LEVELS[0]
    nxt = None
    for i, (threshold, label) in enumerate(LEVELS):
        if uses >= threshold:
            current = (threshold, label)
            nxt = LEVELS[i + 1] if i + 1 < len(LEVELS) else None
    progress = 100 if nxt is None else round((uses - current[0]) * 100 / (nxt[0] - current[0]))
    return {"label": convert(current[1]), "next_label": convert(nxt[1]) if nxt else None,
            "to_next": (nxt[0] - uses) if nxt else 0, "progress": progress}


def _iso(value: str) -> str:
    """'2026-11-15 10:00:00' → '2026-11-15T10:00:00+05:00' (har qanday brauzer, jumladan iPhone tushunadi)."""
    if not value:
        return ""
    return value[:19].replace(" ", "T") + "+05:00"


def _is_admin(user_id: int) -> bool:
    admin = get_settings().admin_id
    return admin is not None and user_id == admin


def _catalog() -> list[dict]:
    from handlers.ai_assistant import SECTIONS
    items = []
    for key in MAP_ORDER:
        if key in SECTIONS:
            title, desc, _ = SECTIONS[key]
            items.append({"key": key, "title": convert(title), "desc": convert(desc)})
    return items


async def api_me(request: web.Request) -> web.Response:
    user_id = require_webapp_user(request, get_settings())
    try:
        profile = await database.get_user_profile(user_id)
        sections = await database.get_user_sections(user_id)
        for sec, n in activity.pending_sections_for(user_id).items():
            sections[sec] = sections.get(sec, 0) + n
        uses = sum(sections.values())
        catalog = _catalog()
        for item in catalog:
            item["uses"] = sections.get(item["key"], 0)
        favourite = max(sections.items(), key=lambda kv: kv[1])[0] if sections else None
        return web.json_response({
            "registered": profile is not None,
            "name": (profile or {}).get("name") or "",
            "joined": _iso((profile or {}).get("joined_date") or ""),
            "uses": uses,
            "level": level_info(uses),
            "sections": catalog,
            "tried": sum(1 for item in catalog if item["uses"]),
            "favourite": convert(activity.SECTION_TITLES.get(favourite, "")) if favourite else "",
            "referrals": await database.count_referrals(user_id),
            "reminders": await database.count_active_reminders(user_id),
            "ai_left": gemini.remaining(user_id, _is_admin(user_id)) if gemini.is_enabled() else None,
            "ai_limit": gemini.daily_limit(),
            "invite_link": f"https://t.me/{botinfo.username()}?start={user_id}",
            "bot_username": botinfo.username(),
            "is_admin": _is_admin(user_id),
        })
    except Exception:
        logging.exception("Web ilova: /api/me xatosi")
        return web.json_response({"error": "Internal server error"}, status=500)


async def api_admin_dashboard(request: web.Request) -> web.Response:
    require_admin(request, get_settings())
    try:
        await activity.flush()
        now = now_tashkent()
        day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week, month = day - timedelta(days=6), day - timedelta(days=29)
        stats = await database.admin_stats(day.strftime(DB_FORMAT), week.strftime(DB_FORMAT), month.strftime(DB_FORMAT))
        stats["returning_week"] = await database.returning_users(week.strftime(DB_FORMAT))
        raw_series = await database.daily_series(month.strftime("%Y-%m-%d"))
        series = []
        for i in range(30):
            d = (month + timedelta(days=i)).strftime("%Y-%m-%d")
            point = raw_series.get(d, {"new": 0, "active": 0})
            series.append({"day": d, "new": point["new"], "active": point["active"]})
        ai_requests, ai_users = gemini.usage_today()
        sections = [{"key": k, "title": convert(activity.SECTION_TITLES.get(k, k)), "users": u, "uses": n}
                    for k, u, n in await database.top_sections(since=week.strftime(DB_FORMAT), limit=14)]
        referrers = [{"id": uid, "name": name, "count": n} for uid, name, n in await database.top_referrers(5)]
        from services.onboarding import CHOICES
        titles = dict(CHOICES) | {"all": "🧭 Hammasini ko'rish"}
        onboarding = await database.onboarding_stats(month.strftime(DB_FORMAT), now.strftime(DB_FORMAT))
        onboarding["picks"] = [{"title": convert(titles.get(k, k)), "count": n}
                               for k, n in await database.flag_stats("onb:", month.strftime(DB_FORMAT))]
        return web.json_response({
            "stats": stats, "series": series, "sections": sections, "referrers": referrers, "onboarding": onboarding,
            "ai": {"requests": ai_requests, "users": ai_users},
            "generated": now.strftime("%d.%m.%Y %H:%M"),
        })
    except Exception:
        logging.exception("Web ilova: dashboard xatosi")
        return web.json_response({"error": "Internal server error"}, status=500)


async def api_admin_users(request: web.Request) -> web.Response:
    require_admin(request, get_settings())
    try:
        await activity.flush()
        try:
            offset = int(request.query.get("offset", "0"))
        except ValueError:
            offset = 0
        total, users = await database.list_users(request.query.get("q", "")[:64],
                                                 request.query.get("sort", "active"), 50, offset)
        for u in users:
            u["joined"], u["last_active"] = _iso(u["joined"]), _iso(u["last_active"])
        return web.json_response({"total": total, "offset": offset, "users": users})
    except Exception:
        logging.exception("Web ilova: foydalanuvchilar ro'yxati xatosi")
        return web.json_response({"error": "Internal server error"}, status=500)


def setup_routes(app: web.Application) -> None:
    app.router.add_get("/api/me", api_me)
    app.router.add_get("/api/admin/dashboard", api_admin_dashboard)
    app.router.add_get("/api/admin/users", api_admin_users)
