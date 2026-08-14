from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.types.web_app_info import WebAppInfo

def get_main_menu() -> ReplyKeyboardMarkup:
    web_app_url = "https://smartoffice-moms.onrender.com/?v=3"

    keyboard = [
        [
            KeyboardButton(text="📊 Excel bilan ishlash"),
            KeyboardButton(text="📄 PDF bilan ishlash"),
        ],
        [
            KeyboardButton(text="📝 Word bilan ishlash"),
            KeyboardButton(text="🔄 Format o'zgartirish va Tarjima"),
        ],
        [
            KeyboardButton(text="🛠 Boshqa qulayliklar"),
            KeyboardButton(text="🤖 AI Yordamchi (Savol-javob)"),
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
            KeyboardButton(text="📋 Ma'lumotnoma (Obyektivka)"),
            KeyboardButton(text="📞 Admin / Buyurtma"),
        ],
        [
            KeyboardButton(text="🔗 Do'stlarga ulashish"),
            KeyboardButton(text="🛒 Xizmatlarim"),
        ],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
