"""
Ariza to'ldirish — Foydalanuvchi rasm yuboradi,
bot Web Ilova orqali tahrirlash havolasini beradi.
"""
import os
import uuid
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types.web_app_info import WebAppInfo
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import RENDER_URL
from services.database import create_form_session

router = Router()
logger = logging.getLogger(__name__)

TEMP_DIR = "temp/forms"
os.makedirs(TEMP_DIR, exist_ok=True)


class FormFillerStates(StatesGroup):
    waiting_for_image = State()


@router.message(F.text == "📝 Ariza To'ldirish")
async def form_filler_start(message: Message, state: FSMContext):
    await state.set_state(FormFillerStates.waiting_for_image)
    await message.answer(
        "📝 <b>Ariza To'ldirish</b>\n\n"
        "Ariza yoki blanka rasmini yuboring (foto yoki fayl sifatida).\n\n"
        "<i>Men sizga interaktiv tahrirlash oynasini ochaman — "
        "u yerda ustiga matn yozib, sana va imzongizni qo'shishingiz mumkin.</i>",
        parse_mode="HTML"
    )


@router.message(FormFillerStates.waiting_for_image, F.photo)
async def handle_form_photo(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    await message.answer("⏳ Rasm tayyorlanmoqda...")

    try:
        # Eng katta o'lchamdagi rasmni olish
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_id = uuid.uuid4().hex
        filename = f"{file_id}.jpg"
        filepath = os.path.join(TEMP_DIR, filename)

        await bot.download_file(file.file_path, destination=filepath)

        token = await create_form_session(message.from_user.id, filename)
        editor_url = f"{RENDER_URL}/form-editor?img={filename}&token={token}"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="✏️ Tahrirlash — Matn va Imzo Qo'shish",
                web_app=WebAppInfo(url=editor_url)
            )]
        ])

        await message.answer(
            "✅ <b>Ariza rasmi qabul qilindi!</b>\n\n"
            "Quyidagi tugmani bosing va:\n"
            "• Xohlagan joyga <b>matn yozing</b>\n"
            "• <b>Sanani</b> kiriting\n"
            "• Barmoq bilan <b>imzo chekib</b> qo'ying\n"
            "• Tayyor bo'lgach <b>Saqlash</b> tugmasini bosing\n\n"
            "<i>📎 Tayyor hujjat PDF shaklida yuboriladi.</i>",
            parse_mode="HTML",
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Form filler error: {e}")
        await message.answer("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")


@router.message(FormFillerStates.waiting_for_image, F.document)
async def handle_form_document(message: Message, state: FSMContext, bot: Bot):
    """Fayl sifatida yuborilgan rasm"""
    doc = message.document
    if not doc.mime_type or not doc.mime_type.startswith("image/"):
        await message.answer("⚠️ Iltimos, faqat rasm fayl yuboring (JPG, PNG).")
        return

    await state.clear()
    await message.answer("⏳ Rasm tayyorlanmoqda...")

    try:
        file = await bot.get_file(doc.file_id)
        ext = doc.file_name.split(".")[-1] if "." in doc.file_name else "jpg"
        file_id = uuid.uuid4().hex
        filename = f"{file_id}.{ext}"
        filepath = os.path.join(TEMP_DIR, filename)

        await bot.download_file(file.file_path, destination=filepath)

        token = await create_form_session(message.from_user.id, filename)
        editor_url = f"{RENDER_URL}/form-editor?img={filename}&token={token}"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="✏️ Tahrirlash — Matn va Imzo Qo'shish",
                web_app=WebAppInfo(url=editor_url)
            )]
        ])

        await message.answer(
            "✅ <b>Ariza rasmi qabul qilindi!</b>\n\n"
            "Quyidagi tugmani bosing va:\n"
            "• Xohlagan joyga <b>matn yozing</b>\n"
            "• <b>Sanani</b> kiriting\n"
            "• Barmoq bilan <b>imzo chekib</b> qo'ying\n"
            "• Tayyor bo'lgach <b>Saqlash</b> tugmasini bosing\n\n"
            "<i>📎 Tayyor hujjat PDF shaklida yuboriladi.</i>",
            parse_mode="HTML",
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Form filler doc error: {e}")
        await message.answer("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")
