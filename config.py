"""Backward-compatible configuration exports.

New code should depend on ``src.shared.settings.get_settings`` instead of
reading environment variables directly.
"""

from src.shared.settings import get_settings

settings = get_settings()

BOT_TOKEN = settings.bot_token
ADMIN_ID = str(settings.admin_id) if settings.admin_id is not None else None
CHANNEL_ID = settings.channel_id
RENDER_URL = settings.render_url
