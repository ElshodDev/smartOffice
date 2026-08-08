from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
import os

router = Router()
BOT_USERNAME = os.getenv("BOT_USERNAME", "smartOffice_bot")

@router.message(F.text == "🛒 Xizmatlarim")
async def show_services(message: Message):
    await message.answer(
        "💻 <b>Dasturlash va IT Xizmatlari</b>\n\n"
        "Men quyidagi xizmatlarni taklif qilaman:\n\n"
        "1️⃣ <b>Telegram Bot Yaratish</b>\n"
        "Biznesingiz uchun aynan siz xohlagandek botlar (masalan: do'kon, admin panel, AI ulangan botlar). <i>(Narxi: kelishilgan)</i>\n\n"
        "2️⃣ <b>Web Sayt Yaratish</b>\n"
        "Zamonaviy va chiroyli veb-saytlar (Landing page, Korporativ sayt). <i>(Narxi: kelishilgan)</i>\n\n"
        "3️⃣ <b>Biznesni Avtomatlashtirish</b>\n"
        "Kompaniyangiz jarayonlarini osonlashtiruvchi CRM, hisobot generatorlari kabi tizimlar.\n\n"
        "Murojaat uchun pastdagi tugmani bosing 👇",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="📞 Dasturchi bilan aloqa", url="https://t.me/Elshod_Developer")
        ]])
    )

@router.message(F.text == "🔗 Ulashish")
async def share_bot(message: Message):
    # Foydalanuvchi uchun maxsus referral havola (agar ulashsa va boshqalar kirsa u bonus oladi)
    user_id = message.from_user.id
    share_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
    
    text_to_share = "Ajoyib bot! PDF, Excel hisobotlar va sun'iy intellekt xizmatlaridan foydalanish uchun shu yerdan kiring 👇"
    
    # Telegram share link (URL encode required for text)
    encoded_text = text_to_share.replace(" ", "%20").replace("\n", "%0A")
    telegram_share_url = f"https://t.me/share/url?url={share_link}&text={encoded_text}"
    
    await message.answer(
        "🔗 <b>Do'stlarga ulashing!</b>\n\n"
        "Do'stlaringizni botga taklif qiling va ular bilan birga foydali xizmatlardan foydalaning! 🤝\n\n"
        f"Sizning maxsus havolangiz:\n<code>{share_link}</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🚀 Do'stlarga ulashish", url=telegram_share_url)
        ]])
    )
