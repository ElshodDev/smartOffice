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
    # --- Asosiy ma'lumotlar ---
    full_name    = State()
    birth_date   = State()
    birth_place  = State()
    nationality  = State()
    party        = State()
    education    = State()
    graduated    = State()
    specialty    = State()
    sci_degree   = State()
    sci_title    = State()
    languages    = State()
    military     = State()
    awards       = State()
    deputy       = State()
    work_history = State()
    # --- Qarindoshlar (2-sahifa) ---
    rel_father   = State()   # Otasi
    rel_mother   = State()   # Onasi
    rel_spouse   = State()   # Turmush o'rtog'i
    rel_children = State()   # Farzandlari
    rel_siblings = State()   # Aka-uka / Opa-singillar
    # --- Yakunlovchi ---
    photo        = State()
    choose_fmt   = State()


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

# Qarindosh kiritish uchun format eslatmasi
def rel_hint(role: str) -> str:
    return (
        f"👨‍👩‍👧 <b>{role}</b> haqida ma'lumot kiriting:\n\n"
        "<b>Namuna:</b>\n"
        "F.I.Sh.: Abdullayev Bahodir Hamidovich\n"
        "Tug'ilgan yili va joyi: 1965, Samarqand vil.\n"
        "Ish joyi va lavozimi: Pensioner\n"
        "Yashash manzili: Toshkent sh., Yunusobod t.\n\n"
        "<i>Har bir qatorni alohida-alohida yozing yoki barchasini bir xabarda yuboring. "
        "Yo'q bo'lsa — tugmani bosing.</i>"
    )


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
        "<i>Misol: Abdullayev Elshod Mahmadali o'g'li</i>",
        parse_mode="HTML"
    )
    await state.set_state(ObyektivkaStates.full_name)


# ── 1. F.I.Sh ──
@router.message(ObyektivkaStates.full_name, F.text)
async def get_full_name(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text.strip())
    await message.answer(
        "✅ Saqlandi!\n\n📅 <b>Tug'ilgan yili:</b>\n<i>Misol: 08.06.2004</i>",
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
        "✅ Saqlandi!\n\n🌍 <b>Millati:</b>\n<i>Misol: o'zbek</i>",
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
        "<i>Misol: 2026 y. O'zMU, bakalavr</i>",
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
        "<i>Misol:\n"
        "2022-2026 — O'zMU, talaba\n"
        "2026 — h.v. — 169-maktab, o'qituvchi</i>",
        parse_mode="HTML",
        reply_markup=skip_kb()
    )
    await state.set_state(ObyektivkaStates.work_history)


# ── 15. Mehnat faoliyati ──
@router.message(ObyektivkaStates.work_history, F.text)
async def get_work_history(message: Message, state: FSMContext):
    await state.update_data(work_history=message.text.strip())
    await ask_relatives_start(message)
    await state.set_state(ObyektivkaStates.rel_father)


# ── Qarindoshlar bo'limiga kirish ──
async def ask_relatives_start(message: Message):
    await message.answer(
        "✅ Saqlandi!\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "👨‍👩‍👧 <b>YAQIN QARINDOSHLAR (2-sahifa)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Endi har bir yaqin qarindoshingiz haqida ma'lumot so'rayman.\n"
        "Ma'lumot yo'q bo'lsa — <b>\"⏩ Yo'q\"</b> tugmasini bosing.\n\n"
        "Birinchi: <b>Otangiz</b> haqida →",
        parse_mode="HTML"
    )


# ── 16. Otasi ──
@router.message(ObyektivkaStates.rel_father, F.text)
async def get_rel_father_start(message: Message, state: FSMContext):
    # bu holat trigger bo'lmasligi kerak — handler yo'q degan signal
    pass

async def _ask_rel(message: Message, state, role: str, next_state):
    await message.answer(rel_hint(role), parse_mode="HTML", reply_markup=skip_kb())
    await state.set_state(next_state)


# Har bir qarindosh uchun alohida trigger — ask_rel_father → ask_rel_mother ...
# Otasini so'rash
@router.message(ObyektivkaStates.rel_father, F.text)
async def noop_father(message: Message, state: FSMContext):
    pass  # Covered by ob_skip

async def send_father_question(message: Message, state: FSMContext):
    await message.answer(rel_hint("Otasi"), parse_mode="HTML", reply_markup=skip_kb())
    await state.set_state(ObyektivkaStates.rel_father)


# ── Yetarli — oddiyroq yondashuv: bitta handler ketma-ket holatlar uchun ──
# Butun qarindoshlar zanjiri: father → mother → spouse → children → siblings → photo

RELATIVE_CHAIN = [
    ("rel_father",   "Otasi",             ObyektivkaStates.rel_father),
    ("rel_mother",   "Onasi",             ObyektivkaStates.rel_mother),
    ("rel_spouse",   "Turmush o'rtog'i",  ObyektivkaStates.rel_spouse),
    ("rel_children", "Farzandlari",       ObyektivkaStates.rel_children),
    ("rel_siblings", "Aka-uka/Opa-singillar", ObyektivkaStates.rel_siblings),
]


def _next_relative(current_key: str):
    """Joriy qarindosh kalitidan keyingisini qaytaradi."""
    keys = [r[0] for r in RELATIVE_CHAIN]
    if current_key in keys:
        idx = keys.index(current_key)
        if idx + 1 < len(RELATIVE_CHAIN):
            return RELATIVE_CHAIN[idx + 1]
    return None


async def _save_and_advance(message_or_cb, state: FSMContext, field_key: str, value: str):
    """Ma'lumotni saqlaydi va keyingi qarindoshga o'tadi yoki fotoga o'tadi."""
    await state.update_data(**{field_key: value})
    next_rel = _next_relative(field_key)
    if next_rel:
        nkey, nrole, nstate = next_rel
        await state.set_state(nstate)
        await message_or_cb.answer(rel_hint(nrole), parse_mode="HTML", reply_markup=skip_kb())
    else:
        # Hamma qarindoshlar tugadi → Fotoga o'tamiz
        await message_or_cb.answer(
            "✅ Barcha qarindoshlar saqlandi!\n\n"
            "📸 Endi <b>3x4 sm fotosuratingizni</b> yuboring:\n"
            "<i>(Ixtiyoriy — o'tkazib yuborish mumkin)</i>",
            parse_mode="HTML",
            reply_markup=skip_kb()
        )
        await state.set_state(ObyektivkaStates.photo)


# ── Otasi ──
@router.message(ObyektivkaStates.rel_father, F.text)
async def get_rel_father(message: Message, state: FSMContext):
    await _save_and_advance(message, state, "rel_father", message.text.strip())

# ── Onasi ──
@router.message(ObyektivkaStates.rel_mother, F.text)
async def get_rel_mother(message: Message, state: FSMContext):
    await _save_and_advance(message, state, "rel_mother", message.text.strip())

# ── Turmush o'rtog'i ──
@router.message(ObyektivkaStates.rel_spouse, F.text)
async def get_rel_spouse(message: Message, state: FSMContext):
    await _save_and_advance(message, state, "rel_spouse", message.text.strip())

# ── Farzandlari ──
@router.message(ObyektivkaStates.rel_children, F.text)
async def get_rel_children(message: Message, state: FSMContext):
    await _save_and_advance(message, state, "rel_children", message.text.strip())

# ── Aka-uka/Opa-singillar ──
@router.message(ObyektivkaStates.rel_siblings, F.text)
async def get_rel_siblings(message: Message, state: FSMContext):
    await _save_and_advance(message, state, "rel_siblings", message.text.strip())


# ── Skip callback — barcha ixtiyoriy maydonlar uchun ──
@router.callback_query(F.data == "ob_skip")
async def skip_field(callback: CallbackQuery, state: FSMContext):
    await callback.answer("O'tkazib yuborildi", show_alert=False)
    current = await state.get_state()

    # --- Asosiy ma'lumotlar skip map ---
    main_skip_map = {
        ObyektivkaStates.party.state:        ("party",        ObyektivkaStates.education,   "✅\n\n🎓 <b>Ma'lumoti</b> (oliy / o'rta maxsus / o'rta):"),
        ObyektivkaStates.sci_degree.state:   ("sci_degree",   ObyektivkaStates.sci_title,   "✅\n\n🏅 <b>Ilmiy unvoni</b> (dotsent, professor va h.k.):"),
        ObyektivkaStates.sci_title.state:    ("sci_title",    ObyektivkaStates.languages,   "✅\n\n🌐 <b>Qaysi chet tillarini biladi:</b>"),
        ObyektivkaStates.languages.state:    ("languages",    ObyektivkaStates.military,    "✅\n\n⭐ <b>Harbiy (maxsus) unvoni:</b>"),
        ObyektivkaStates.military.state:     ("military",     ObyektivkaStates.awards,      "✅\n\n🏆 <b>Davlat mukofotlari bilan taqdirlangan (qanaqasi):</b>"),
        ObyektivkaStates.awards.state:       ("awards",       ObyektivkaStates.deputy,      "✅\n\n🗳 <b>Xalq deputatimi yoki boshqa saylanadigan organlar a'zosimi?</b>"),
        ObyektivkaStates.deputy.state:       ("deputy",       ObyektivkaStates.work_history,
            "✅\n\n💼 <b>MEHNAT FAOLIYATI</b>\n\n"
            "Misol:\n<i>2022-2026 — O'zMU, talaba\n2026 — h.v. — Maktab, o'qituvchi</i>"),
        ObyektivkaStates.work_history.state: ("work_history", None, None),  # Qarindoshlarga o'tadi
    }

    if current in main_skip_map:
        field_key, next_state, next_text = main_skip_map[current]
        await state.update_data(**{field_key: "yo'q"})

        if field_key == "work_history":
            await state.update_data(work_history="yo'q")
            await ask_relatives_start(callback.message)
            first = RELATIVE_CHAIN[0]
            await state.set_state(first[2])
            await callback.message.answer(rel_hint(first[1]), parse_mode="HTML", reply_markup=skip_kb())
            return

        await callback.message.edit_text(next_text, parse_mode="HTML", reply_markup=skip_kb())
        await state.set_state(next_state)
        return

    # --- Qarindoshlar skip ---
    rel_keys = [r[0] for r in RELATIVE_CHAIN]
    # Joriy state nomidan field_key topamiz
    for rkey, rrole, rstate in RELATIVE_CHAIN:
        if current == rstate.state:
            await _save_and_advance(callback.message, state, rkey, "yo'q")
            return

    # --- Fotosurat skip ---
    if current == ObyektivkaStates.photo.state:
        await state.update_data(photo_file_id=None)
        await ask_format(callback.message, state)
        return


# ── Fotosurat ──
@router.message(ObyektivkaStates.photo, F.photo)
async def get_photo(message: Message, state: FSMContext):
    photo = message.photo[-1]
    await state.update_data(photo_file_id=photo.file_id)
    await ask_format(message, state)


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
            file = await message.bot.get_file(photo_file_id)
            photo_io = io.BytesIO()
            await message.bot.download_file(file.file_path, photo_io)
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
        await wait_msg.edit_text("❌ Xatolik yuz berdi. Keyinroq urinib ko'ring.")


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
