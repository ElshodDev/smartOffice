from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.types.web_app_info import WebAppInfo

def get_main_menu() -> ReplyKeyboardMarkup:
    web_app_url = "https://smartoffice-moms.onrender.com/"

    keyboard = [
        [
            KeyboardButton(text="📊 Excel Asboblari"),
            KeyboardButton(text="📄 PDF Asboblari"),
        ],
        [
            KeyboardButton(text="📝 Word & Hujjat"),
            KeyboardButton(text="🔄 Tarjimon & Konvertor"),
        ],
        [
            KeyboardButton(text="🛠 Qulay Vositalar"),
            KeyboardButton(text="🤖 AI Yordamchi"),
        ],
        [
            KeyboardButton(text="⏰ Eslatmalar"),
            KeyboardButton(text="⚙️ Sozlamalar"),
        ],
        [
            KeyboardButton(text="📝 Ariza To'ldirish"),
            KeyboardButton(text="🌐 Web Ilova", web_app=WebAppInfo(url=web_app_url)),
        ],
        [
            KeyboardButton(text="📞 Admin / Buyurtma"),
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
