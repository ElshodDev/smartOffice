"""
Tarjimon & Konvertor — tarjima, alifbo va format o'zgartirish uchun markaziy hub.
"""
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext

router = Router()


def get_converter_hub_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Tarjimon / Alifbo o'zgartirish", callback_data="conv_hub_translate")],
        [InlineKeyboardButton(text="📁 Fayl formatini o'zgartirish", callback_data="conv_hub_format")],
    ])


@router.message(F.text == "🔄 Format o'zgartirish va Tarjima")
async def show_converter_hub(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🔄 <b>Format o'zgartirish va Tarjima</b>\n\n"
        "Qaysi funksiyadan foydalanmoqchisiz?",
        parse_mode="HTML",
        reply_markup=get_converter_hub_menu()
    )


@router.callback_query(F.data == "conv_hub_translate")
async def go_translator(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    from handlers.converter import get_direction_menu
    await callback.message.edit_text(
        "🔄 <b>Tarjimon / Alifbo</b>\n\n"
        "Yo'nalishni tanlang:",
        parse_mode="HTML",
        reply_markup=get_direction_menu()
    )


@router.callback_query(F.data == "conv_hub_format")
async def go_format_converter(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    from handlers.format_converter import get_converter_menu
    await callback.message.edit_text(
        "📁 <b>Fayl formatini o'zgartirish</b>\n\nQaysi formatni xohlaysiz?",
        parse_mode="HTML",
        reply_markup=get_converter_menu()
    )
