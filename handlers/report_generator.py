import io
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from services.pdf_report import generate_pdf
from services.excel_report import generate_excel

router = Router()

# ── Holatlar (FSM) ──
class ReportStates(StatesGroup):
    full_name   = State()
    surname     = State()
    passport    = State()
    birth_date  = State()
    address     = State()
    phone       = State()
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
@router.message(F.text == "📋 Hisobot Yaratish")
async def start_report(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "📋 <b>Hisobot Yaratish</b>\n\n"
        "Men sizning shaxsiy ma'lumotlaringizni yig'ib, chiroyli hisobot tayyorlayman.\n\n"
        "👤 Avval <b>ismingizni</b> kiriting:",
        parse_mode="HTML"
    )
    await state.set_state(ReportStates.full_name)


# ── Ism ──
@router.message(ReportStates.full_name, F.text)
async def get_full_name(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text.strip())
    await message.answer(
        "✅ Ism saqlandi!\n\n👤 Endi <b>familiyangizni</b> kiriting:",
        parse_mode="HTML"
    )
    await state.set_state(ReportStates.surname)


# ── Familiya ──
@router.message(ReportStates.surname, F.text)
async def get_surname(message: Message, state: FSMContext):
    await state.update_data(surname=message.text.strip())
    await message.answer(
        "✅ Familiya saqlandi!\n\n🪪 <b>Pasport raqamingizni</b> kiriting:\n"
        "<i>(Ixtiyoriy — o'tkazib yuborish mumkin)</i>",
        parse_mode="HTML",
        reply_markup=skip_kb()
    )
    await state.set_state(ReportStates.passport)


# ── Pasport ──
@router.message(ReportStates.passport, F.text)
async def get_passport(message: Message, state: FSMContext):
    await state.update_data(passport=message.text.strip())
    await message.answer(
        "✅ Pasport saqlandi!\n\n📅 <b>Tug'ilgan sanangizni</b> kiriting:\n"
        "<i>Misol: 15.03.1990  (Ixtiyoriy)</i>",
        parse_mode="HTML",
        reply_markup=skip_kb()
    )
    await state.set_state(ReportStates.birth_date)


# ── Tug'ilgan sana ──
@router.message(ReportStates.birth_date, F.text)
async def get_birth_date(message: Message, state: FSMContext):
    await state.update_data(birth_date=message.text.strip())
    await message.answer(
        "✅ Sana saqlandi!\n\n📍 <b>Manzilingizni</b> kiriting:\n"
        "<i>Misol: Toshkent sh., Chilonzor t.  (Ixtiyoriy)</i>",
        parse_mode="HTML",
        reply_markup=skip_kb()
    )
    await state.set_state(ReportStates.address)


# ── Manzil ──
@router.message(ReportStates.address, F.text)
async def get_address(message: Message, state: FSMContext):
    await state.update_data(address=message.text.strip())
    await message.answer(
        "✅ Manzil saqlandi!\n\n📞 <b>Telefon raqamingizni</b> kiriting:\n"
        "<i>Misol: +998901234567  (Ixtiyoriy)</i>",
        parse_mode="HTML",
        reply_markup=skip_kb()
    )
    await state.set_state(ReportStates.phone)


# ── Telefon ──
@router.message(ReportStates.phone, F.text)
async def get_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text.strip())
    await ask_format(message, state)


# ── Skip callback ──
@router.callback_query(F.data == "report_skip")
async def skip_field(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    current = await state.get_state()

    # Joriy holat bo'yicha keyingisiga o'tamiz
    if current == ReportStates.passport:
        await state.update_data(passport='-')
        await callback.message.edit_text(
            "⏩ O'tkazildi.\n\n📅 <b>Tug'ilgan sanangizni</b> kiriting:\n"
            "<i>Misol: 15.03.1990  (Ixtiyoriy)</i>",
            parse_mode="HTML",
            reply_markup=skip_kb()
        )
        await state.set_state(ReportStates.birth_date)

    elif current == ReportStates.birth_date:
        await state.update_data(birth_date='-')
        await callback.message.edit_text(
            "⏩ O'tkazildi.\n\n📍 <b>Manzilingizni</b> kiriting:\n"
            "<i>Misol: Toshkent sh., Chilonzor t.  (Ixtiyoriy)</i>",
            parse_mode="HTML",
            reply_markup=skip_kb()
        )
        await state.set_state(ReportStates.address)

    elif current == ReportStates.address:
        await state.update_data(address='-')
        await callback.message.edit_text(
            "⏩ O'tkazildi.\n\n📞 <b>Telefon raqamingizni</b> kiriting:\n"
            "<i>Misol: +998901234567  (Ixtiyoriy)</i>",
            parse_mode="HTML",
            reply_markup=skip_kb()
        )
        await state.set_state(ReportStates.phone)

    elif current == ReportStates.phone:
        await state.update_data(phone='-')
        await ask_format(callback.message, state)
        await state.set_state(ReportStates.choose_fmt)


# ── Format so'rash ──
async def ask_format(message: Message, state: FSMContext):
    await message.answer(
        "✅ Ma'lumotlar yig'ildi!\n\n"
        "📁 Qaysi formatda hisobot olmoqchisiz?",
        reply_markup=format_kb()
    )
    await state.set_state(ReportStates.choose_fmt)


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
                BufferedInputFile(pdf_bytes, filename=f"{name_part}_hisobot.pdf"),
                caption="📄 <b>PDF Hisobot</b> tayyor!",
                parse_mode="HTML"
            )

        if fmt in ('excel', 'both'):
            excel_bytes = generate_excel(data)
            await message.answer_document(
                BufferedInputFile(excel_bytes, filename=f"{name_part}_hisobot.xlsx"),
                caption="📊 <b>Excel Hisobot</b> tayyor!",
                parse_mode="HTML"
            )

        await wait_msg.delete()

    except Exception as e:
        logging.error(f"Hisobot yaratishda xato: {e}")
        await wait_msg.edit_text("❌ Hisobot yaratishda xatolik yuz berdi. Keyinroq urinib ko'ring.")


@router.callback_query(F.data == "report_fmt_pdf", ReportStates.choose_fmt)
async def fmt_pdf(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text("📄 PDF hisobot yaratilmoqda...")
    await send_report(callback.message, state, 'pdf')


@router.callback_query(F.data == "report_fmt_excel", ReportStates.choose_fmt)
async def fmt_excel(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text("📊 Excel hisobot yaratilmoqda...")
    await send_report(callback.message, state, 'excel')


@router.callback_query(F.data == "report_fmt_both", ReportStates.choose_fmt)
async def fmt_both(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text("📦 PDF va Excel hisobotlar yaratilmoqda...")
    await send_report(callback.message, state, 'both')
