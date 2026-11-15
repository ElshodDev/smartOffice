"""🔗 Do'stlarga ulashish va 💻 dasturchi xizmatlari."""
from urllib.parse import quote

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from services import botinfo
from services.database import count_referrals

router = Router()

DEVELOPER_USERNAME = "Elshod_Developer"

BACK = InlineKeyboardButton(text="⬅️ Orqaga", callback_data="profile_menu")

SERVICES_TEXT = (
    "💻 <b>Dasturchi va xizmatlar</b>\n\n"
    "Bot muallifi quyidagi xizmatlarni taklif qiladi:\n\n"
    "1️⃣ <b>Telegram bot yaratish</b> — do'kon, admin panel, AI ulangan botlar.\n"
    "2️⃣ <b>Veb-sayt yaratish</b> — landing page, korporativ sayt.\n"
    "3️⃣ <b>Biznesni avtomatlashtirish</b> — CRM, hisobot generatorlari kabi tizimlar.\n\n"
    "<i>Narxi kelishiladi.</i> Buyurtma yoki savol uchun pastdagi tugmani bosing 👇"
)


def services_keyboard(with_back: bool) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="📞 Dasturchiga yozish", url=f"https://t.me/{DEVELOPER_USERNAME}")]]
    if with_back:
        rows.append([BACK])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(F.text == "🛒 Xizmatlarim")
async def show_services(message: Message):
    await message.answer(SERVICES_TEXT, parse_mode="HTML", reply_markup=services_keyboard(False))


@router.callback_query(F.data == "dev_contact")
async def show_services_cb(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(SERVICES_TEXT, parse_mode="HTML", reply_markup=services_keyboard(True))


async def share_content(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    link = f"https://t.me/{botinfo.username()}?start={user_id}"
    invite = "Ofis ishlari uchun qulay bot: Excel, PDF, Word, skaner, ariza va hujjatlar tayyorlash 👇"
    share_url = f"https://t.me/share/url?url={quote(link, safe='')}&text={quote(invite, safe='')}"
    invited = await count_referrals(user_id)
    text = (
        "🔗 <b>Do'stlarga ulashing!</b>\n\n"
        "Botni hamkasblaringiz va do'stlaringizga tavsiya qiling 🤝\n\n"
        f"👥 Siz taklif qilgan do'stlar: <b>{invited} ta</b>\n"
        "<i>Do'stingiz havola orqali qo'shilganda sizga xabar keladi.</i>\n\n"
        f"Sizning havolangiz:\n<code>{link}</code>"
    )
    return text, InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🚀 Do'stlarga yuborish", url=share_url)]])


@router.message(F.text.in_({"🔗 Ulashish", "🔗 Do'stlarga ulashish"}))
async def share_bot(message: Message):
    text, keyboard = await share_content(message.from_user.id)
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data == "share_bot")
async def share_bot_cb(callback: CallbackQuery):
    await callback.answer()
    text, keyboard = await share_content(callback.from_user.id)
    keyboard.inline_keyboard.append([BACK])
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
