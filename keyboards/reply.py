from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.types.web_app_info import WebAppInfo

def get_main_menu() -> ReplyKeyboardMarkup:
    web_app_url = "https://smartoffice-moms.onrender.com/?v=4"

    keyboard = [
        [
            KeyboardButton(text="📁 Hujjatlar bilan ishlash"),
            KeyboardButton(text="🔄 Formatlar va Tarjima"),
        ],
        [
            KeyboardButton(text="🤖 AI Yordamchi (Savol-javob)"),
            KeyboardButton(text="🌐 Web Ilova", web_app=WebAppInfo(url=web_app_url)),
        ],
        [
            KeyboardButton(text="👤 Profil va Sozlamalar"),
        ],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_documents_menu() -> ReplyKeyboardMarkup:
    keyboard = [
        [
            KeyboardButton(text="📊 Excel bilan ishlash"),
            KeyboardButton(text="📄 PDF bilan ishlash"),
        ],
        [
            KeyboardButton(text="📝 Word bilan ishlash"),
            KeyboardButton(text="📋 Ma'lumotnoma (Obyektivka)"),
        ],
        [
            KeyboardButton(text="🔙 Asosiy menyu"),
        ],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_formats_menu() -> ReplyKeyboardMarkup:
    keyboard = [
        [
            KeyboardButton(text="🔄 Konvertor"),
            KeyboardButton(text="🔠 Tarjimon"),
        ],
        [
            KeyboardButton(text="🔙 Asosiy menyu"),
        ],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_profile_menu() -> ReplyKeyboardMarkup:
    keyboard = [
        [
            KeyboardButton(text="⚙️ Sozlamalar"),
            KeyboardButton(text="📞 Admin / Buyurtma"),
        ],
        [
            KeyboardButton(text="🔙 Asosiy menyu"),
        ],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
