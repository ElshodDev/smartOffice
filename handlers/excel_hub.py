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
        [InlineKeyboardButton(text="✂️ Excelni qatorlarga qirqish", callback_data="xl_cut")],
        [InlineKeyboardButton(text="📊 Excelni teng bo'laklarga bo'lish", callback_data="xl_smart")],
        [InlineKeyboardButton(text="📑 Ustunlari bo'yicha alohida fayllarga bo'lish", callback_data="xl_cat")],
        [InlineKeyboardButton(text="📈 Takrorlangan (Dublikat) ma'lumotlarni tozalash", callback_data="eu_dedup")],
        [InlineKeyboardButton(text="🔗 Bir nechta Excel fayllarni birlashtirish", callback_data="eu_merge")],
        [InlineKeyboardButton(text="📉 Ma'lumotlardan grafik (Chart) chizish", callback_data="eu_chart")],
    ])


@router.message(F.text == "📊 Excel bilan ishlash")
async def show_excel_hub(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "📊 <b>Excel bilan ishlash</b>\n\n"
        "Qaysi amaliyotni bajarmoqchisiz? Quyidagi tugmalardan birini tanlang:",
        parse_mode="HTML",
        reply_markup=get_excel_menu()
    )


@router.callback_query(F.data == "xl_cut")
async def go_excel_cut(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    from handlers.excel_tools import ExcelSplitterStates
    await callback.message.edit_text(
        "✂️ <b>Excelni qatorlarga qirqish</b>\n\n"
        "Excel (.xlsx yoki .xls) faylni menga yuboring. Men uni siz aytgan qatorlar orasida qirqib, yangi fayl qilib beraman.",
        parse_mode="HTML"
    )
    await state.set_state(ExcelSplitterStates.waiting_for_file)


@router.callback_query(F.data == "xl_smart")
async def go_smart_splitter(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    from handlers.smart_splitter import SmartSplitterStates
    await callback.message.edit_text(
        "📊 <b>Excelni teng bo'laklarga bo'lish</b>\n\n"
        "Excel faylni yuboring. Masalan mingta qatori bo'lsa, men uni 100 tadan qilib alohida fayllarga bo'lib beraman.",
        parse_mode="HTML"
    )
    await state.set_state(SmartSplitterStates.waiting_for_file)


@router.callback_query(F.data == "xl_cat")
async def go_category_splitter(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    from handlers.category_splitter import CategorySplitterStates
    await callback.message.edit_text(
        "📑 <b>Ustunlari bo'yicha alohida fayllarga bo'lish</b>\n\n"
        "Excel faylni yuboring. Menga qaysi ustun bo'yicha ajratishni aytasiz (masalan, Viloyatlar ustuni). "
        "Men har bir viloyat ma'lumotini alohida fayl qilib yuboraman.",
        parse_mode="HTML"
    )
    await state.set_state(CategorySplitterStates.waiting_for_excel)
