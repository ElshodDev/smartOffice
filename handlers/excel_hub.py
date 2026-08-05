"""
Excel Asboblari — barcha Excel imkoniyatlari uchun markaziy hub.
"""
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext

router = Router()


def get_excel_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✂️ Excel qirqish (ajratish)", callback_data="xl_cut")],
        [InlineKeyboardButton(text="📊 Smart Splitter (aqlli bo'lish)", callback_data="xl_smart")],
        [InlineKeyboardButton(text="📑 Toifa bo'yicha bo'lish", callback_data="xl_cat")],
        [InlineKeyboardButton(text="📈 Dublikat tozalash", callback_data="eu_dedup")],
        [InlineKeyboardButton(text="🔗 Excel birlashtirish", callback_data="eu_merge")],
        [InlineKeyboardButton(text="📉 Grafik (Chart) yasash", callback_data="eu_chart")],
    ])


@router.message(F.text == "📊 Excel Asboblari")
async def show_excel_hub(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "📊 <b>Excel Asboblari</b>\n\n"
        "Qaysi funksiyadan foydalanmoqchisiz?",
        parse_mode="HTML",
        reply_markup=get_excel_menu()
    )


@router.callback_query(F.data == "xl_cut")
async def go_excel_cut(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    from handlers.excel_tools import ExcelSplitterStates
    await callback.message.edit_text(
        "✂️ <b>Excel qirqish</b>\n\n"
        "Excel (.xlsx/.xls) faylni yuboring. Bot uni kerakli qatorlar oralig'ida qirqib beradi.",
        parse_mode="HTML"
    )
    await state.set_state(ExcelSplitterStates.waiting_for_file)


@router.callback_query(F.data == "xl_smart")
async def go_smart_splitter(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    from handlers.smart_splitter import SmartSplitterStates
    await callback.message.edit_text(
        "📊 <b>Smart Splitter</b>\n\n"
        "Excel (.xlsx) faylni yuboring. Bot uni teng bo'laklarga ajratib beradi.",
        parse_mode="HTML"
    )
    await state.set_state(SmartSplitterStates.waiting_for_file)


@router.callback_query(F.data == "xl_cat")
async def go_category_splitter(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    from handlers.category_splitter import CategorySplitterStates
    await callback.message.edit_text(
        "📑 <b>Toifa bo'yicha bo'lish</b>\n\n"
        "Excel (.xlsx) faylni yuboring. Bot ustun nomini so'rab, har bir toifaga alohida fayl yasab beradi.",
        parse_mode="HTML"
    )
    await state.set_state(CategorySplitterStates.waiting_for_excel)
