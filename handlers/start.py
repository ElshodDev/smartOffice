from aiogram import Router, Bot, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext

from config import CHANNEL_ID
from keyboards.reply import get_main_menu
from keyboards.inline import get_subscription_menu
from middlewares.subscription import check_sub, channel_url
from services import botinfo
from services.alphabet import esc
from services.database import add_user, user_exists, count_referrals


router = Router()

BOT_VERSION = botinfo.VERSION

WELCOME_TEXT = (
    "🏢 <b>Smart Office Bot</b> ga xush kelibsiz!\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "Men sizning shaxsiy ofis yordamchingizman.\n"
    "Menda quyidagi qulayliklar bor:\n\n"
    
    "📁 <b>Hujjatlar bilan ishlash:</b>\n"
    "Excel, PDF, Word hujjatlari bilan ishlash, Excel ro'yxatdan ommaviy hujjat yaratish. Ariza, tushuntirish xati, buyruq va Obyektivka tayyorlash.\n\n"

    "🔤 <b>Tarjimon va Alifbo:</b>\n"
    "Matnlarni tarjima qilish (UZ, EN, RU), Lotin↔Kirill va yangi lotin alifbosiga o'girish (matn, Word, PDF).\n\n"

    "📁 <b>Format o'zgartirish:</b>\n"
    "PDF ni Word ga, rasmni PDF ga o'girish, telefon suratidan toza skan qilish.\n\n"

    "🤖 <b>AI Yordamchi:</b>\n"
    "Savollaringizga javob topish uchun sun'iy intellekt.\n\n"
    
    "👤 <b>Profil va Sozlamalar:</b>\n"
    "Bot sozlamalari va biz bilan aloqa.\n\n"

    "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    f"📦 Versiya: <b>{BOT_VERSION}</b>"
)

@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    # Taklif havolasi: /start 123456789
    args = (message.text or "").split()
    referrer_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
    if referrer_id == message.from_user.id or (referrer_id and not await user_exists(referrer_id)):
        referrer_id = None

    is_new = await add_user(message.from_user.id, message.from_user.full_name, referrer_id)

    if is_new and referrer_id:
        try:
            total = await count_referrals(referrer_id)
            await bot.send_message(
                chat_id=referrer_id,
                text=(f"🎉 <b>Tabriklaymiz!</b>\n\nSizning havolangiz orqali do'stingiz "
                      f"<a href='tg://user?id={message.from_user.id}'>{esc(message.from_user.full_name)}</a> "
                      f"botga qo'shildi! 🤝\n\n👥 Siz taklif qilgan do'stlar: <b>{total} ta</b>"),
                parse_mode="HTML",
            )
        except Exception:
            pass

    if await check_sub(bot, message.from_user.id, use_cache=False):
        await message.answer(WELCOME_TEXT, parse_mode="HTML", reply_markup=get_main_menu())
        # Web ilovadagi xaritadan: /start go_scan → shu bo'lim darhol ochiladi
        if len(args) > 1 and args[1].startswith("go_"):
            from handlers.ai_assistant import send_section
            from services import activity
            key = args[1][3:]
            if await send_section(message, key):
                activity.record_section(message.from_user.id, key)
    else:
        await message.answer(
            "Botdan to'liq foydalanish uchun kanalimizga obuna bo'ling!",
            reply_markup=get_subscription_menu(await channel_url(bot)),
        )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    # Bekor qilinadigan holat bormi yo'qmi tekshiramiz (keraksiz xabar bermaslik uchun)
    current_state = await state.get_state()
    if current_state:
        await state.clear()
    
    await message.answer(
        "❌ Joriy amal bekor qilindi.\n"
        "Asosiy menyuga qaytdingiz.",
        reply_markup=get_main_menu()
    )

@router.callback_query(F.data == "check_subscription")
async def process_check_sub(callback_query: CallbackQuery, bot: Bot):
    is_subscribed = await check_sub(bot, callback_query.from_user.id, use_cache=False)
    
    if is_subscribed:
        await callback_query.message.delete()
        await callback_query.message.answer(
            WELCOME_TEXT,
            parse_mode="HTML",
            reply_markup=get_main_menu()
        )
    else:
        await callback_query.answer("Siz hali kanalga obuna bo'lmagansiz!", show_alert=True)
