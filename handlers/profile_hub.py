from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext

router = Router()

PROFILE_TEXT = "👤 <b>Profil va Sozlamalar</b>\n\nQaysi bo'limga kirishni xohlaysiz?"


def get_profile_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="hub_settings"),
         InlineKeyboardButton(text="⏰ Eslatmalar", callback_data="reminders_menu")],
        [InlineKeyboardButton(text="🔗 Do'stlarga ulashish", callback_data="share_bot")],
        [InlineKeyboardButton(text="📞 Adminga murojaat", callback_data="feedback_start")],
        [InlineKeyboardButton(text="💻 Dasturchi va xizmatlar", callback_data="dev_contact")],
    ])


@router.message(F.text == "👤 Profil va Sozlamalar")
async def show_profile_hub(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(PROFILE_TEXT, parse_mode="HTML", reply_markup=get_profile_menu())


@router.callback_query(F.data == "profile_menu")
async def show_profile_hub_cb(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(PROFILE_TEXT, parse_mode="HTML", reply_markup=get_profile_menu())


@router.callback_query(F.data == "hub_settings")
async def redirect_to_settings(callback: CallbackQuery, state: FSMContext, bot):
    from handlers.settings import build_settings_text, get_settings_menu
    await callback.answer()
    text = await build_settings_text(bot, callback.from_user)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_settings_menu())
