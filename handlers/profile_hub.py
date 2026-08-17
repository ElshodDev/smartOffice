from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext

router = Router()

def get_profile_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="hub_settings")],
        [InlineKeyboardButton(text="📞 Aloqa va Admin", callback_data="hub_admin")]
    ])

@router.message(F.text == "👤 Profil va Sozlamalar")
async def show_profile_hub(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👤 <b>Profil va Sozlamalar</b>\n\nQaysi bo'limga kirishni xohlaysiz?",
        parse_mode="HTML",
        reply_markup=get_profile_menu()
    )

@router.callback_query(F.data == "hub_settings")
async def redirect_to_settings(callback: CallbackQuery, state: FSMContext, bot):
    from handlers.settings import show_settings
    await callback.message.delete()
    await show_settings(callback.message, bot)

@router.callback_query(F.data == "hub_admin")
async def redirect_to_admin(callback: CallbackQuery, state: FSMContext):
    from handlers.feedback import start_feedback_callback
    await callback.message.delete()
    await start_feedback_callback(callback, state)
