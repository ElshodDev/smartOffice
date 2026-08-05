import os
import qrcode
import pyshorteners
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

router = Router()

class UtilityStates(StatesGroup):
    waiting_for_qr_text = State()
    waiting_for_url = State()

def get_utility_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 QR Kod yaratish", callback_data="util_qr")],
        [InlineKeyboardButton(text="🔗 URL qisqartirish", callback_data="util_url")]
    ])

@router.message(F.text == "🛠 Yordamchi Asboblar")
async def show_utility_tools(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🛠 <b>Yordamchi Asboblar</b>\n\nQaysi biridan foydalanasiz?",
        parse_mode="HTML",
        reply_markup=get_utility_menu()
    )

# ── QR KOD YARATISH ──
@router.callback_query(F.data == "util_qr")
async def ask_qr_text(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "📸 <b>QR Kod yaratish</b>\n\n"
        "Matn yoki havolani (link) yuboring, men uni QR kod rasmi qilib beraman.\n\n"
        "<i>Bekor qilish uchun /cancel yozing.</i>",
        parse_mode="HTML"
    )
    await state.set_state(UtilityStates.waiting_for_qr_text)

@router.message(UtilityStates.waiting_for_qr_text, F.text)
async def generate_qr(message: Message, state: FSMContext):
    text = message.text
    os.makedirs("temp", exist_ok=True)
    img_path = f"temp/qr_{message.from_user.id}.png"
    
    try:
        # QR yasash
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(text)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(img_path)
        
        photo = FSInputFile(img_path)
        await message.answer_photo(photo, caption="✅ QR Kod tayyor!")
    except Exception as e:
        await message.answer("❌ QR kod yaratishda xatolik yuz berdi.")
    finally:
        if os.path.exists(img_path):
            os.remove(img_path)
        await state.clear()

# ── URL QISQARTIRISH ──
@router.callback_query(F.data == "util_url")
async def ask_url(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "🔗 <b>URL Qisqartirish</b>\n\n"
        "Uzun havolani (https://...) yuboring.",
        parse_mode="HTML"
    )
    await state.set_state(UtilityStates.waiting_for_url)

@router.message(UtilityStates.waiting_for_url, F.text)
async def shorten_url(message: Message, state: FSMContext):
    url = message.text
    if not url.startswith("http"):
        await message.answer("❌ Xato! Havola 'http://' yoki 'https://' bilan boshlanishi kerak.")
        return
        
    msg = await message.answer("⏳ Qisqartirilmoqda...")
    try:
        s = pyshorteners.Shortener()
        short_url = s.tinyurl.short(url)
        
        await msg.edit_text(
            f"✅ <b>Havola qisqartirildi:</b>\n\n{short_url}",
            parse_mode="HTML"
        )
    except Exception as e:
        await msg.edit_text("❌ Havolani qisqartirish ilojsiz. Link to'g'riligini tekshiring.")
    finally:
        await state.clear()
