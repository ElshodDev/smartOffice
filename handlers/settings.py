import html
import logging

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest

from config import CHANNEL_ID
from services.alphabet import esc as uesc, raw

router = Router()

from services import botinfo

BOT_VERSION = botinfo.VERSION
BOT_NAME = botinfo.NAME

FEATURES = [
    "📊 Excel — qirqish, bo'laklarga va ustun bo'yicha bo'lish, dublikat, birlashtirish, grafik, qidiruv",
    "📄 PDF — birlashtirish, sahifalarni ajratish, watermark",
    "📝 Word — shablon to'ldirish (bitta va Excel ro'yxatdan ommaviy), o'qish",
    "✍️ Rasmiy hujjatlar — ariza, tushuntirish xati, dalolatnoma, tavsifnoma, buyruq",
    "🖊 Blankani to'ldirish va imzolash · 📋 Obyektivka",
    "📁 Formatlar — PDF↔Word/rasm, skaner, OCR, PDF siqish, HEIC→JPG, QR kod",
    "🔤 Tarjimon — UZ↔EN↔RU, Lotin↔Kirill, yangi lotin alifbosi",
    "🤖 AI Yordamchi (Gemini) · ⏰ Eslatmalar · 🌐 Web ilova",
]


def get_settings_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Ma'lumotlarni yangilash", callback_data="settings_refresh")],
        [InlineKeyboardButton(text="ℹ️ Bot haqida", callback_data="settings_about")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="profile_menu")],
    ])


async def build_settings_text(bot: Bot, user) -> str:
    sub_status = "❓ Noma'lum"
    if CHANNEL_ID:
        try:
            member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user.id)
            sub_status = "✅ Obuna bo'lgan" if member.status in ("member", "administrator", "creator") else "❌ Obuna bo'lmagan"
        except TelegramBadRequest:
            sub_status = "⚠️ Tekshirib bo'lmadi"
        except Exception as e:
            logging.error(f"Obuna tekshirishda xatolik: {e}")
            sub_status = "⚠️ Tekshirib bo'lmadi"

    username = f"@{user.username}" if user.username else "Yo'q"
    lang = user.language_code.upper() if user.language_code else "Noma'lum"
    return (
        f"⚙️ <b>Sozlamalar va profil</b>\n"
        f"{'─' * 28}\n\n"
        f"👤 <b>Ism:</b> {uesc(user.full_name)}\n"
        f"🆔 <b>Telegram ID:</b> <code>{user.id}</code>\n"
        f"📱 <b>Username:</b> {uesc(username)}\n"
        f"🌐 <b>Telegram tili:</b> {html.escape(lang)}\n\n"
        f"📣 <b>Kanal obunasi:</b> {sub_status}\n"
        f"{'─' * 28}\n\n"
        f"🔤 <b>Bot yozuvi:</b> yangi lotin alifbosi\n"
        f"🤖 <b>Bot:</b> {BOT_NAME} @{botinfo.username()}\n"
        f"📦 <b>Versiya:</b> {BOT_VERSION}"
    )


@router.message(F.text == "⚙️ Sozlamalar")
async def show_settings(message: Message, bot: Bot):
    text = await build_settings_text(bot, message.from_user)
    await message.answer(text, parse_mode="HTML", reply_markup=get_settings_menu())


@router.callback_query(F.data == "settings_refresh")
async def refresh_settings(callback: CallbackQuery, bot: Bot):
    await callback.answer("Yangilanmoqda...")
    text = await build_settings_text(bot, callback.from_user)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_settings_menu())
    except TelegramBadRequest:
        pass  # matn o'zgarmagan


@router.callback_query(F.data == "settings_about")
async def show_about(callback: CallbackQuery):
    features = "\n".join(f"  • {f}" for f in FEATURES)
    about = (
        f"ℹ️ <b>{BOT_NAME} haqida</b>\n"
        f"{'─' * 28}\n\n"
        f"<b>{BOT_NAME}</b> — ofis ishlarini avtomatlashtirishga mo'ljallangan Telegram yordamchisi.\n\n"
        f"🛠 <b>Imkoniyatlar:</b>\n{features}\n\n"
        f"📦 <b>Versiya:</b> {BOT_VERSION}\n\n"
        f"💡 <i>Taklif va savollar uchun: 👤 Profil → 📞 Adminga murojaat.</i>"
    )
    await callback.message.edit_text(
        about, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="⬅️ Orqaga", callback_data="settings_refresh")
        ]]),
    )
    await callback.answer()
