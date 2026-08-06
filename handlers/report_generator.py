import io
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from services.subscription import is_premium
from services.pdf_report import generate_pdf
from services.excel_report import generate_excel

router = Router()

# ── Holatlar (FSM) ──
class ObyektivkaStates(StatesGroup):
    full_name   = State()
    birth_info  = State()
    education   = State()
    experience  = State()
    choose_fmt  = State()


# ── Skip tugmasi ──
def skip_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⏩ O'tkazib yuborish", callback_data="report_skip")
    ]])


# ── Format tanlash klaviaturasi ──
def format_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📄 PDF", callback_data="report_fmt_pdf"),
            InlineKeyboardButton(text="📊 Excel", callback_data="report_fmt_excel"),
        ],
        [
            InlineKeyboardButton(text="📦 Ikkalasi ham", callback_data="report_fmt_both"),
        ]
    ])


# ── Boshlash ──
@router.message(F.text == "📋 Obyektivka Yaratish")
async def start_report(message: Message, state: FSMContext):
    await state.clear()

    # Premium tekshiruv
    premium = await is_premium(message.from_user.id)
    if not premium:
        await message.answer(
            "📋 <b>Obyektivka Yaratish — Premium xizmat</b>\n\n"
            "Bu funksiya faqat <b>Premium</b> foydalanuvchilar uchun mavjud.\n\n"
            "💳 Premium olish uchun asosiy menyudagi <b>\"💳 Premium\"</b> tugmasini bosing.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="💳 Premium olish", callback_data="go_premium")
            ]])
        )
        return

    await message.answer(
        "📋 <b>Obyektivka Yaratish (Qisqacha)</b>\n\n"
        "Men sizning asosiy ma'lumotlaringizni yig'ib, chiroyli Ma'lumotnoma tayyorlayman.\n\n"
        "👤 Avval to'liq <b>F.I.Sh.</b> (Familiya Ism Sharifingizni) kiriting:",
        parse_mode="HTML"
    )
    await state.set_state(ObyektivkaStates.full_name)


# ── F.I.Sh ──
@router.message(ObyektivkaStates.full_name, F.text)
async def get_full_name(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text.strip())
    await message.answer(
        "✅ Saqlandi!\n\n📅 <b>Tug'ilgan sanangiz va joyingizni</b> kiriting:\n"
        "<i>(Misol: 15.03.1990, Toshkent shahri)</i>",
        parse_mode="HTML"
    )
    await state.set_state(ObyektivkaStates.birth_info)


# ── Tug'ilgan sana va joy ──
@router.message(ObyektivkaStates.birth_info, F.text)
async def get_birth_info(message: Message, state: FSMContext):
    await state.update_data(birth_info=message.text.strip())
    await message.answer(
        "✅ Saqlandi!\n\n🎓 <b>Ma'lumotingiz, mutaxassisligingiz va qayerda o'qiganingizni</b> kiriting:\n"
        "<i>(Misol: Oliy, Falsafa, Toshkent Davlat Universiteti (2000-yil))</i>",
        parse_mode="HTML"
    )
    await state.set_state(ObyektivkaStates.education)


# ── Ma'lumoti ──
@router.message(ObyektivkaStates.education, F.text)
async def get_education(message: Message, state: FSMContext):
    await state.update_data(education=message.text.strip())
    await message.answer(
        "✅ Saqlandi!\n\n💼 <b>Hozirgi ish joyingiz va lavozimingizni</b> kiriting:\n"
        "<i>(Misol: \"Smart Office\" MChJ, Bosh menejer)</i>",
        parse_mode="HTML"
    )
    await state.set_state(ObyektivkaStates.experience)


# ── Ish joyi ──
@router.message(ObyektivkaStates.experience, F.text)
async def get_experience(message: Message, state: FSMContext):
    await state.update_data(experience=message.text.strip())
    await ask_format(message, state)


# ── Skip callback ──
@router.callback_query(F.data == "report_skip")
async def skip_field(callback: CallbackQuery, state: FSMContext):
    await callback.answer("O'tkazib yuborildi", show_alert=False)


# ── Format so'rash ──
async def ask_format(message: Message, state: FSMContext):
    await message.answer(
        "✅ Barcha ma'lumotlar yig'ildi!\n\n"
        "📁 Obyektivkani qaysi formatda olmoqchisiz?",
        reply_markup=format_kb()
    )
    await state.set_state(ObyektivkaStates.choose_fmt)


# ── Hisobot yaratish ──
async def send_report(message: Message, state: FSMContext, fmt: str):
    data = await state.get_data()
    await state.clear()

    # Foydalanuvchi ismidan fayl nomi
    name_part = data.get('full_name', 'hisobot').replace(' ', '_')

    wait_msg = await message.answer("⏳ Hisobot tayyorlanmoqda...")

    try:
        if fmt in ('pdf', 'both'):
            pdf_bytes = generate_pdf(data)
            await message.answer_document(
                BufferedInputFile(pdf_bytes, filename=f"{name_part}_obyektivka.pdf"),
                caption="📄 <b>Obyektivka (PDF)</b> tayyor!\n\n<i>To'liq obyektivka to'ldirish uchun kompyuter kerak bo'lishi mumkin.</i>",
                parse_mode="HTML"
            )

        if fmt in ('excel', 'both'):
            excel_bytes = generate_excel(data)
            await message.answer_document(
                BufferedInputFile(excel_bytes, filename=f"{name_part}_obyektivka.xlsx"),
                caption="📊 <b>Obyektivka (Excel)</b> tayyor!",
                parse_mode="HTML"
            )

        await wait_msg.delete()
        
        # UX: Bosh menyuga qaytish
        from keyboards.reply import get_main_menu
        await message.answer("Boshqa xizmatlardan foydalanish uchun menyudan tanlang 👇", reply_markup=get_main_menu())

    except Exception as e:
        logging.error(f"Obyektivka yaratishda xato: {e}")
        await wait_msg.edit_text("❌ Obyektivka yaratishda xatolik yuz berdi. Keyinroq urinib ko'ring.")


@router.callback_query(F.data == "report_fmt_pdf", ObyektivkaStates.choose_fmt)
async def fmt_pdf(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text("📄 PDF hisobot yaratilmoqda...")
    await send_report(callback.message, state, 'pdf')


@router.callback_query(F.data == "report_fmt_excel", ObyektivkaStates.choose_fmt)
async def fmt_excel(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text("📊 Excel obyektivka yaratilmoqda...")
    await send_report(callback.message, state, 'excel')


@router.callback_query(F.data == "report_fmt_both", ObyektivkaStates.choose_fmt)
async def fmt_both(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text("📦 PDF va Excel hisobotlar yaratilmoqda...")
    await send_report(callback.message, state, 'both')
