"""
📞 Adminga murojaat: foydalanuvchi yozadi → admin'ga boradi → admin shu xabarga Reply qilsa,
javob (matn, rasm, fayl) foydalanuvchiga yetkaziladi.
"""
import html
import logging
import re

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from config import ADMIN_ID
from services.alphabet import esc as uesc, raw

router = Router()

MAX_FEEDBACK = 2000
ID_MARKER = re.compile(r"🆔 ID:\s*(\d+)")

ASK_TEXT = (
    "📞 <b>Adminga murojaat</b>\n\n"
    "Savolingiz, taklifingiz yoki buyurtmangizni batafsil yozib yuboring.\n"
    "Xato chiqqan bo'lsa — ekran rasmini (skrinshot) ham yuborishingiz mumkin.\n"
    "<i>Xabaringiz to'g'ridan-to'g'ri adminga yetkaziladi, javob shu chatga keladi.</i>"
)


class FeedbackStates(StatesGroup):
    waiting_for_feedback = State()


@router.message(F.text.in_({"📞 Adminga murojaat", "📞 Admin / Buyurtma"}))
async def start_feedback(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(ASK_TEXT, parse_mode="HTML")
    await state.set_state(FeedbackStates.waiting_for_feedback)


@router.callback_query(F.data.in_({"feedback_start", "settings_feedback"}))
async def start_feedback_cb(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        ASK_TEXT, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="⬅️ Orqaga", callback_data="profile_menu")
        ]]),
    )
    await state.set_state(FeedbackStates.waiting_for_feedback)


def _admin_header(user) -> str:
    username = f"@{user.username}" if user.username else "yo'q"
    return (
        f"📩 <b>Yangi murojaat</b>\n\n"
        f"👤 <b>Foydalanuvchi:</b> {uesc(user.full_name)}\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"📱 <b>Username:</b> {uesc(username)}\n\n"
    )


REPLY_HINT = "<i>💬 Javob berish uchun shu xabarga Reply qiling (matn, rasm yoki fayl).</i>"
MAX_CAPTION_TEXT = 600   # Telegram izoh (caption) chegarasi 1024 belgi


@router.message(FeedbackStates.waiting_for_feedback, F.text | F.photo | F.document | F.voice | F.video)
async def process_feedback(message: Message, state: FSMContext, bot: Bot):
    text = (message.text or message.caption or "").strip()
    if message.text and text.startswith("/"):
        return
    if message.text and len(text) > MAX_FEEDBACK:
        await message.answer(f"❌ Xabar juda uzun ({len(text)} belgi). {MAX_FEEDBACK} belgigacha qisqartiring:")
        return
    if not ADMIN_ID:
        await message.answer("Kechirasiz, hozirda admin bilan bog'lanish imkoni yo'q.")
        await state.clear()
        return

    # Foydalanuvchi yozgan hamma narsa esc() qilinadi — aks holda "<" yoki "&" xabarni buzadi
    header = _admin_header(message.from_user)
    try:
        if message.text:
            await bot.send_message(chat_id=int(ADMIN_ID), text=f"{header}{uesc(text)}\n\n{REPLY_HINT}",
                                   parse_mode="HTML")
        else:
            if len(text) > MAX_CAPTION_TEXT:
                text = text[:MAX_CAPTION_TEXT] + "…"
            await bot.copy_message(chat_id=int(ADMIN_ID), from_chat_id=message.chat.id,
                                   message_id=message.message_id,
                                   caption=f"{header}{uesc(text)}\n\n{REPLY_HINT}", parse_mode="HTML")
        await message.answer("✅ Murojaatingiz adminga yuborildi! Javob shu chatga keladi.")
    except Exception as e:
        logging.error(f"Adminga xabar yuborishda xato: {e}")
        await message.answer("❌ Xatolik yuz berdi. Keyinroq urinib ko'ring.")
    finally:
        await state.clear()


def _is_admin_reply_to_feedback(message: Message) -> bool:
    if not ADMIN_ID or str(message.chat.id) != str(ADMIN_ID).lstrip("@"):
        return False
    original = message.reply_to_message
    return bool(original and original.from_user and original.from_user.is_bot
                and ID_MARKER.search(original.text or original.caption or ""))


@router.message(F.func(_is_admin_reply_to_feedback))
async def admin_reply_to_user(message: Message, bot: Bot):
    """Admin murojaat xabariga Reply qilganda — javobni foydalanuvchiga yetkazadi."""
    original = message.reply_to_message
    user_id = int(ID_MARKER.search(original.text or original.caption or "").group(1))
    try:
        await bot.send_message(chat_id=user_id, text="📬 <b>Admin javobi:</b>", parse_mode="HTML")
        await bot.copy_message(chat_id=user_id, from_chat_id=message.chat.id, message_id=message.message_id)
        await message.reply("✅ Javob foydalanuvchiga yetkazildi.")
    except Exception as e:
        logging.error(f"Foydalanuvchiga javob yuborishda xato: {e}")
        await message.reply("❌ Javob yuborilmadi — foydalanuvchi botni bloklagan bo'lishi mumkin.")
