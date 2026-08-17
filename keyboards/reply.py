from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.types.web_app_info import WebAppInfo

def get_main_menu() -> ReplyKeyboardMarkup:
    web_app_url = "https://smartoffice-moms.onrender.com/?v=4"

    keyboard = [
        [
            KeyboardButton(text="📁 Hujjatlar bilan ishlash")
        ],
        [
            KeyboardButton(text="🔄 Formatlar va Tarjima"),
            KeyboardButton(text="🤖 AI Yordamchi (Savol-javob)"),
        ],
        [
            KeyboardButton(text="👤 Profil va Sozlamalar"),
            KeyboardButton(text="🌐 Web Ilova", web_app=WebAppInfo(url=web_app_url)),
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
