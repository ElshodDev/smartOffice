"""Web App form image delivery and secure PDF submission."""

from __future__ import annotations

import base64
import binascii
import io
import logging
import os
from typing import Any

from aiohttp import web
from PIL import Image

from services.database import (
    cleanup_expired_form_sessions,
    consume_form_session,
    get_form_session,
)
from src.shared.security.http import require_webapp_user
from src.shared.settings import Settings, get_settings

logger = logging.getLogger(__name__)

TEMP_DIR = "temp/forms"
os.makedirs(TEMP_DIR, exist_ok=True)


class ImageEditorService:
    """Owns Web App form delivery without process-global bot state."""

    def __init__(self, bot: Any, settings: Settings | None = None) -> None:
        self._bot = bot
        self._settings = settings or get_settings()

    async def serve_form_image(self, request: web.Request) -> web.Response:
        await self._cleanup_expired_files()
        filename = request.match_info.get("filename", "")
        if not filename or os.path.basename(filename) != filename:
            raise web.HTTPForbidden()

        session = await get_form_session(request.query.get("token", ""))
        if not session or session["filename"] != filename:
            raise web.HTTPNotFound()

        filepath = os.path.join(TEMP_DIR, filename)
        if not os.path.isfile(filepath):
            raise web.HTTPNotFound()
        return web.FileResponse(filepath)

    async def serve_form_editor(self, request: web.Request) -> web.Response:
        from services.alphabet import load_page
        return web.Response(text=load_page("./webapp/editor.html"), content_type="text/html",
                            headers={"Cache-Control": "no-cache"})

    async def receive_edited_form(self, request: web.Request) -> web.Response:
        try:
            await self._cleanup_expired_files()
            authenticated_user_id = require_webapp_user(request, self._settings)
            data = await request.json()
            image_base64 = data.get("image")
            token = data.get("token")
            original_filename = os.path.basename(
                str(data.get("filename", "form"))
            )
            requested_chat_id = data.get("chat_id")

            if requested_chat_id is not None:
                if int(requested_chat_id) != authenticated_user_id:
                    raise web.HTTPForbidden()
            if not isinstance(image_base64, str) or not image_base64:
                return web.json_response(
                    {"ok": False, "error": "Missing image"}, status=400
                )
            session = await get_form_session(str(token or ""))
            if not session or session["user_id"] != authenticated_user_id:
                raise web.HTTPForbidden()
            filename = session["filename"]
            if original_filename == "form":
                original_filename = filename

            encoded_image = image_base64.split("base64,", 1)[-1]
            image_bytes = base64.b64decode(encoded_image, validate=True)
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

            pdf_buffer = io.BytesIO()
            # Sahifa A4 (210×297 mm) ga sig'adigan qilib: rasm qancha katta bo'lsa, dpi shuncha yuqori
            dpi = max(72.0, image.width / 8.27, image.height / 11.69)
            image.save(pdf_buffer, format="PDF", resolution=dpi)
            pdf_buffer.seek(0)

            from aiogram.types import BufferedInputFile

            if not await consume_form_session(
                str(token), authenticated_user_id, filename
            ):
                return web.json_response(
                    {"ok": False, "error": "Form session expired"}, status=409
                )

            await self._bot.send_document(
                chat_id=authenticated_user_id,
                document=BufferedInputFile(
                    pdf_buffer.read(),
                    filename="blanka_tayyor.pdf",
                ),
                caption=(
                    "✅ <b>Hujjat tayyor!</b>\n\n"
                    "📎 Matn va imzo qo'yilgan blanka PDF shaklida yuqorida.\n"
                    "<i>Uni printerda chop etishingiz yoki elektron jo'natishingiz mumkin.</i>"
                ),
                parse_mode="HTML",
            )
            return web.json_response({"ok": True})
        except web.HTTPException:
            raise
        except (ValueError, TypeError, binascii.Error, Image.DecompressionBombError):
            return web.json_response(
                {"ok": False, "error": "Invalid form data"}, status=400
            )
        except Exception:
            logger.exception("Failed to process edited form")
            return web.json_response(
                {"ok": False, "error": "Internal server error"}, status=500
            )

    async def _cleanup_expired_files(self) -> None:
        for filename in await cleanup_expired_form_sessions():
            filepath = os.path.join(TEMP_DIR, os.path.basename(filename))
            try:
                if os.path.isfile(filepath):
                    os.remove(filepath)
            except OSError:
                logger.warning("Could not remove expired form file: %s", filepath)
