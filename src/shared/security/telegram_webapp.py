"""Telegram Web App initData authentication."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import parse_qsl


class WebAppAuthenticationError(ValueError):
    """Raised when Telegram Web App credentials are invalid."""


@dataclass(frozen=True, slots=True)
class TelegramWebAppUser:
    id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None


def validate_init_data(
    init_data: str,
    bot_token: str,
    *,
    max_age_seconds: int = 86_400,
    now: int | None = None,
) -> TelegramWebAppUser:
    """Validate Telegram's signed initData and return the authenticated user."""
    if not init_data or not bot_token:
        raise WebAppAuthenticationError("Missing Web App credentials")

    fields = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = fields.pop("hash", None)
    if not received_hash:
        raise WebAppAuthenticationError("Missing initData hash")

    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(fields.items())
    )
    secret_key = hmac.new(
        b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256
    ).digest()
    expected_hash = hmac.new(
        secret_key, data_check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(received_hash, expected_hash):
        raise WebAppAuthenticationError("Invalid initData signature")

    try:
        auth_date = int(fields["auth_date"])
        user_payload = json.loads(fields["user"])
        user_id = int(user_payload["id"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise WebAppAuthenticationError("Malformed initData") from exc

    current_time = int(time.time()) if now is None else now
    if auth_date > current_time or current_time - auth_date > max_age_seconds:
        raise WebAppAuthenticationError("Expired initData")

    return TelegramWebAppUser(
        id=user_id,
        username=user_payload.get("username"),
        first_name=user_payload.get("first_name"),
        last_name=user_payload.get("last_name"),
    )


def extract_init_data(headers: Mapping[str, str]) -> str | None:
    """Read initData from the canonical header, with Bearer compatibility."""
    value = headers.get("X-Telegram-Init-Data")
    if value:
        return value

    authorization = headers.get("Authorization", "")
    if authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ").strip() or None
    return None
