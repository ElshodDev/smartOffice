"""
Web server endpointlar: ariza rasmlarini serve qilish va
tahrirlangan PDF ni qabul qilish.
"""
import os
import uuid
import base64
import logging
import asyncio
from aiohttp import web
from PIL import Image
import io

logger = logging.getLogger(__name__)

TEMP_DIR = "temp/forms"
os.makedirs(TEMP_DIR, exist_ok=True)

# Global bot reference (main.py dan beriladi)
_bot = None
_chat_ids = {}  # file_id -> chat_id mapping


def set_bot(bot):
    global _bot
    _bot = bot


def register_chat(filename: str, chat_id: int):
    """Fayl va foydalanuvchi chat_id ni bog'lab qo'yish"""
    _chat_ids[filename] = chat_id


async def serve_form_image(request: web.Request) -> web.Response:
    """Ariza rasmini serve qilish"""
    filename = request.match_info.get("filename", "")
    # Security: faqat temp/forms papkasidan
    if ".." in filename or "/" in filename:
        raise web.HTTPForbidden()

    filepath = os.path.join(TEMP_DIR, filename)
    if not os.path.exists(filepath):
        raise web.HTTPNotFound()

    return web.FileResponse(filepath)


async def serve_form_editor(request: web.Request) -> web.Response:
    """Tahrirlash sahifasini ochish"""
    return web.FileResponse('./webapp/editor.html')


async def receive_edited_form(request: web.Request) -> web.Response:
    """
    Web App dan kelgan tahrirlangan rasmni qabul qilib,
    foydalanuvchiga PDF sifatida yuborish.
    """
    try:
        data = await request.json()
        chat_id = data.get("chat_id")
        image_base64 = data.get("image")  # base64 encoded PNG
        original_filename = data.get("filename", "form")

        if not chat_id or not image_base64:
            return web.json_response({"ok": False, "error": "Missing fields"}, status=400)

        # Base64 decode
        if "base64," in image_base64:
            image_base64 = image_base64.split("base64,")[1]

        img_bytes = base64.b64decode(image_base64)

        # PNG → PDF conversion using PIL
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        pdf_buffer = io.BytesIO()
        img.save(pdf_buffer, format="PDF", resolution=150)
        pdf_buffer.seek(0)

        # Send PDF to user via bot
        if _bot:
            from aiogram.types import BufferedInputFile
            pdf_file = BufferedInputFile(
                pdf_buffer.read(),
                filename=f"ariza_tayyor_{original_filename}.pdf"
            )
            await _bot.send_document(
                chat_id=int(chat_id),
                document=pdf_file,
                caption=(
                    "✅ <b>Ariza muvaffaqiyatli to'ldirildi!</b>\n\n"
                    "📎 Tayyor ariza PDF formatida yuqorida.\n"
                    "<i>Uni printerda chop etishingiz yoki elektron jo'natishingiz mumkin.</i>"
                ),
                parse_mode="HTML"
            )
            return web.json_response({"ok": True})
        else:
            return web.json_response({"ok": False, "error": "Bot not ready"}, status=500)

    except Exception as e:
        logger.error(f"receive_edited_form error: {e}")
        return web.json_response({"ok": False, "error": str(e)}, status=500)
