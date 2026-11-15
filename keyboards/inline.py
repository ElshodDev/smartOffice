from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_subscription_menu(channel_url: str) -> InlineKeyboardMarkup:
    keyboard = []
    if channel_url:   # bo'sh havola bilan tugma yuborilsa, Telegram xabarni rad etadi
        keyboard.append([InlineKeyboardButton(text="📣 Kanalga a'zo bo'lish", url=channel_url)])
    keyboard.append([InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_subscription")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
