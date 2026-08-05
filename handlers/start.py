from aiogram import Router, Bot, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from config import CHANNEL_ID
from keyboards.reply import get_main_menu
from keyboards.inline import get_subscription_menu
from services.database import add_user


router = Router()

BOT_VERSION = "2.0"

WELCOME_TEXT = (
    "🏢 <b>Smart Office Bot</b> ga xush kelibsiz!\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "Men sizning shaxsiy ofis yordamchingizman. "
    "Quyidagi barcha imkoniyatlardan <b>bepul</b> foydalanishingiz mumkin:\n\n"

    "📊 <b>Excel Asboblari</b>\n"
    "  • Excelni qirqish, aqlli bo'lish, toifa bo'yicha ajratish\n"
    "  • Dublikat tozalash, birlashtirish, grafik chizish\n\n"

    "📄 <b>PDF Asboblari</b>\n"
    "  • Birlashtirish, parol qo'yish, sahifa ajratish\n"
    "  • Watermark qo'yish, PDF → Word o'girish\n\n"

    "📝 <b>Word & Hujjat</b>\n"
    "  • Shablon to'ldirish, Word faylni o'qish\n\n"

    "🔄 <b>Tarjimon & Konvertor</b>\n"
    "  • Lotin ↔ Kirill, UZ ↔ EN ↔ RU tarjima\n"
    "  • Fayl formatini o'zgartirish (Rasm → PDF)\n\n"

    "🛠 <b>Qulay Vositalar</b>\n"
    "  • OCR (rasmdan matn o'qish)\n"
    "  • QR Kod yaratish, URL qisqartirish\n"
    "  • Excel ichidan ma'lumot qidirish\n\n"

    "🤖 <b>AI Yordamchi</b> — Sun'iy intellekt bilan suhbat\n"
    "⏰ <b>Eslatmalar</b> — Shaxsiy eslatmalar qo'shish\n"
    "⚙️ <b>Sozlamalar</b> — Profil, bot haqida, admin bilan aloqa\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    f"📦 Versiya: <b>{BOT_VERSION}</b> | 👨‍💻 @Elshod_Developer"
)

async def check_sub(bot: Bot, user_id: int) -> bool:
    if not CHANNEL_ID:
        return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except TelegramBadRequest:
        return False

@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    await add_user(message.from_user.id, message.from_user.full_name)

    is_subscribed = await check_sub(bot, message.from_user.id)

    if is_subscribed:
        await message.answer(
            WELCOME_TEXT,
            parse_mode="HTML",
            reply_markup=get_main_menu()
        )
    else:
        try:
            chat = await bot.get_chat(CHANNEL_ID)
            channel_url = chat.invite_link or f"https://t.me/{chat.username}" if chat.username else ""
        except Exception:
            channel_url = "https://t.me/your_channel_username"
            
        await message.answer(
            "Botdan to'liq foydalanish uchun kanalimizga obuna bo'ling!",
            reply_markup=get_subscription_menu(channel_url)
        )

@router.callback_query(F.data == "check_subscription")
async def process_check_sub(callback_query: CallbackQuery, bot: Bot):
    is_subscribed = await check_sub(bot, callback_query.from_user.id)
    
    if is_subscribed:
        await callback_query.message.delete()
        await callback_query.message.answer(
            WELCOME_TEXT,
            parse_mode="HTML",
            reply_markup=get_main_menu()
        )
    else:
        await callback_query.answer("Siz hali kanalga obuna bo'lmagansiz!", show_alert=True)
