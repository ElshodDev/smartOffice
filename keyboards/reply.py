from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.types.web_app_info import WebAppInfo

def get_main_menu() -> ReplyKeyboardMarkup:
    web_app_url = "https://smartoffice-moms.onrender.com/?v=3"

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
            KeyboardButton(text="📋 Obyektivka Yaratish"),
            KeyboardButton(text="📞 Admin / Buyurtma"),
        ],
        [
            KeyboardButton(text="💳 Premium"),
            KeyboardButton(text="🛒 Xizmatlarim"),
        ],
        [
            KeyboardButton(text="🔗 Ulashish"),
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
