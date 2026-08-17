"""
Word & Hujjat — barcha Word va hujjat imkoniyatlari uchun markaziy hub.
"""
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext

router = Router()


def get_word_hub_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Word shablonni ma'lumotlar bilan to'ldirish", callback_data="word_fill_template")],
        [InlineKeyboardButton(text="📖 Word hujjatni bot ichida o'qish", callback_data="word_read")],
    ])


@router.message(F.text == "📝 Word bilan ishlash")
async def show_word_hub(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "📝 <b>Word bilan ishlash</b>\n\n"
        "Qaysi funksiyadan foydalanmoqchisiz?",
        parse_mode="HTML",
        reply_markup=get_word_hub_menu()
    )
