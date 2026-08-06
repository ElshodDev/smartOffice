from aiogram import Router, Bot, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from config import CHANNEL_ID
from keyboards.reply import get_main_menu
from keyboards.inline import get_subscription_menu
from services.database import add_user
from services.subscription import activate_premium


router = Router()

BOT_VERSION = "2.0"

WELCOME_TEXT = (
    "🏢 <b>Smart Office Bot</b> ga xush kelibsiz!\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "Men sizning shaxsiy ofis yordamchingizman. "
    "Menda quyidagi imkoniyatlar bor:\n\n"
    
    "📋 <b>Hisobot Yaratish</b> <i>(Premium)</i> — Shaxsiy PDF va Excel hisobotlar yaratish\n"
    "💳 <b>Premium</b> — VIP funksiyalar va sun'iy intellekt xizmatlariga cheksiz kirish\n"
    "🌐 <b>Web Ilova</b> — Barcha vositalarni chiroyli ilova ichida ishlatish\n\n"

    "<b>📁 Asosiy Bo'limlar (Tugmalar ichidagi imkoniyatlar):</b>\n"
    "📊 <b>Excel Asboblari:</b> Excelni qirqish, aqlli bo'lish, toifa bo'yicha ajratish, dublikat tozalash, birlashtirish, grafik chizish.\n"
    "📄 <b>PDF Asboblari:</b> PDF larni birlashtirish, parol qo'yish, sahifaga ajratish, watermark (imzo) qo'yish, PDF ni Word ga o'girish.\n"
    "📝 <b>Word & Hujjat:</b> Shablon to'ldirish va Word fayllarni o'qish.\n"
    "🔄 <b>Tarjimon & Konvertor:</b> Lotin-Kirill, UZ-EN-RU tarjima va har qanday fayl formatini o'zgartirish.\n"
    "🛠 <b>Qulay Vositalar:</b> Rasmdan matn o'qish (OCR), QR Kod yaratish, URL qisqartirish, Excel ichidan ma'lumot qidirish.\n\n"

    "<b>Boshqalar:</b>\n"
    "🤖 <b>AI Yordamchi</b> — Gemini AI bilan istalgan mavzuda suhbat\n"
    "⏰ <b>Eslatmalar</b> — O'zingizga eslatma va vazifalar belgilash\n"
    "🔗 <b>Ulashish</b> — Do'stlarni taklif qilib tekin Premium olish\n"
    "🛒 <b>Xizmatlarim</b> — Dasturchi bilan aloqa va maxsus xizmatlar\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    f"📦 Versiya: <b>{BOT_VERSION}</b>"
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
    # Referral code parsing: /start 123456789
    args = message.text.split()
    referrer_id = None
    if len(args) > 1 and args[1].isdigit():
        referrer_id = int(args[1])

    is_new = await add_user(message.from_user.id, message.from_user.full_name, referrer_id)

    # Agar yangi foydalanuvchi bo'lsa va referral bilan kirgan bo'lsa (va o'zini o'zi taklif qilmagan bo'lsa)
    if is_new and referrer_id and referrer_id != message.from_user.id:
        # Ikkalasiga ham 3 kunlik premium beramiz
        await activate_premium(message.from_user.id, "referral_bonus", 3)
        await activate_premium(referrer_id, "referral_bonus", 3)
        try:
            await bot.send_message(
                chat_id=referrer_id,
                text=f"🎉 <b>Tabriklaymiz!</b>\n\nSizning havolangiz orqali do'stingiz (<a href='tg://user?id={message.from_user.id}'>{message.from_user.full_name}</a>) botga qo'shildi!\n\n"
                     f"Sizga <b>3 kunlik Premium</b> sovg'a qilindi! 💎",
                parse_mode="HTML"
            )
        except Exception:
            pass # Agar bloklagan bo'lsa xato bermaydi
        
        await message.answer("🎁 <b>Maxsus havola orqali kirdingiz!</b>\nSizga <b>3 kunlik Premium</b> sovg'a qilindi! 💎", parse_mode="HTML")


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
