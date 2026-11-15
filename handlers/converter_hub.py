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
        [InlineKeyboardButton(text="🔤 Tarjimon va Alifbo", callback_data="conv_hub_translate")],
        [InlineKeyboardButton(text="📁 Fayl formatini o'zgartirish", callback_data="conv_hub_format")],
    ])


@router.message(F.text == "📁 Format o'zgartirish")
async def show_format_converter(message: Message, state: FSMContext):
    await state.clear()
    from handlers.format_converter import get_converter_menu
    await message.answer(
        "📁 <b>Fayl formatini o'zgartirish</b>\n\nQaysi formatni xohlaysiz?",
        parse_mode="HTML",
        reply_markup=get_converter_menu()
    )


# Eski klaviaturasi qolgan foydalanuvchilar uchun (/start bosmaguncha)
@router.message(F.text == "🔄 Formatlar va Tarjima")
async def show_converter_hub(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🔄 <b>Formatlar va Tarjima</b>\n\n"
        "Qaysi funksiyadan foydalanmoqchisiz?",
        parse_mode="HTML",
        reply_markup=get_converter_hub_menu()
    )


@router.callback_query(F.data == "conv_hub_translate")
async def go_translator(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    from handlers.converter import get_direction_menu
    from handlers.converter import TRANSLATOR_TITLE
    await callback.message.edit_text(
        TRANSLATOR_TITLE,
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
