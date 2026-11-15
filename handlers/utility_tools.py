"""🔳 QR kod yaratish: matn yoki havoladan QR kod rasmi."""
import io
import logging

import qrcode
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

router = Router()

MAX_QR_TEXT = 1000   # QR kod sig'imi chegaralangan; uzun matn o'qib bo'lmaydigan darajada zich bo'ladi

FINISH_KB = InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text="✅ Tugatish", callback_data="qr_finish")
]])


class UtilityStates(StatesGroup):
    waiting_for_qr_text = State()


@router.callback_query(F.data == "util_qr")
async def ask_qr_text(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "🔳 <b>QR kod yaratish</b>\n\n"
        "Matn, havola (https://...), telefon raqami yoki Wi-Fi ma'lumotini yuboring — QR kod rasmini qaytaraman.\n"
        "<i>Bir nechta QR kodni ketma-ket yaratishingiz mumkin.</i>",
        parse_mode="HTML",
    )
    await state.set_state(UtilityStates.waiting_for_qr_text)


def make_qr_png(text: str) -> bytes:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(text)
    qr.make(fit=True)
    buf = io.BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(buf, format="PNG")
    return buf.getvalue()


@router.message(UtilityStates.waiting_for_qr_text, F.text)
async def generate_qr(message: Message):
    text = message.text.strip()
    if text.startswith("/"):
        return
    if len(text) > MAX_QR_TEXT:
        await message.answer(f"❌ Matn juda uzun ({len(text)} belgi). QR kod uchun {MAX_QR_TEXT} belgigacha yozing:")
        return
    try:
        png = make_qr_png(text)
        await message.answer_photo(BufferedInputFile(png, filename="qr.png"),
                                   caption="✅ QR kod tayyor! Yana matn yuborishingiz mumkin.", reply_markup=FINISH_KB)
    except Exception:
        logging.exception("QR yaratishda xato")
        await message.answer("❌ QR kod yaratishda xatolik yuz berdi.")


@router.callback_query(F.data == "qr_finish")
async def qr_finish(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Tugatildi")
    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
