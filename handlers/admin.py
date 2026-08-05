import logging
import asyncio
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from config import ADMIN_ID
from services.database import get_users_count, get_all_users

# ADMIN_ID ni xavfsiz int ga o'tkazish
try:
    _ADMIN_ID = int(ADMIN_ID) if ADMIN_ID else None
except (ValueError, TypeError):
    _ADMIN_ID = None

# Faqat adminni o'tkazuvchi filtr
admin_filter = F.from_user.id == _ADMIN_ID

router = Router()
router.message.filter(admin_filter)
router.callback_query.filter(admin_filter)



class AdminStates(StatesGroup):
    waiting_for_broadcast_message = State()


def get_admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats"),
            InlineKeyboardButton(text="✉️ Xabar tarqatish", callback_data="admin_broadcast")
        ]
    ])


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👑 <b>Admin Panel</b>\n\nQuyidagi amallardan birini tanlang:",
        parse_mode="HTML",
        reply_markup=get_admin_menu()
    )


@router.callback_query(F.data == "admin_stats")
async def show_stats(callback: CallbackQuery):
    await callback.answer()
    count = await get_users_count()
    await callback.message.edit_text(
        f"📊 <b>Bot Statistikasi</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{count} ta</b>\n\n"
        f"<i>Faqat /start bosgan foydalanuvchilar hisoblanadi.</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_back")]
        ])
    )


@router.callback_query(F.data == "admin_broadcast")
async def ask_broadcast_message(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "✉️ <b>Xabar tarqatish</b>\n\n"
        "Barcha foydalanuvchilarga yubormoqchi bo'lgan xabaringizni yozing.\n"
        "<i>Matn, rasm, fayl — istalgan format qabul qilinadi.</i>\n\n"
        "Bekor qilish uchun /cancel yozing.",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_broadcast_message)


@router.callback_query(F.data == "admin_back")
async def go_back_to_admin(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "👑 <b>Admin Panel</b>\n\nQuyidagi amallardan birini tanlang:",
        parse_mode="HTML",
        reply_markup=get_admin_menu()
    )


@router.message(Command("cancel"), AdminStates.waiting_for_broadcast_message)
async def cancel_broadcast(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Xabar tarqatish bekor qilindi.", reply_markup=get_admin_menu())


@router.message(AdminStates.waiting_for_broadcast_message)
async def process_broadcast(message: Message, state: FSMContext, bot: Bot):
    await state.clear()

    all_user_ids = await get_all_users()
    total = len(all_user_ids)

    if total == 0:
        await message.answer("Bazada hali foydalanuvchi yo'q.")
        return

    status_msg = await message.answer(
        f"Xabar <b>{total}</b> ta foydalanuvchiga yuborilmoqda... ⏳",
        parse_mode="HTML"
    )

    success_count = 0
    blocked_count = 0

    for user_id in all_user_ids:
        try:
            # Xabarni to'liq (rasm, fayl, matn) nusxalab yuborish
            await message.copy_to(chat_id=user_id)
            success_count += 1
        except TelegramForbiddenError:
            # Foydalanuvchi botni block qilgan — o'tkazib yuborish
            blocked_count += 1
        except TelegramBadRequest as e:
            logging.warning(f"Broadcast xatosi (user {user_id}): {e}")
            blocked_count += 1
        except Exception as e:
            logging.error(f"Broadcast — kutilmagan xato (user {user_id}): {e}")
            blocked_count += 1
        
        # Spam filtriga tushib qolmaslik uchun kichik pauza
        await asyncio.sleep(0.05)

    await status_msg.edit_text(
        f"✅ <b>Xabar tarqatish yakunlandi!</b>\n\n"
        f"📨 Yuborildi: <b>{success_count}</b> ta\n"
        f"🚫 Bloklaganlar: <b>{blocked_count}</b> ta\n"
        f"📊 Jami: <b>{total}</b> ta",
        parse_mode="HTML"
    )
