from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.types.web_app_info import WebAppInfo
from config import RENDER_URL

def get_main_menu() -> ReplyKeyboardMarkup:
    web_app_url = f"{RENDER_URL.rstrip('/')}/?v=4"

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
            KeyboardButton(text="🌐 Web Ilova", web_app=WebAppInfo(url=web_app_url)),
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
