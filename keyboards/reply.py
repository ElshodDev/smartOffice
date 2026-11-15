from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types.web_app_info import WebAppInfo
from config import RENDER_URL

WEB_APP_BUTTON = "🌐 Web Ilova"


def web_app_url() -> str:
    return f"{RENDER_URL.rstrip('/')}/?v=6"


def web_app_inline() -> InlineKeyboardMarkup:
    """Web ilova xabar ichidagi tugma orqali ochiladi: pastki klaviatura tugmasidan ochilganda
    Telegram foydalanuvchi ma'lumotini (initData) bermaydi va ilova kim kirganini bila olmaydi."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🌐 Web ilovani ochish", web_app=WebAppInfo(url=web_app_url()))
    ]])


def get_main_menu() -> ReplyKeyboardMarkup:
    keyboard = [
        [
            KeyboardButton(text="📁 Hujjatlar bilan ishlash")
        ],
        [
            KeyboardButton(text="🔤 Tarjimon va Alifbo"),
            KeyboardButton(text="📁 Format o'zgartirish"),
        ],
        [
            KeyboardButton(text="🤖 AI Yordamchi (Savol-javob)"),
            KeyboardButton(text="👤 Profil va Sozlamalar"),
        ],
        [
            KeyboardButton(text=WEB_APP_BUTTON),
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
