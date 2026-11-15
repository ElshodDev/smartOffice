"""🔗 Do'stlarga ulashish, 💻 dasturchi loyihalari (portfolio) va 📩 buyurtma berish."""
import logging
import uuid
from urllib.parse import quote

from aiogram import Bot, Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from services import botinfo
from services.database import count_referrals

router = Router()

DEVELOPER_USERNAME = "Elshod_Developer"

BACK = InlineKeyboardButton(text="⬅️ Orqaga", callback_data="profile_menu")

SERVICES_TEXT = (
    "💻 <b>Dasturchi va loyihalar</b>\n\n"
    "smartOffice muallifi — dasturchi {dev}. Uning boshqa loyihalari:\n\n"
    "{projects}\n\n"
    "🛠 <b>Buyurtma asosida:</b> Telegram botlar, veb-saytlar, web ilovalar va ish jarayonini "
    "avtomatlashtirish (CRM, hisobotlar, hujjat tizimlari).\n\n"
    "<i>Loyihangiz bormi? «📩 Buyurtma berish» ni bosing — 1 daqiqalik so'rovnoma, javob shu chatga keladi.</i>"
)


def services_text() -> str:
    from services.alphabet import raw
    from services.portfolio import PROJECTS
    projects = "\n".join(f"{emoji} <b>{raw(name)}</b> — {desc}" for _, emoji, name, _, desc in PROJECTS)
    return SERVICES_TEXT.format(dev=raw("@" + DEVELOPER_USERNAME), projects=projects)


def services_keyboard(with_back: bool, user_id: int | None = None) -> InlineKeyboardMarkup:
    from aiogram.types import WebAppInfo
    from services.alphabet import raw
    from services.portfolio import PROJECTS, tracked_url
    # Loyihalar Telegram ichida ochiladi (Web App), havola orqali kim ochgani hisoblanadi
    rows = [[InlineKeyboardButton(text=f"{emoji} {raw(name)}", web_app=WebAppInfo(url=tracked_url(key, user_id)))]
            for key, emoji, name, _, _ in PROJECTS]
    rows.append([InlineKeyboardButton(text="📩 Buyurtma berish", callback_data="order_start")])
    rows.append([InlineKeyboardButton(text="📞 Dasturchiga yozish", url=f"https://t.me/{DEVELOPER_USERNAME}")])
    if with_back:
        rows.append([BACK])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(F.text.in_({"🛒 Xizmatlarim", "💻 Dasturchi"}))
async def show_services(message: Message):
    await message.answer(services_text(), parse_mode="HTML", disable_web_page_preview=True,
                         reply_markup=services_keyboard(False, message.from_user.id))


@router.callback_query(F.data == "dev_contact")
async def show_services_cb(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(services_text(), parse_mode="HTML", disable_web_page_preview=True,
                                     reply_markup=services_keyboard(True, callback.from_user.id))


# ── 📩 Buyurtma berish ─────────────────────────────────────────────────────
class OrderStates(StatesGroup):
    description = State()
    phone = State()


CANCEL_ROW = [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="dev_contact")]


@router.callback_query(F.data == "order_start")
async def order_start(callback: CallbackQuery, state: FSMContext):
    from services.portfolio import ORDER_TYPES
    await callback.answer()
    await state.clear()
    rows = [[InlineKeyboardButton(text=title, callback_data=f"order_type:{key}")] for key, title in ORDER_TYPES]
    rows.append(CANCEL_ROW)
    await callback.message.edit_text("📩 <b>Buyurtma</b> (1/3)\n\nQanday loyiha kerak?", parse_mode="HTML",
                                     reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data.startswith("order_type:"))
async def order_type(callback: CallbackQuery, state: FSMContext):
    from services.portfolio import ORDER_TITLES
    key = callback.data.split(":", 1)[1]
    if key not in ORDER_TITLES:
        await callback.answer()
        return
    await callback.answer()
    await state.set_state(OrderStates.description)
    await state.update_data(order_type=key)
    await callback.message.edit_text(
        f"📩 <b>Buyurtma</b> (2/3) — {ORDER_TITLES[key]}\n\n"
        "Loyihangizni qisqacha yozing: nima qilishi kerak, kimlar uchun, muddat va taxminiy byudjet "
        "(bilsangiz).\n\n<i>Masalan: «Do'konim uchun buyurtma qabul qiladigan bot, 1 oy ichida».</i>",
        parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[CANCEL_ROW]),
    )


@router.message(OrderStates.description, F.text)
async def order_description(message: Message, state: FSMContext):
    text = message.text.strip()
    if text.startswith("/"):
        return
    if len(text) < 15:
        await message.answer("✍️ Biroz batafsilroq yozing (kamida 15 belgi) — shunda aniq javob bera olaman.")
        return
    if len(text) > 2000:
        await message.answer(f"❌ Juda uzun ({len(text)} belgi). 2000 belgigacha qisqartiring.")
        return
    await state.update_data(order_text=text)
    await state.set_state(OrderStates.phone)
    await message.answer(
        "📩 <b>Buyurtma</b> (3/3)\n\nTelefon raqamingizni yozing — dasturchi qo'ng'iroq qilishi uchun.\n"
        "<i>Istamasangiz, «O'tkazib yuborish» ni bosing: javob shu chatga yoziladi.</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ O'tkazib yuborish", callback_data="order_skip_phone")], CANCEL_ROW]),
    )


async def _finish_order(message: Message, user, state: FSMContext, bot: Bot, phone: str):
    from config import ADMIN_ID
    from services.alphabet import esc
    from services.database import set_flag
    from services.portfolio import ORDER_TITLES
    from services.timeutil import now_tashkent
    data = await state.get_data()
    await state.clear()
    username = f"@{user.username}" if user.username else "yo'q"
    admin_text = (
        f"🛠 <b>Yangi buyurtma!</b>\n\n"
        f"📌 <b>Turi:</b> {ORDER_TITLES.get(data.get('order_type'), '—')}\n"
        f"👤 <b>Mijoz:</b> {esc(user.full_name)}\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"📱 <b>Username:</b> {esc(username)}\n"
        f"📞 <b>Telefon:</b> {esc(phone) if phone else 'ko‘rsatilmagan'}\n\n"
        f"📝 {esc(data.get('order_text', ''))}\n\n"
        f"<i>💬 Javob berish uchun shu xabarga Reply qiling.</i>"
    )
    try:
        if ADMIN_ID:
            await bot.send_message(int(ADMIN_ID), admin_text, parse_mode="HTML")
        # Har bir buyurtma alohida hisoblanadi (bir soniyada ikkitasi bo'lsa ham)
        await set_flag(user.id, f"order:{now_tashkent():%Y%m%d%H%M%S}-{uuid.uuid4().hex[:6]}")
        await message.answer(
            "✅ <b>Buyurtmangiz yuborildi!</b>\n\nDasturchi tez orada shu chatga yoki telefoningizga javob beradi. Rahmat! 🤝",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Profilga", callback_data="profile_menu")]]),
        )
    except Exception as e:
        logging.error(f"Buyurtmani yuborishda xato: {e}")
        await message.answer("❌ Xatolik yuz berdi. Iltimos, dasturchiga to'g'ridan-to'g'ri yozing: "
                             f"@{DEVELOPER_USERNAME}")


@router.message(OrderStates.phone, F.text)
async def order_phone(message: Message, state: FSMContext, bot: Bot):
    text = message.text.strip()
    if text.startswith("/"):
        return
    digits = sum(ch.isdigit() for ch in text)
    if digits < 7 or len(text) > 30:
        await message.answer("📞 Raqamni to'g'ri yozing, masalan: +998 90 123 45 67 — yoki «O'tkazib yuborish» ni bosing.")
        return
    await _finish_order(message, message.from_user, state, bot, text)


@router.callback_query(OrderStates.phone, F.data == "order_skip_phone")
async def order_skip_phone(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    await _finish_order(callback.message, callback.from_user, state, bot, "")


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
