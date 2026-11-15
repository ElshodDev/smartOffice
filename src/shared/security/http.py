"""HTTP authentication helpers for the aiohttp presentation layer."""

from __future__ import annotations

from aiohttp import web

from src.shared.security.telegram_webapp import (
    WebAppAuthenticationError,
    extract_init_data,
    validate_init_data,
)
from src.shared.settings import Settings


def require_webapp_user(request: web.Request, settings: Settings) -> int:
    """Return the authenticated Telegram user ID or raise HTTP 401."""
    init_data = extract_init_data(request.headers)
    if not init_data:
        raise web.HTTPUnauthorized(
            text='{"error":"Authentication required"}',
            content_type="application/json",
        )

    try:
        user = validate_init_data(
            init_data,
            settings.bot_token,
            max_age_seconds=settings.webapp_init_data_max_age,
        )
    except WebAppAuthenticationError as exc:
        raise web.HTTPUnauthorized(
            text='{"error":"Invalid authentication"}',
            content_type="application/json",
        ) from exc
    return user.id


def require_admin(request: web.Request, settings: Settings) -> int:
    """Authenticate a Web App request and require the configured admin."""
    user_id = require_webapp_user(request, settings)
    if settings.admin_id is None or user_id != settings.admin_id:
        raise web.HTTPForbidden(
            text='{"error":"Forbidden"}',
            content_type="application/json",
        )
    return user_id
