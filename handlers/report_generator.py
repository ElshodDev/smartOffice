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
    # --- Qarindoshlar ---
    rel_father   = State()
    rel_mother   = State()
    rel_spouse   = State()
    rel_children = State()
    rel_siblings = State()
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
        [InlineKeyboardButton(text="📦 Ikkalasi ham", callback_data="report_fmt_both")],
    ])

def rel_hint(role: str) -> str:
    return (
        f"👨‍👩‍👧 <b>{role}</b> haqida ma'lumot kiriting:\n\n"
        "<b>Quyidagi tartibda (har biri yangi qatorda):</b>\n"
        "<i>1-qator: F.I.Sh. va Tug'ilgan yili\n"
        "2-qator: Ish joyi va lavozimi\n"
        "3-qator: Yashash manzili</i>\n\n"
        "<b>Namuna:</b>\n"
        "<code>Eshmatov Ali Toshmatovich, 1965-yil\n"
        "Pensioner\n"
        "Toshkent sh., Yunusobod t.</code>\n\n"
        "<i>💡 Agar ular bir nechta bo'lsa, xuddi shu tartibda pastdan qo'shib yozib ketavering.</i>"
    )


# ── Boshlash ──
@router.message(F.text == "📋 Ma'lumotnoma (Obyektivka)")
async def start_report(message: Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "📋 <b>Ma'lumotnoma (Obyektivka) Yaratish</b>\n\n"
        "Standart O'zbek Obyektivkasini tayyorlayman.\n"
        "Har bir savolga javob bering. Ixtiyoriy bo'lganlarda <b>⏩</b> tugmasini bosing.\n\n"
        "👤 <b>F.I.Sh.</b> (To'liq familiya ism sharif):\n"
        "<i>Misol: Eshmatov Toshmat Eshmatovich</i>",
        parse_mode="HTML"
    )
    await state.set_state(ObyektivkaStates.full_name)


# ═══════════════ ASOSIY MA'LUMOTLAR ═══════════════

@router.message(ObyektivkaStates.full_name, F.text)
async def s01_full_name(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text.strip())
    await message.answer("✅ Saqlandi!\n\n📅 <b>Tug'ilgan yili:</b>\n<i>Misol: 15.08.1990 y.</i>", parse_mode="HTML")
    await state.set_state(ObyektivkaStates.birth_date)


@router.message(ObyektivkaStates.birth_date, F.text)
async def s02_birth_date(message: Message, state: FSMContext):
    await state.update_data(birth_date=message.text.strip())
    await message.answer(
        "✅ Saqlandi!\n\n📍 <b>Tug'ilgan joyi</b> (viloyat, tuman):\n"
        "<i>Misol: Toshkent viloyati, Parkent tumani</i>",
        parse_mode="HTML"
    )
    await state.set_state(ObyektivkaStates.birth_place)


@router.message(ObyektivkaStates.birth_place, F.text)
async def s03_birth_place(message: Message, state: FSMContext):
    await state.update_data(birth_place=message.text.strip())
    await message.answer("✅ Saqlandi!\n\n🌍 <b>Millati:</b>\n<i>Misol: o'zbek</i>", parse_mode="HTML")
    await state.set_state(ObyektivkaStates.nationality)


@router.message(ObyektivkaStates.nationality, F.text)
async def s04_nationality(message: Message, state: FSMContext):
    await state.update_data(nationality=message.text.strip())
    await message.answer(
        "✅ Saqlandi!\n\n🏛 <b>Partiyaviyligi</b> (qaysi partiya a'zosi):\n<i>(Yo'q bo'lsa tugmani bosing)</i>",
        parse_mode="HTML",
        reply_markup=skip_kb()
    )
    await state.set_state(ObyektivkaStates.party)


@router.message(ObyektivkaStates.party, F.text)
async def s05_party(message: Message, state: FSMContext):
    await state.update_data(party=message.text.strip())
    await message.answer(
        "✅ Saqlandi!\n\n🎓 <b>Ma'lumoti</b> (oliy / o'rta maxsus / o'rta):",
        parse_mode="HTML"
    )
    await state.set_state(ObyektivkaStates.education)


@router.message(ObyektivkaStates.education, F.text)
async def s06_education(message: Message, state: FSMContext):
    await state.update_data(education=message.text.strip())
    await message.answer(
        "✅ Saqlandi!\n\n🏫 <b>Tamomlagan</b> (o'quv yurti, yili, bosqichi):\n"
        "<i>Misol: 2015 y. Toshkent Davlat Iqtisodiyot Universiteti, bakalavr</i>",
        parse_mode="HTML"
    )
    await state.set_state(ObyektivkaStates.graduated)


@router.message(ObyektivkaStates.graduated, F.text)
async def s07_graduated(message: Message, state: FSMContext):
    await state.update_data(graduated=message.text.strip())
    await message.answer(
        "✅ Saqlandi!\n\n📚 <b>Ma'lumoti bo'yicha mutaxassisligi:</b>\n<i>Misol: Iqtisodchi</i>",
        parse_mode="HTML"
    )
    await state.set_state(ObyektivkaStates.specialty)


@router.message(ObyektivkaStates.specialty, F.text)
async def s08_specialty(message: Message, state: FSMContext):
    await state.update_data(specialty=message.text.strip())
    await message.answer(
        "✅ Saqlandi!\n\n🔬 <b>Ilmiy darajasi:</b>\n<i>(Yo'q bo'lsa tugmani bosing)</i>",
        parse_mode="HTML",
        reply_markup=skip_kb()
    )
    await state.set_state(ObyektivkaStates.sci_degree)


@router.message(ObyektivkaStates.sci_degree, F.text)
async def s09_sci_degree(message: Message, state: FSMContext):
    await state.update_data(sci_degree=message.text.strip())
    await message.answer(
        "✅ Saqlandi!\n\n🏅 <b>Ilmiy unvoni:</b>\n<i>(Yo'q bo'lsa tugmani bosing)</i>",
        parse_mode="HTML",
        reply_markup=skip_kb()
    )
    await state.set_state(ObyektivkaStates.sci_title)


@router.message(ObyektivkaStates.sci_title, F.text)
async def s10_sci_title(message: Message, state: FSMContext):
    await state.update_data(sci_title=message.text.strip())
    await message.answer(
        "✅ Saqlandi!\n\n🌐 <b>Qaysi chet tillarini biladi:</b>\n<i>Misol: ingliz tili</i>\n<i>(Yo'q bo'lsa tugmani bosing)</i>",
        parse_mode="HTML",
        reply_markup=skip_kb()
    )
    await state.set_state(ObyektivkaStates.languages)


@router.message(ObyektivkaStates.languages, F.text)
async def s11_languages(message: Message, state: FSMContext):
    await state.update_data(languages=message.text.strip())
    await message.answer(
        "✅ Saqlandi!\n\n⭐ <b>Harbiy (maxsus) unvoni:</b>\n<i>(Yo'q bo'lsa tugmani bosing)</i>",
        parse_mode="HTML",
        reply_markup=skip_kb()
    )
    await state.set_state(ObyektivkaStates.military)


@router.message(ObyektivkaStates.military, F.text)
async def s12_military(message: Message, state: FSMContext):
    await state.update_data(military=message.text.strip())
    await message.answer(
        "✅ Saqlandi!\n\n🏆 <b>Davlat mukofotlari bilan taqdirlangan (qanaqasi):</b>\n<i>(Yo'q bo'lsa tugmani bosing)</i>",
        parse_mode="HTML",
        reply_markup=skip_kb()
    )
    await state.set_state(ObyektivkaStates.awards)


@router.message(ObyektivkaStates.awards, F.text)
async def s13_awards(message: Message, state: FSMContext):
    await state.update_data(awards=message.text.strip())
    await message.answer(
        "✅ Saqlandi!\n\n🗳 <b>Xalq deputatimi yoki saylanadigan organlar a'zosimi?</b>\n"
        "<i>(To'liq ko'rsatilishi lozim. Yo'q bo'lsa tugmani bosing)</i>",
        parse_mode="HTML",
        reply_markup=skip_kb()
    )
    await state.set_state(ObyektivkaStates.deputy)


@router.message(ObyektivkaStates.deputy, F.text)
async def s14_deputy(message: Message, state: FSMContext):
    await state.update_data(deputy=message.text.strip())
    await message.answer(
        "✅ Saqlandi!\n\n💼 <b>MEHNAT FAOLIYATI</b>\n\n"
        "Ish joylarini quyidagi ko'rinishda yozing:\n"
        "<i>2011-2015 — TDIU, talaba\n2015 — h.v. — Bank, menejer</i>\n\n"
        "<i>(Yo'q bo'lsa tugmani bosing)</i>",
        parse_mode="HTML",
        reply_markup=skip_kb()
    )
    await state.set_state(ObyektivkaStates.work_history)


@router.message(ObyektivkaStates.work_history, F.text)
async def s15_work_history(message: Message, state: FSMContext):
    await state.update_data(work_history=message.text.strip())
    await _ask_father(message, state)


async def _ask_father(message: Message, state: FSMContext):
    await message.answer(
        "✅ Saqlandi!\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "👨‍👩‍👧 <b>YAQIN QARINDOSHLAR (2-sahifa)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Endi har bir qarindoshingiz haqida so'rayman.\n"
        "Ma'lumot yo'q bo'lsa — <b>⏩</b> tugmasini bosing.\n\n" +
        rel_hint("Otasi"),
        parse_mode="HTML",
        reply_markup=skip_kb()
    )
    await state.set_state(ObyektivkaStates.rel_father)


# ═══════════════ QARINDOSHLAR ═══════════════

@router.message(ObyektivkaStates.rel_father, F.text)
async def r01_father(message: Message, state: FSMContext):
    await state.update_data(rel_father=message.text.strip())
    await message.answer(rel_hint("Onasi"), parse_mode="HTML", reply_markup=skip_kb())
    await state.set_state(ObyektivkaStates.rel_mother)


@router.message(ObyektivkaStates.rel_mother, F.text)
async def r02_mother(message: Message, state: FSMContext):
    await state.update_data(rel_mother=message.text.strip())
    await message.answer(rel_hint("Turmush o'rtog'i"), parse_mode="HTML", reply_markup=skip_kb())
    await state.set_state(ObyektivkaStates.rel_spouse)


@router.message(ObyektivkaStates.rel_spouse, F.text)
async def r03_spouse(message: Message, state: FSMContext):
    await state.update_data(rel_spouse=message.text.strip())
    await message.answer(rel_hint("Farzandlari"), parse_mode="HTML", reply_markup=skip_kb())
    await state.set_state(ObyektivkaStates.rel_children)


@router.message(ObyektivkaStates.rel_children, F.text)
async def r04_children(message: Message, state: FSMContext):
    await state.update_data(rel_children=message.text.strip())
    await message.answer(rel_hint("Aka-uka / Opa-singillar"), parse_mode="HTML", reply_markup=skip_kb())
    await state.set_state(ObyektivkaStates.rel_siblings)


@router.message(ObyektivkaStates.rel_siblings, F.text)
async def r05_siblings(message: Message, state: FSMContext):
    await state.update_data(rel_siblings=message.text.strip())
    await _ask_photo(message, state)


async def _ask_photo(message: Message, state: FSMContext):
    await message.answer(
        "✅ Barcha qarindoshlar saqlandi!\n\n"
        "📸 <b>3x4 sm fotosuratingizni</b> yuboring:\n"
        "<i>(Ixtiyoriy — o'tkazib yuborish mumkin)</i>",
        parse_mode="HTML",
        reply_markup=skip_kb()
    )
    await state.set_state(ObyektivkaStates.photo)


# ── Fotosurat ──
@router.message(ObyektivkaStates.photo, F.photo)
async def r06_photo(message: Message, state: FSMContext):
    photo = message.photo[-1]
    await state.update_data(photo_file_id=photo.file_id)
    await ask_format(message, state)


# ═══════════════ SKIP CALLBACK ═══════════════

# Har bir holatga skip uchun qaysi field va keyingi qadam
SKIP_MAP = {
    ObyektivkaStates.party.state: {
        "field": "party", "action": "next_required",
        "text": "✅\n\n🎓 <b>Ma'lumoti</b> (oliy / o'rta maxsus / o'rta):",
        "next": ObyektivkaStates.education
    },
    ObyektivkaStates.sci_degree.state: {
        "field": "sci_degree", "action": "next_optional",
        "text": "✅\n\n🏅 <b>Ilmiy unvoni:</b>\n<i>(Yo'q bo'lsa tugmani bosing)</i>",
        "next": ObyektivkaStates.sci_title
    },
    ObyektivkaStates.sci_title.state: {
        "field": "sci_title", "action": "next_optional",
        "text": "✅\n\n🌐 <b>Qaysi chet tillarini biladi:</b>\n<i>(Yo'q bo'lsa tugmani bosing)</i>",
        "next": ObyektivkaStates.languages
    },
    ObyektivkaStates.languages.state: {
        "field": "languages", "action": "next_optional",
        "text": "✅\n\n⭐ <b>Harbiy (maxsus) unvoni:</b>\n<i>(Yo'q bo'lsa tugmani bosing)</i>",
        "next": ObyektivkaStates.military
    },
    ObyektivkaStates.military.state: {
        "field": "military", "action": "next_optional",
        "text": "✅\n\n🏆 <b>Davlat mukofotlari bilan taqdirlangan:</b>\n<i>(Yo'q bo'lsa tugmani bosing)</i>",
        "next": ObyektivkaStates.awards
    },
    ObyektivkaStates.awards.state: {
        "field": "awards", "action": "next_optional",
        "text": "✅\n\n🗳 <b>Xalq deputatimi yoki saylanadigan organlar a'zosimi?</b>\n<i>(Yo'q bo'lsa tugmani bosing)</i>",
        "next": ObyektivkaStates.deputy
    },
    ObyektivkaStates.deputy.state: {
        "field": "deputy", "action": "next_optional",
        "text": (
            "✅\n\n💼 <b>MEHNAT FAOLIYATI</b>\n\n"
            "Misol:\n<i>2011-2015 — TDIU, talaba\n2015 — h.v. — Bank, menejer</i>\n\n"
            "<i>(Yo'q bo'lsa tugmani bosing)</i>"
        ),
        "next": ObyektivkaStates.work_history
    },
    ObyektivkaStates.work_history.state: {"field": "work_history", "action": "ask_father"},
    ObyektivkaStates.rel_father.state:   {"field": "rel_father",   "action": "next_rel", "next_role": "Onasi",                   "next": ObyektivkaStates.rel_mother},
    ObyektivkaStates.rel_mother.state:   {"field": "rel_mother",   "action": "next_rel", "next_role": "Turmush o'rtog'i",         "next": ObyektivkaStates.rel_spouse},
    ObyektivkaStates.rel_spouse.state:   {"field": "rel_spouse",   "action": "next_rel", "next_role": "Farzandlari",             "next": ObyektivkaStates.rel_children},
    ObyektivkaStates.rel_children.state: {"field": "rel_children", "action": "next_rel", "next_role": "Aka-uka / Opa-singillar", "next": ObyektivkaStates.rel_siblings},
    ObyektivkaStates.rel_siblings.state: {"field": "rel_siblings", "action": "ask_photo"},
    ObyektivkaStates.photo.state:        {"field": "photo_file_id", "action": "ask_format"},
}


@router.callback_query(F.data == "ob_skip")
async def skip_field(callback: CallbackQuery, state: FSMContext):
    await callback.answer("O'tkazib yuborildi")
    current = await state.get_state()

    entry = SKIP_MAP.get(current)
    if not entry:
        return

    # Ma'lumotni "yo'q" deb saqlash
    field = entry["field"]
    await state.update_data(**{field: "yo'q" if field != "photo_file_id" else None})

    action = entry["action"]

    if action == "next_required":
        # Skip button ko'rsatilmaydi (majburiy maydon)
        await callback.message.edit_text(entry["text"], parse_mode="HTML")
        await state.set_state(entry["next"])

    elif action == "next_optional":
        await callback.message.edit_text(entry["text"], parse_mode="HTML", reply_markup=skip_kb())
        await state.set_state(entry["next"])

    elif action == "next_rel":
        await callback.message.answer(rel_hint(entry["next_role"]), parse_mode="HTML", reply_markup=skip_kb())
        await state.set_state(entry["next"])

    elif action == "ask_father":
        await _ask_father(callback.message, state)

    elif action == "ask_photo":
        await _ask_photo(callback.message, state)

    elif action == "ask_format":
        await ask_format(callback.message, state)


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

    photo_bytes = None
    photo_file_id = data.get('photo_file_id')
    if photo_file_id and photo_file_id not in ("yo'q", None):
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
