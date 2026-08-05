from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_subscription_menu(channel_url: str) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(text="📣 Kanalga a'zo bo'lish", url=channel_url)
        ],
        [
            InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_subscription")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
