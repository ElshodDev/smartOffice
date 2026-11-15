from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext

router = Router()

def get_documents_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Excel", callback_data="hub_excel"), InlineKeyboardButton(text="📄 PDF", callback_data="hub_pdf")],
        [InlineKeyboardButton(text="📝 Word", callback_data="hub_word"), InlineKeyboardButton(text="📋 Obyektivka", callback_data="hub_obyektivka")],
        [InlineKeyboardButton(text="✍️ Rasmiy hujjat yaratish", callback_data="docgen")],
        [InlineKeyboardButton(text="🖊 Blankani to'ldirish va imzolash", callback_data="form_fill")],
    ])

@router.message(F.text == "📁 Hujjatlar bilan ishlash")
async def show_documents_hub(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "📁 <b>Hujjatlar bilan ishlash</b>\n\nQaysi hujjat turini tanlaysiz?",
        parse_mode="HTML",
        reply_markup=get_documents_menu()
    )

@router.callback_query(F.data == "hub_excel")
async def redirect_to_excel(callback: CallbackQuery, state: FSMContext):
    from handlers.excel_hub import get_excel_menu
    await callback.message.edit_text(
        "📊 <b>Excel bilan ishlash</b>\n\nQaysi amaliyotni bajarmoqchisiz?",
        parse_mode="HTML",
        reply_markup=get_excel_menu()
    )

@router.callback_query(F.data == "hub_pdf")
async def redirect_to_pdf(callback: CallbackQuery, state: FSMContext):
    from handlers.pdf_tools import get_pdf_menu
    await callback.message.edit_text(
        "📄 <b>PDF bilan ishlash</b>\n\nQaysi amaldan foydalanasiz?",
        parse_mode="HTML",
        reply_markup=get_pdf_menu()
    )

@router.callback_query(F.data == "hub_word")
async def redirect_to_word(callback: CallbackQuery, state: FSMContext):
    from handlers.word_tools import get_word_menu
    await callback.message.edit_text(
        "📝 <b>Word bilan ishlash</b>\n\nQaysi amaldan foydalanasiz?",
        parse_mode="HTML",
        reply_markup=get_word_menu()
    )

@router.callback_query(F.data == "hub_obyektivka")
async def redirect_to_obyektivka(callback: CallbackQuery, state: FSMContext):
    # Avval bu tugma xato bilan «Blankani to'ldirish» ni ochardi
    from handlers.report_generator import start_report_cb
    await start_report_cb(callback, state)
