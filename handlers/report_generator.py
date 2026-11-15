"""
📋 Obyektivka (ma'lumotnoma): savol-javob → standart shakldagi PDF / Excel.

Tartib: asosiy ma'lumotlar (hozirgi lavozim bilan) → mehnat faoliyati → yaqin qarindoshlar
(birma-bir, 5 ustunli jadval uchun) → 3×4 fotosurat (yuz bo'yicha avtomatik kadrlanadi) → format.
"""
import base64
import html
import logging
import os

from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from services.converter_service import run_heavy, MAX_FILE_SIZE, IMAGE_EXTENSIONS
from services.excel_report import generate_excel
from services.obyektivka_photo import make_photo
from services.pdf_report import generate_pdf
from services.tempfiles import new_job_dir, remove, safe_filename
from services.alphabet import esc as uesc, raw

router = Router()

MAX_ANSWER = 700
MAX_RELATIVES = 25

# key, savol, namuna, ixtiyoriy
FIELDS = [
    ("full_name", "👤 Familiya, ism, otasining ismi (to'liq)", "Karimova Dilnoza Rustamovna", False),
    ("current_position", "💼 Hozirgi ish joyi va lavozimi (qachondan)",
     "2020 yil 1 sentyabrdan: «Ziyo» MChJ bosh buxgalteri", True),
    ("birth_date", "📅 Tug'ilgan yili (sanasi)", "15.08.1990", False),
    ("birth_place", "📍 Tug'ilgan joyi", "Toshkent viloyati, Qibray tumani", False),
    ("nationality", "🌍 Millati", "o'zbek", False),
    ("party", "🏛 Partiyaviyligi", "yo'q", True),
    ("education", "🎓 Ma'lumoti", "oliy", False),
    ("graduated", "🏫 Tamomlagan (yili, o'quv yurti)", "2012 y. Toshkent moliya instituti (kunduzgi)", False),
    ("specialty", "📚 Ma'lumoti bo'yicha mutaxassisligi", "Buxgalteriya hisobi va audit", False),
    ("sci_degree", "🔬 Ilmiy darajasi", "yo'q", True),
    ("sci_title", "🏅 Ilmiy unvoni", "yo'q", True),
    ("languages", "🌐 Qaysi chet tillarini biladi", "ingliz, rus", True),
    ("military", "⭐ Harbiy (maxsus) unvoni", "yo'q", True),
    ("awards", "🏆 Davlat mukofotlari bilan taqdirlanganmi (qanaqa)", "yo'q", True),
    ("deputy", "🗳 Xalq deputatlari Kengashi deputatimi yoki boshqa saylanadigan organ a'zosimi", "yo'q", True),
    ("work_history", "🗂 MEHNAT FAOLIYATI — har bir ish joyi yangi qatorda: «yillar — ish joyi va lavozimi»",
     "2012-2014 yy. — «Ziyo» MChJ buxgalteri\n2014-2020 yy. — Toshkent shahar moliya boshqarmasi yetakchi mutaxassisi\n"
     "2020 y. — h.v. — «Ziyo» MChJ bosh buxgalteri", True),
]

RELATIONS = ["Otasi", "Onasi", "Turmush o'rtog'i", "O'g'li", "Qizi", "Akasi", "Ukasi", "Opasi", "Singlisi",
             "Qaynotasi", "Qaynonasi"]


class ObyektivkaStates(StatesGroup):
    answering = State()
    relatives = State()
    relative_entry = State()
    photo = State()
    photo_confirm = State()
    choose_fmt = State()


def _field_keyboard(index: int) -> InlineKeyboardMarkup | None:
    rows = []
    if FIELDS[index][3]:
        rows.append([InlineKeyboardButton(text="⏩ Yo'q / O'tkazib yuborish", callback_data="ob_skip")])
    if index > 0:
        rows.append([InlineKeyboardButton(text="⬅️ Oldingi savol", callback_data="ob_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


async def _ask_field(message: Message, state: FSMContext):
    index = (await state.get_data())["index"]
    key, question, example, optional = FIELDS[index]
    text = f"<b>{index + 1}/{len(FIELDS)}. {html.escape(question)}</b>"
    if example:
        text += f"\n\n<i>Namuna:</i>\n<code>{html.escape(example)}</code>"
    if optional:
        text += "\n\n<i>Yo'q bo'lsa — ⏩ tugmasini bosing.</i>"
    await message.answer(text, parse_mode="HTML", reply_markup=_field_keyboard(index))


async def _start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(ObyektivkaStates.answering)
    await state.update_data(index=0, values={}, relatives=[], photo_b64=None)
    await message.answer(
        "📋 <b>Obyektivka (ma'lumotnoma)</b>\n\n"
        "Standart shakldagi obyektivkani tayyorlayman: 1-sahifa — shaxsiy ma'lumotlar va mehnat faoliyati, "
        "2-sahifa — yaqin qarindoshlar jadvali. Rasmingizni 3×4 sm formatga o'zim keltiraman.\n\n"
        "<i>Xato yozsangiz — «⬅️ Oldingi savol» bilan qaytishingiz mumkin. To'xtatish: /cancel</i>",
        parse_mode="HTML",
    )
    await _ask_field(message, state)


@router.message(F.text == "📋 Ma'lumotnoma (Obyektivka)")
async def start_report(message: Message, state: FSMContext):
    await _start(message, state)


@router.callback_query(F.data == "ob_start")
async def start_report_cb(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await _start(callback.message, state)


async def _next_field(message: Message, state: FSMContext, value: str):
    data = await state.get_data()
    values = dict(data["values"])
    values[FIELDS[data["index"]][0]] = value
    index = data["index"] + 1
    await state.update_data(values=values, index=index)
    if index < len(FIELDS):
        await _ask_field(message, state)
    else:
        await _ask_relatives(message, state, first=True)


@router.message(ObyektivkaStates.answering, F.text)
async def answer_field(message: Message, state: FSMContext):
    text = message.text.strip()
    if text.startswith("/"):
        return
    if len(text) > MAX_ANSWER * (3 if FIELDS[(await state.get_data())["index"]][0] == "work_history" else 1):
        await message.answer("❌ Javob juda uzun. Qisqartirib qayta yuboring:")
        return
    await _next_field(message, state, text)


@router.callback_query(ObyektivkaStates.answering, F.data == "ob_skip")
async def skip_field(callback: CallbackQuery, state: FSMContext):
    index = (await state.get_data())["index"]
    if not FIELDS[index][3]:
        await callback.answer("Bu savol majburiy", show_alert=True)
        return
    await callback.answer("O'tkazib yuborildi")
    await callback.message.edit_reply_markup(reply_markup=None)
    await _next_field(callback.message, state, "yo'q")


@router.callback_query(ObyektivkaStates.answering, F.data == "ob_back")
async def back_field(callback: CallbackQuery, state: FSMContext):
    index = (await state.get_data())["index"]
    await callback.answer()
    if index > 0:
        await state.update_data(index=index - 1)
        await callback.message.edit_reply_markup(reply_markup=None)
        await _ask_field(callback.message, state)


# ── Yaqin qarindoshlar ─────────────────────────────────────────────────────
def _relations_keyboard(count: int) -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(text=r, callback_data=f"ob_rel:{i}") for i, r in enumerate(RELATIONS)]
    rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    rows.append([InlineKeyboardButton(text=f"✅ Qarindoshlar kiritildi ({count} ta) — davom etish", callback_data="ob_rel_done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _ask_relatives(message: Message, state: FSMContext, first: bool = False):
    await state.set_state(ObyektivkaStates.relatives)
    relatives = (await state.get_data()).get("relatives", [])
    if first:
        text = ("👨‍👩‍👧 <b>YAQIN QARINDOSHLAR (2-sahifa)</b>\n\n"
                "Qarindoshlarni birma-bir qo'shing: avval kimligini tanlang, so'ng ma'lumotini yozing.\n"
                "Odatda: ota-ona, turmush o'rtog'i, farzandlar, aka-uka va opa-singillar, qaynota va qaynona.")
    else:
        listing = "\n".join(f"{i}. {uesc(r['rel'])} — {uesc(r['name'])}" for i, r in enumerate(relatives, 1))
        text = f"✅ Qo'shildi. Ro'yxat:\n{listing}\n\nYana qarindosh qo'shing yoki davom eting 👇"
    await message.answer(text, parse_mode="HTML", reply_markup=_relations_keyboard(len(relatives)))


@router.callback_query(ObyektivkaStates.relatives, F.data.startswith("ob_rel:"))
async def choose_relation(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if len((await state.get_data()).get("relatives", [])) >= MAX_RELATIVES:
        await callback.message.answer(f"⚠️ Ko'pi bilan {MAX_RELATIVES} ta qarindosh.")
        return
    relation = RELATIONS[int(callback.data.split(":", 1)[1])]
    await state.update_data(current_relation=relation)
    await state.set_state(ObyektivkaStates.relative_entry)
    await callback.message.answer(
        f"<b>{html.escape(relation)}</b> haqida 4 qatorda yozing:\n"
        "1) Familiya, ism, otasining ismi\n2) Tug'ilgan yili va joyi\n3) Ish joyi va lavozimi\n4) Turar joyi\n\n"
        "<i>Namuna:</i>\n<code>Karimov Rustam Aliyevich\n1962 y., Toshkent viloyati, Qibray tumani\n"
        "Pensiyada\nToshkent sh., Yunusobod tumani</code>\n\n"
        "<i>Vafot etgan bo'lsa, 3-qatorga «Vafot etgan (2015 y.)» deb yozing.</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="ob_rel_cancel")]]),
    )


@router.callback_query(ObyektivkaStates.relative_entry, F.data == "ob_rel_cancel")
async def cancel_relation(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await _ask_relatives(callback.message, state, first=True)


@router.message(ObyektivkaStates.relative_entry, F.text)
async def relative_entry(message: Message, state: FSMContext):
    if message.text.startswith("/"):
        return
    lines = [line.strip() for line in message.text.split("\n") if line.strip()]
    if len(lines) < 2 or len(message.text) > MAX_ANSWER:
        await message.answer("❌ Kamida 2 qator kerak: F.I.Sh. va tug'ilgan yili/joyi. Namunadagidek qayta yozing:")
        return
    lines += [""] * (4 - len(lines))
    data = await state.get_data()
    relatives = list(data.get("relatives", []))
    relatives.append({
        "rel": data.get("current_relation", ""), "name": lines[0], "birth": lines[1],
        "work": lines[2], "address": " ".join(lines[3:]).strip(),
    })
    await state.update_data(relatives=relatives)
    await _ask_relatives(message, state)


@router.callback_query(ObyektivkaStates.relatives, F.data == "ob_rel_done")
async def relatives_done(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(ObyektivkaStates.photo)
    await callback.message.answer(
        "📷 <b>Fotosurat</b>\n\nIstalgan suratingizni yuboring (selfi ham bo'ladi) — yuzingizni topib, "
        "<b>3×4 sm</b> standart formatga o'zim keltiraman.\n"
        "<i>Eng yaxshi natija: yuz to'g'ri qaragan, yorug' joyda, oddiy fonda olingan surat.</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="⏩ Rasmsiz davom etish", callback_data="ob_photo_skip")]]),
    )


# ── Fotosurat (3×4, yuz bo'yicha) ──────────────────────────────────────────
@router.message(ObyektivkaStates.photo, F.photo | F.document)
async def receive_photo(message: Message, state: FSMContext, bot: Bot):
    if message.photo:
        file, ext = message.photo[-1], ".jpg"
    else:
        file = message.document
        name = (file.file_name or "").lower()
        if not name.endswith(IMAGE_EXTENSIONS):
            await message.answer("❌ Rasm yuboring (JPG, PNG, HEIC...).")
            return
        ext = os.path.splitext(name)[1]
    if file.file_size and file.file_size > MAX_FILE_SIZE:
        await message.answer("❌ Rasm juda katta (20 MB gacha).")
        return

    job_dir = new_job_dir("obphoto")
    status = await message.answer("⏳ Rasm 3×4 formatga keltirilmoqda...")
    try:
        src, dst = os.path.join(job_dir, "src" + ext), os.path.join(job_dir, "photo.jpg")
        await bot.download(file, destination=src)
        face_found = await run_heavy(make_photo, src, dst)
        with open(dst, "rb") as f:
            photo = f.read()
    except Exception:
        logging.exception("Obyektivka rasmi")
        await status.edit_text("❌ Rasmni ochib bo'lmadi. Boshqa rasm yuboring.")
        return
    finally:
        remove(job_dir)

    await state.update_data(photo_b64=base64.b64encode(photo).decode())
    await state.set_state(ObyektivkaStates.photo_confirm)
    await status.delete()
    note = ("✅ Yuz topildi — rasm 3×4 sm formatga keltirildi." if face_found else
            "⚠️ Rasmda yuz aniqlanmadi — markazdan qirqildi. Yuzingiz aniq ko'ringan boshqa surat yuborsangiz yaxshiroq bo'ladi.")
    await message.answer_photo(
        BufferedInputFile(photo, filename="3x4.jpg"),
        caption=note,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Ma'qul, davom etish", callback_data="ob_photo_ok")],
            [InlineKeyboardButton(text="🔄 Boshqa rasm yuborish", callback_data="ob_photo_again")],
        ]),
    )


@router.callback_query(ObyektivkaStates.photo_confirm, F.data == "ob_photo_again")
async def photo_again(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(photo_b64=None)
    await state.set_state(ObyektivkaStates.photo)
    await callback.message.answer("📷 Boshqa suratni yuboring:")


@router.callback_query(F.data.in_({"ob_photo_ok", "ob_photo_skip"}))
async def ask_format(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if await state.get_state() not in (ObyektivkaStates.photo.state, ObyektivkaStates.photo_confirm.state):
        return
    if callback.data == "ob_photo_skip":
        await state.update_data(photo_b64=None)
    await state.set_state(ObyektivkaStates.choose_fmt)
    await callback.message.answer(
        "✅ Barcha ma'lumotlar yig'ildi! Obyektivkani qaysi formatda olasiz?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📄 PDF", callback_data="report_fmt_pdf"),
             InlineKeyboardButton(text="📊 Excel", callback_data="report_fmt_excel")],
            [InlineKeyboardButton(text="📦 Ikkalasi ham", callback_data="report_fmt_both")],
        ]),
    )


# ── Yaratish ───────────────────────────────────────────────────────────────
@router.callback_query(ObyektivkaStates.choose_fmt, F.data.startswith("report_fmt_"))
async def build_report(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    fmt = callback.data.removeprefix("report_fmt_")
    data = await state.get_data()
    await state.clear()
    values = dict(data.get("values", {}))
    values["relatives"] = data.get("relatives", [])
    photo = base64.b64decode(data["photo_b64"]) if data.get("photo_b64") else None
    name = safe_filename(values.get("full_name", "obyektivka").replace(" ", "_"), "obyektivka", 40)

    status = await callback.message.edit_text("⏳ Obyektivka tayyorlanmoqda...")
    try:
        if fmt in ("pdf", "both"):
            pdf_bytes = await run_heavy(generate_pdf, values, photo)
            await callback.message.answer_document(BufferedInputFile(pdf_bytes, filename=f"{name}_obyektivka.pdf"),
                                                   caption="📄 Obyektivka (PDF) tayyor!")
        if fmt in ("excel", "both"):
            xlsx = await run_heavy(generate_excel, values)
            await callback.message.answer_document(BufferedInputFile(xlsx, filename=f"{name}_obyektivka.xlsx"),
                                                   caption="📊 Obyektivka (Excel) tayyor!")
        await status.delete()
    except Exception:
        logging.exception("Obyektivka yaratishda xato")
        await status.edit_text("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")
