"""
Qulay Vositalar — OCR, QR kod, URL qisqartirish, Ma'lumot qidirish uchun markaziy hub.
"""
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext

router = Router()


def get_tools_hub_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖼 OCR — Rasmdan matn o'qish", callback_data="tools_ocr")],
        [InlineKeyboardButton(text="📸 QR Kod yaratish", callback_data="util_qr")],
        [InlineKeyboardButton(text="🔗 URL qisqartirish", callback_data="util_url")],
        [InlineKeyboardButton(text="🔍 Ma'lumot qidirish", callback_data="tools_search")],
    ])


@router.message(F.text == "🛠 Boshqa qulayliklar")
async def show_tools_hub(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🛠 <b>Boshqa qulayliklar</b>\n\n"
        "Qaysi funksiyadan foydalanmoqchisiz?",
        parse_mode="HTML",
        reply_markup=get_tools_hub_menu()
    )


@router.callback_query(F.data == "tools_ocr")
async def go_ocr(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    from handlers.ocr_tools import OCRStates
    await callback.message.edit_text(
        "🖼 <b>OCR — Rasmdan matn o'qish</b>\n\n"
        "Matn yozilgan rasmni yuboring (foto yoki fayl sifatida).\n"
        "<i>Inglizcha, Ruscha va O'zbekcha matnlarni taniydi.</i>",
        parse_mode="HTML"
    )
    await state.set_state(OCRStates.waiting_for_image)


@router.callback_query(F.data == "tools_search")
async def go_search(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    from handlers.search_data import SearchDataStates
    await callback.message.edit_text(
        "🔍 <b>Ma'lumot qidirish</b>\n\n"
        "Avval Excel (.xlsx) faylni yuboring, keyin qidiruv so'rovini kiritasiz:",
        parse_mode="HTML"
    )
    await state.set_state(SearchDataStates.waiting_for_file)
