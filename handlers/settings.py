from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from config import CHANNEL_ID, ADMIN_ID
import logging

router = Router()

BOT_VERSION = "2.0"
BOT_NAME = "smartOffice"
BOT_USERNAME = "@raqamli_ofis_bot"

FEATURES = [
    "📊 Excel — qirqish, aqlli bo'lish, toifa ajratish, grafik",
    "📄 PDF — birlashtirish, parol, ajratish, watermark, PDF→Word",
    "📝 Word — shablon to'ldirish, o'qish",
    "🔄 Tarjimon — Lotin↔Kirill, UZ↔EN↔RU",
    "🛠 OCR — rasmdan matn o'qish",
    "📸 QR Kod yaratish, 🔗 URL qisqartirish",
    "🔍 Excel ichidan ma'lumot qidirish",
    "🤖 AI Yordamchi (Gemini)",
    "⏰ Shaxsiy eslatmalar",
    "🌐 Web App (Mini ilova)",
]

# ── Sozlamalar uchun holatlar ──
class SettingsStates(StatesGroup):
    waiting_for_feedback = State()

def get_settings_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(text="🔄 Ma'lumotlarni yangilash", callback_data="settings_refresh")
        ],
        [
            InlineKeyboardButton(text="ℹ️ Bot haqida", callback_data="settings_about")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def build_settings_text(bot: Bot, user) -> str:
    sub_status = "❓ Noma'lum"
    if CHANNEL_ID:
        try:
            member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user.id)
            if member.status in ['member', 'administrator', 'creator']:
                sub_status = "✅ Obuna bo'lgan"
            else:
                sub_status = "❌ Obuna bo'lmagan"
        except TelegramBadRequest:
            sub_status = "⚠️ Tekshirib bo'lmadi"
        except Exception as e:
            logging.error(f"Obuna tekshirishda xatolik: {e}")
            sub_status = "⚠️ Tekshirib bo'lmadi"

    username_display = f"@{user.username}" if user.username else "Yo'q"
    lang = user.language_code.upper() if user.language_code else "Noma'lum"

    text = (
        f"⚙️ <b>Sozlamalar va profil</b>\n"
        f"{'─' * 28}\n\n"
        f"👤 <b>Ism:</b> {user.full_name}\n"
        f"🆔 <b>Telegram ID:</b> <code>{user.id}</code>\n"
        f"📱 <b>Username:</b> {username_display}\n"
        f"🌐 <b>Til:</b> {lang}\n\n"
        f"📣 <b>Kanal obunasi:</b> {sub_status}\n"
        f"{'─' * 28}\n\n"
        f"🤖 <b>Bot:</b> {BOT_NAME} {BOT_USERNAME}\n"
        f"📦 <b>Versiya:</b> {BOT_VERSION}"
    )
    return text

@router.message(F.text == "⚙️ Sozlamalar")
async def show_settings(message: Message, bot: Bot):
    text = await build_settings_text(bot, message.from_user)
    await message.answer(text, parse_mode="HTML", reply_markup=get_settings_menu())

@router.callback_query(F.data == "settings_refresh")
async def refresh_settings(callback: CallbackQuery, bot: Bot):
    await callback.answer("Yangilanmoqda...", show_alert=False)
    text = await build_settings_text(bot, callback.from_user)
    try:
        await callback.message.edit_text(
            text, parse_mode="HTML", reply_markup=get_settings_menu()
        )
    except TelegramBadRequest:
        pass

@router.callback_query(F.data == "settings_about")
async def show_about(callback: CallbackQuery):
    features_list = "\n".join([f"  • {f}" for f in FEATURES])
    about_text = (
        f"ℹ️ <b>{BOT_NAME} haqida</b>\n"
        f"{'─' * 28}\n\n"
        f"<b>{BOT_NAME}</b> — ofis ishlarini avtomatlashtirishga "
        f"mo'ljallangan aqlli Telegram yordamchisi.\n\n"
        f"🛠 <b>Imkoniyatlar:</b>\n{features_list}\n\n"
        f"📦 <b>Versiya:</b> {BOT_VERSION}\n\n"
        f"💡 <i>Takliflar uchun: \"📞 Adminga murojaat\" tugmasidan foydalaning.</i>"
    )
    back_btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="settings_refresh")]
    ])
    await callback.message.edit_text(about_text, parse_mode="HTML", reply_markup=back_btn)
    await callback.answer()

# ── Adminga murojaat (Asosiy menyu va Sozlamalar ichidan) ──
@router.message(F.text == "📞 Admin / Buyurtma")
async def ask_feedback_menu(message: Message, state: FSMContext):
    await message.answer(
        "📞 <b>Admin bilan aloqa</b>\n\n"
        "Savolingiz, taklifingiz yoki <b>buyurtmangizni</b> batafsil yozib yuboring.\n"
        "<i>Xabaringiz to'g'ridan-to'g'ri adminga yuboriladi.</i>",
        parse_mode="HTML"
    )
    await state.set_state(SettingsStates.waiting_for_feedback)

@router.callback_query(F.data == "settings_feedback")
async def ask_feedback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "📞 <b>Adminga murojaat</b>\n\n"
        "Savolingiz yoki taklifingizni batafsil yozing.\n"
        "<i>Xabaringiz to'g'ridan-to'g'ri adminga yuboriladi.</i>",
        parse_mode="HTML"
    )
    await state.set_state(SettingsStates.waiting_for_feedback)

@router.message(SettingsStates.waiting_for_feedback, F.text)
async def process_settings_feedback(message: Message, state: FSMContext, bot: Bot):
    if not ADMIN_ID:
        await message.answer("Kechirasiz, hozirda admin bilan bog'lanish imkoni yo'q.")
        await state.clear()
        return

    user = message.from_user
    user_info = (
        f"👤 <b>Foydalanuvchi:</b> {user.full_name}\n"
        f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
        f"📱 <b>Username:</b> @{user.username or 'Yoq'}\n\n"
        f"📩 <b>Murojaat:</b>\n{message.text}"
    )

    try:
        admin_id = int(ADMIN_ID)
        await bot.send_message(
            chat_id=admin_id,
            text=user_info + f"\n\n<i>💬 Javob berish uchun ushbu xabarga <b>Reply</b> qiling.</i>",
            parse_mode="HTML"
        )
        await message.answer(
            "✅ Murojaatingiz adminga yuborildi!\n\n"
            "Admin eng yaqin vaqtda javob qaytaradi."
        )
    except Exception as e:
        logging.error(f"Adminga xabar yuborishda xato: {e}")
        await message.answer("Xatolik yuz berdi. Keyinroq urinib ko'ring.")
    finally:
        await state.clear()
