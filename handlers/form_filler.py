"""
🖊 Blankani to'ldirish va imzolash — foydalanuvchi blanka/ariza rasmini yuboradi,
bot Web Ilova orqali ustiga matn, sana va imzo qo'yish oynasini ochadi.
"""
import logging
import os
import uuid

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types.web_app_info import WebAppInfo
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from PIL import Image, ImageOps

from config import RENDER_URL
from services.converter_service import run_heavy, MAX_FILE_SIZE, human_size, IMAGE_EXTENSIONS
from services.database import create_form_session
from services.tempfiles import new_job_dir, remove

router = Router()
logger = logging.getLogger(__name__)

TEMP_DIR = "temp/forms"
os.makedirs(TEMP_DIR, exist_ok=True)
EDITOR_MAX_SIDE = 2000   # telefon brauzerida tez ochilishi uchun

INTRO = (
    "🖊 <b>Blankani to'ldirish va imzolash</b>\n\n"
    "Ariza yoki blanka rasmini yuboring (foto yoki fayl sifatida).\n\n"
    "<i>Tahrirlash oynasini ochaman — u yerda ustiga matn yozib, sana va barmoq bilan imzo qo'yasiz. "
    "Tayyor hujjat PDF shaklida qaytadi.</i>"
)


class FormFillerStates(StatesGroup):
    waiting_for_image = State()


@router.message(F.text == "📝 Ariza To'ldirish")
async def form_filler_start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(FormFillerStates.waiting_for_image)
    await message.answer(INTRO, parse_mode="HTML")


@router.callback_query(F.data == "form_fill")
async def form_filler_start_cb(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await state.set_state(FormFillerStates.waiting_for_image)
    await callback.message.edit_text(INTRO, parse_mode="HTML")


def _normalize(src: str, dst: str) -> None:
    """Har qanday rasmni (HEIC, PNG, burilgan telefon surati) brauzer ochadigan JPG ga keltiradi."""
    with Image.open(src) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((EDITOR_MAX_SIDE, EDITOR_MAX_SIDE))
        image.save(dst, "JPEG", quality=90)


@router.message(FormFillerStates.waiting_for_image, F.photo | F.document)
async def handle_form_image(message: Message, state: FSMContext, bot: Bot):
    if message.photo:
        file, ext = message.photo[-1], ".jpg"
    else:
        file = message.document
        name = (file.file_name or "").lower()
        if not name.endswith(IMAGE_EXTENSIONS):
            await message.answer("⚠️ Iltimos, blanka rasmini yuboring (JPG, PNG, HEIC...).\n"
                                 "<i>PDF bo'lsa, avval «PDF ➡️ Rasm» orqali rasmga o'giring.</i>", parse_mode="HTML")
            return
        ext = os.path.splitext(name)[1]
    if file.file_size and file.file_size > MAX_FILE_SIZE:
        await message.answer(f"❌ Fayl juda katta ({human_size(file.file_size)}). Limit — 20 MB.")
        return

    await state.clear()
    status = await message.answer("⏳ Rasm tayyorlanmoqda...")
    job_dir = new_job_dir("form")
    try:
        raw = os.path.join(job_dir, "raw" + ext)
        await bot.download(file, destination=raw)
        filename = f"{uuid.uuid4().hex}.jpg"
        await run_heavy(_normalize, raw, os.path.join(TEMP_DIR, filename))
        token = await create_form_session(message.from_user.id, filename)
        editor_url = f"{RENDER_URL.rstrip('/')}/form-editor?img={filename}&token={token}"
        await status.edit_text(
            "✅ <b>Blanka qabul qilindi!</b>\n\n"
            "Quyidagi tugmani bosing va:\n"
            "• kerakli joylarga <b>matn yozing</b>;\n"
            "• <b>sanani</b> qo'ying;\n"
            "• barmoq bilan <b>imzo chekib</b> qo'ying;\n"
            "• tayyor bo'lgach <b>Saqlash</b> ni bosing.\n\n"
            "<i>📎 Tayyor hujjat PDF shaklida shu chatga yuboriladi.</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✏️ Tahrirlash — matn va imzo qo'shish", web_app=WebAppInfo(url=editor_url))
            ]]),
        )
    except Exception:
        logger.exception("Form filler error")
        await status.edit_text("❌ Rasmni ochib bo'lmadi. Boshqa rasm yuborib ko'ring.")
    finally:
        remove(job_dir)
