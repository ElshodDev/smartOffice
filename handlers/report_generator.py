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
    full_name    = State()  # F.I.Sh.
    birth_date   = State()  # Tug'ilgan yili
    birth_place  = State()  # Tug'ilgan joyi
    nationality  = State()  # Millati
    party        = State()  # Partiyaviyligi
    education    = State()  # Ma'lumoti (Oliy/O'rta)
    graduated    = State()  # Tamomlagan (qayer, qachon)
    specialty    = State()  # Mutaxassisligi
    sci_degree   = State()  # Ilmiy darajasi
    sci_title    = State()  # Ilmiy unvoni
    languages    = State()  # Chet tillari
    military     = State()  # Harbiy unvoni
    awards       = State()  # Davlat mukofotlari
    deputy       = State()  # Deputatmi?
    work_history = State()  # Mehnat faoliyati
    photo        = State()  # 3x4 fotosurat
    choose_fmt   = State()  # Format tanlash


# ── Tugmalar ──
def skip_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⏩ Yo'q / O'tkazib yuborish", callback_data="ob_skip")
    ]])

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

    premium = await is_premium(message.from_user.id)
    if not premium:
        await message.answer(
            "📋 <b>Obyektivka Yaratish — Premium xizmat</b>\n\n"
            "Bu funksiya faqat <b>Premium</b> foydalanuvchilar uchun mavjud.\n\n"
            "💳 Asosiy menyudagi <b>\"💳 Premium\"</b> tugmasini bosing.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="💳 Premium olish", callback_data="go_premium")
            ]])
        )
        return

    await message.answer(
        "📋 <b>Ma'lumotnoma (Obyektivka) Yaratish</b>\n\n"
        "Standart O'zbek Obyektivkasini tayyorlayman.\n"
        "Har bir savolga javob bering. <i>Yo'q</i> bo'lganlarga tugmani bosing.\n\n"
        "👤 <b>F.I.Sh.</b> (To'liq familiya, ism, sharif):\n"
        "<i>Misol: Иводуллаев Элшод Маҳаммади ўғли</i>",
        parse_mode="HTML"
    )
    await state.set_state(ObyektivkaStates.full_name)


# ── 1. F.I.Sh ──
@router.message(ObyektivkaStates.full_name, F.text)
async def get_full_name(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text.strip())
    await message.answer(
        "✅ Saqlandi!\n\n📅 <b>Tug'ilgan yili:</b>\n"
        "<i>Misol: 08.06.2004</i>",
        parse_mode="HTML"
    )
    await state.set_state(ObyektivkaStates.birth_date)


# ── 2. Tug'ilgan yili ──
@router.message(ObyektivkaStates.birth_date, F.text)
async def get_birth_date(message: Message, state: FSMContext):
    await state.update_data(birth_date=message.text.strip())
    await message.answer(
        "✅ Saqlandi!\n\n📍 <b>Tug'ilgan joyi</b> (viloyat, tuman):\n"
        "<i>Misol: Qashqadaryo viloyati, Qamashi tumani</i>",
        parse_mode="HTML"
    )
    await state.set_state(ObyektivkaStates.birth_place)


# ── 3. Tug'ilgan joyi ──
@router.message(ObyektivkaStates.birth_place, F.text)
async def get_birth_place(message: Message, state: FSMContext):
    await state.update_data(birth_place=message.text.strip())
    await message.answer(
        "✅ Saqlandi!\n\n🌍 <b>Millati:</b>\n"
        "<i>Misol: o'zbek</i>",
        parse_mode="HTML"
    )
    await state.set_state(ObyektivkaStates.nationality)


# ── 4. Millati ──
@router.message(ObyektivkaStates.nationality, F.text)
async def get_nationality(message: Message, state: FSMContext):
    await state.update_data(nationality=message.text.strip())
    await message.answer(
        "✅ Saqlandi!\n\n🏛 <b>Partiyaviyligi</b> (qaysi partiya a'zosi):",
        parse_mode="HTML",
        reply_markup=skip_kb()
    )
    await state.set_state(ObyektivkaStates.party)


# ── 5. Partiya ──
@router.message(ObyektivkaStates.party, F.text)
async def get_party(message: Message, state: FSMContext):
    await state.update_data(party=message.text.strip())
    await message.answer(
        "✅ Saqlandi!\n\n🎓 <b>Ma'lumoti</b> (oliy / o'rta maxsus / o'rta):",
        parse_mode="HTML"
    )
    await state.set_state(ObyektivkaStates.education)


# ── 6. Ma'lumot ──
@router.message(ObyektivkaStates.education, F.text)
async def get_education(message: Message, state: FSMContext):
    await state.update_data(education=message.text.strip())
    await message.answer(
        "✅ Saqlandi!\n\n🏫 <b>Tamomlagan</b> (o'quv yurti nomi, yili, bosqichi):\n"
        "<i>Misol: 2026 y. Mirzo Ulug'bekdagi O'zbekiston Milliy Universiteti (bakalavr)</i>",
        parse_mode="HTML"
    )
    await state.set_state(ObyektivkaStates.graduated)


# ── 7. Tamomlagan ──
@router.message(ObyektivkaStates.graduated, F.text)
async def get_graduated(message: Message, state: FSMContext):
    await state.update_data(graduated=message.text.strip())
    await message.answer(
        "✅ Saqlandi!\n\n📚 <b>Ma'lumoti bo'yicha mutaxassisligi:</b>\n"
        "<i>Misol: Sun'iy intellekt</i>",
        parse_mode="HTML"
    )
    await state.set_state(ObyektivkaStates.specialty)


# ── 8. Mutaxassislik ──
@router.message(ObyektivkaStates.specialty, F.text)
async def get_specialty(message: Message, state: FSMContext):
    await state.update_data(specialty=message.text.strip())
    await message.answer(
        "✅ Saqlandi!\n\n🔬 <b>Ilmiy darajasi</b> (nomzod, doktor va h.k.):",
        parse_mode="HTML",
        reply_markup=skip_kb()
    )
    await state.set_state(ObyektivkaStates.sci_degree)


# ── 9. Ilmiy daraja ──
@router.message(ObyektivkaStates.sci_degree, F.text)
async def get_sci_degree(message: Message, state: FSMContext):
    await state.update_data(sci_degree=message.text.strip())
    await message.answer(
        "✅ Saqlandi!\n\n🏅 <b>Ilmiy unvoni</b> (dotsent, professor va h.k.):",
        parse_mode="HTML",
        reply_markup=skip_kb()
    )
    await state.set_state(ObyektivkaStates.sci_title)


# ── 10. Ilmiy unvon ──
@router.message(ObyektivkaStates.sci_title, F.text)
async def get_sci_title(message: Message, state: FSMContext):
    await state.update_data(sci_title=message.text.strip())
    await message.answer(
        "✅ Saqlandi!\n\n🌐 <b>Qaysi chet tillarini biladi:</b>\n"
        "<i>Misol: ingliz tili</i>",
        parse_mode="HTML",
        reply_markup=skip_kb()
    )
    await state.set_state(ObyektivkaStates.languages)


# ── 11. Chet tillari ──
@router.message(ObyektivkaStates.languages, F.text)
async def get_languages(message: Message, state: FSMContext):
    await state.update_data(languages=message.text.strip())
    await message.answer(
        "✅ Saqlandi!\n\n⭐ <b>Harbiy (maxsus) unvoni:</b>",
        parse_mode="HTML",
        reply_markup=skip_kb()
    )
    await state.set_state(ObyektivkaStates.military)


# ── 12. Harbiy unvon ──
@router.message(ObyektivkaStates.military, F.text)
async def get_military(message: Message, state: FSMContext):
    await state.update_data(military=message.text.strip())
    await message.answer(
        "✅ Saqlandi!\n\n🏆 <b>Davlat mukofotlari bilan taqdirlangan (qanaqasi):</b>",
        parse_mode="HTML",
        reply_markup=skip_kb()
    )
    await state.set_state(ObyektivkaStates.awards)


# ── 13. Mukofotlar ──
@router.message(ObyektivkaStates.awards, F.text)
async def get_awards(message: Message, state: FSMContext):
    await state.update_data(awards=message.text.strip())
    await message.answer(
        "✅ Saqlandi!\n\n🗳 <b>Xalq deputatimi yoki boshqa saylanadigan organlar a'zosimi?</b>\n"
        "<i>(To'liq ko'rsatilishi lozim)</i>",
        parse_mode="HTML",
        reply_markup=skip_kb()
    )
    await state.set_state(ObyektivkaStates.deputy)


# ── 14. Deputatlik ──
@router.message(ObyektivkaStates.deputy, F.text)
async def get_deputy(message: Message, state: FSMContext):
    await state.update_data(deputy=message.text.strip())
    await message.answer(
        "✅ Saqlandi!\n\n💼 <b>MEHNAT FAOLIYATI</b>\n\n"
        "Ish joylaringizni quyidagi ko'rinishda yozing:\n"
        "<i>Yillar — Tashkilot nomi, Lavozim</i>\n\n"
        "Misol:\n"
        "<i>2022-2026 yy. — OMU talabasi\n"
        "2026 y. — h.v. — 169-sonli maktab, o'qituvchi</i>",
        parse_mode="HTML",
        reply_markup=skip_kb()
    )
    await state.set_state(ObyektivkaStates.work_history)


# ── 15. Mehnat faoliyati ──
@router.message(ObyektivkaStates.work_history, F.text)
async def get_work_history(message: Message, state: FSMContext):
    await state.update_data(work_history=message.text.strip())
    await message.answer(
        "✅ Saqlandi!\n\n📸 Endi <b>3x4 sm fotosuratingizni</b> yuboring:\n"
        "<i>(Ixtiyoriy — o'tkazib yuborish mumkin)</i>",
        parse_mode="HTML",
        reply_markup=skip_kb()
    )
    await state.set_state(ObyektivkaStates.photo)


# ── 16. Fotosurat ──
@router.message(ObyektivkaStates.photo, F.photo)
async def get_photo(message: Message, state: FSMContext):
    photo = message.photo[-1]
    await state.update_data(photo_file_id=photo.file_id)
    await ask_format(message, state)


# ── Skip callback ──
@router.callback_query(F.data == "ob_skip")
async def skip_field(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Yo'q deb belgilandi", show_alert=False)
    current = await state.get_state()

    next_map = {
        ObyektivkaStates.party:        (None,          "party",        ObyektivkaStates.education,   "✅\n\n🎓 <b>Ma'lumoti</b> (oliy / o'rta maxsus / o'rta):"),
        ObyektivkaStates.sci_degree:   (None,          "sci_degree",   ObyektivkaStates.sci_title,   "✅\n\n🏅 <b>Ilmiy unvoni</b> (dotsent, professor va h.k.):"),
        ObyektivkaStates.sci_title:    (None,          "sci_title",    ObyektivkaStates.languages,   "✅\n\n🌐 <b>Qaysi chet tillarini biladi:</b>"),
        ObyektivkaStates.languages:    (None,          "languages",    ObyektivkaStates.military,    "✅\n\n⭐ <b>Harbiy (maxsus) unvoni:</b>"),
        ObyektivkaStates.military:     (None,          "military",     ObyektivkaStates.awards,      "✅\n\n🏆 <b>Davlat mukofotlari bilan taqdirlangan (qanaqasi):</b>"),
        ObyektivkaStates.awards:       (None,          "awards",       ObyektivkaStates.deputy,      "✅\n\n🗳 <b>Xalq deputatimi yoki boshqa saylanadigan organlar a'zosimi?</b>"),
        ObyektivkaStates.deputy:       (None,          "deputy",       ObyektivkaStates.work_history,"✅\n\n💼 <b>MEHNAT FAOLIYATI</b>\n\nMisol:\n<i>2022-2026 yy. — OMU talabasi\n2026 — h.v. — Maktab, o'qituvchi</i>"),
        ObyektivkaStates.work_history: (None,          "work_history", ObyektivkaStates.photo,       "✅\n\n📸 <b>3x4 sm fotosuratingizni</b> yuboring:\n<i>(O'tkazib yuborish mumkin)</i>"),
        ObyektivkaStates.photo:        ("photo",       "photo_file_id",None,                         None),
    }

    entry = next_map.get(current)
    if not entry:
        await callback.answer()
        return

    _, field_key, next_state, next_text = entry
    await state.update_data(**{field_key: "yo'q"})

    if next_state is None:
        # Bu photo holati — formatlash bosqichiga o'tamiz
        await state.update_data(photo_file_id=None)
        await ask_format(callback.message, state)
        return

    await callback.message.edit_text(next_text, parse_mode="HTML", reply_markup=skip_kb())
    await state.set_state(next_state)


# ── Format so'rash ──
async def ask_format(message: Message, state: FSMContext):
    await message.answer(
        "✅ Barcha ma'lumotlar yig'ildi!\n\n"
        "📁 Obyektivkani qaysi formatda olmoqchisiz?",
        reply_markup=format_kb()
    )
    await state.set_state(ObyektivkaStates.choose_fmt)


# ── Obyektivka yaratish ──
async def send_report(message: Message, state: FSMContext, fmt: str):
    data = await state.get_data()
    await state.clear()

    name_part = data.get('full_name', 'obyektivka').replace(' ', '_')[:30]
    wait_msg = await message.answer("⏳ Obyektivka tayyorlanmoqda...")

    # Fotosurat yuklab olish
    photo_bytes = None
    photo_file_id = data.get('photo_file_id')
    if photo_file_id and photo_file_id != "yo'q":
        try:
            bot = message.bot
            file = await bot.get_file(photo_file_id)
            photo_io = __import__('io').BytesIO()
            await bot.download_file(file.file_path, photo_io)
            photo_bytes = photo_io.getvalue()
        except Exception as e:
            logging.warning(f"Fotosurat yuklab bo'lmadi: {e}")

    try:
        if fmt in ('pdf', 'both'):
            pdf_bytes = generate_pdf(data, photo_bytes=photo_bytes)
            await message.answer_document(
                BufferedInputFile(pdf_bytes, filename=f"{name_part}_obyektivka.pdf"),
                caption="📄 <b>Ma'lumotnoma (PDF)</b> tayyor!",
                parse_mode="HTML"
            )

        if fmt in ('excel', 'both'):
            excel_bytes = generate_excel(data)
            await message.answer_document(
                BufferedInputFile(excel_bytes, filename=f"{name_part}_obyektivka.xlsx"),
                caption="📊 <b>Ma'lumotnoma (Excel)</b> tayyor!",
                parse_mode="HTML"
            )

        await wait_msg.delete()

        from keyboards.reply import get_main_menu
        await message.answer(
            "✅ Tayyor! Boshqa xizmatlardan foydalanish uchun menyudan tanlang 👇",
            reply_markup=get_main_menu()
        )

    except Exception as e:
        logging.error(f"Obyektivka yaratishda xato: {e}", exc_info=True)
        await wait_msg.edit_text("❌ Obyektivka yaratishda xatolik yuz berdi. Keyinroq urinib ko'ring.")


@router.callback_query(F.data == "report_fmt_pdf", ObyektivkaStates.choose_fmt)
async def fmt_pdf(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text("📄 PDF tayyorlanmoqda...")
    await send_report(callback.message, state, 'pdf')


@router.callback_query(F.data == "report_fmt_excel", ObyektivkaStates.choose_fmt)
async def fmt_excel(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text("📊 Excel tayyorlanmoqda...")
    await send_report(callback.message, state, 'excel')


@router.callback_query(F.data == "report_fmt_both", ObyektivkaStates.choose_fmt)
async def fmt_both(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text("📦 PDF va Excel tayyorlanmoqda...")
    await send_report(callback.message, state, 'both')
