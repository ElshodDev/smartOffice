"""🔍 Excel ichidan ma'lumot qidirish: fayl bir marta yuklanadi, so'ng istalgancha so'z qidiriladi."""
import html
import logging
import os
import re

from aiogram import Router, F, Bot
from aiogram.types import Message, FSInputFile, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from services.converter_service import run_heavy
from services.excel_common import is_excel, size_error, read_table
from services.mass_fill import format_cell
from services.tempfiles import new_job_dir, remove, safe_filename

router = Router()

SHOW_AS_TEXT = 15        # shundan ko'p natija bo'lsa — Excel fayl
TELEGRAM_LIMIT = 3900


class SearchDataStates(StatesGroup):
    waiting_for_file = State()
    waiting_for_query = State()


FINISH_KB = InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text="✅ Qidiruvni tugatish", callback_data="search_finish")
]])


@router.message(F.text == "🔍 Ma'lumot qidirish")
async def start_search(message: Message, state: FSMContext):
    remove((await state.get_data()).get("job_dir"))
    await state.clear()
    await message.answer("🔍 Qidirish uchun Excel (.xlsx yoki .xls) faylni yuboring.")
    await state.set_state(SearchDataStates.waiting_for_file)


@router.callback_query(F.data == "tools_search")
async def start_search_cb(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    remove((await state.get_data()).get("job_dir"))
    await state.clear()
    await callback.message.edit_text(
        "🔍 <b>Ma'lumot qidirish</b>\n\nQidirish uchun Excel (.xlsx yoki .xls) faylni yuboring. "
        "Keyin so'z yoki raqam yozasiz — mos qatorlarni topib beraman.",
        parse_mode="HTML",
    )
    await state.set_state(SearchDataStates.waiting_for_file)


@router.message(SearchDataStates.waiting_for_file, F.document)
async def process_search_file(message: Message, state: FSMContext, bot: Bot):
    doc = message.document
    if not is_excel(doc.file_name):
        await message.answer("Iltimos, faqat .xlsx yoki .xls formatidagi fayl yuboring.")
        return
    if error := size_error(doc.file_size):
        await message.answer(error)
        return
    remove((await state.get_data()).get("job_dir"))
    job_dir = new_job_dir("xlsearch")
    path = os.path.join(job_dir, "input" + os.path.splitext(doc.file_name)[1].lower())
    await bot.download(doc, destination=path)
    try:
        df = await run_heavy(read_table, path)
    except Exception:
        logging.exception("Qidiruv: faylni o'qib bo'lmadi")
        remove(job_dir)
        await message.answer("❌ Faylni o'qib bo'lmadi. Fayl buzilgan yoki format noto'g'ri bo'lishi mumkin.")
        return
    if df.empty:
        remove(job_dir)
        await message.answer("❌ Fayl bo'sh — qidiradigan ma'lumot yo'q.")
        return
    await state.update_data(job_dir=job_dir, file_path=path, original_name=doc.file_name)
    await state.set_state(SearchDataStates.waiting_for_query)
    await message.answer(
        f"✅ Fayl qabul qilindi: <b>{len(df)}</b> qator, <b>{len(df.columns)}</b> ustun.\n\n"
        "Qidirmoqchi bo'lgan so'z yoki raqamni yozing (masalan: <code>Aliyev</code> yoki <code>+998901234567</code>).\n"
        "<i>Bir nechta so'zni ketma-ket qidirishingiz mumkin.</i>",
        parse_mode="HTML",
        reply_markup=FINISH_KB,
    )


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text)


def _search(path: str, query: str, out_path: str):
    df = read_table(path)
    # Katakchalarni odam ko'radigan ko'rinishga keltiramiz: 95.0 → "95", sana → "15.11.2026", bo'sh → ""
    as_text = df.apply(lambda col: col.map(format_cell)).astype(str)
    # regex=False: "+998..." yoki "(bo'lim)" kabi so'rovlar oddiy matn sifatida qidiriladi
    mask = as_text.apply(lambda col: col.str.contains(query, case=False, regex=False, na=False)).any(axis=1)
    # Telefon/raqam qidiruvi: Excel "+998 90 123-45-67" ni ko'pincha 998901234567 son sifatida saqlaydi
    digits = _digits(query)
    if len(digits) >= 5 and len(digits) >= len(re.sub(r"[\s+()\-]", "", query)):
        mask |= as_text.apply(lambda col: col.map(_digits).str.contains(digits, regex=False)).any(axis=1)
    found = df[mask]
    if len(found) > SHOW_AS_TEXT:
        found.to_excel(out_path, index=False)
        return len(found), None
    rows = []
    for _, row in as_text[mask].iterrows():
        rows.append([(str(col), val) for col, val in row.items() if val.strip()])
    return len(found), rows


@router.message(SearchDataStates.waiting_for_query, F.text)
async def process_search_query(message: Message, state: FSMContext):
    query = message.text.strip()
    if query.startswith("/"):
        return
    if not query:
        return
    data = await state.get_data()
    stem = safe_filename(os.path.splitext(data.get("original_name") or "")[0], "jadval")
    out_path = os.path.join(data["job_dir"], f"{stem}_qidiruv.xlsx")
    q = html.escape(query)
    try:
        count, rows = await run_heavy(_search, data["file_path"], query, out_path)
    except Exception:
        logging.exception("Qidirishda xatolik")
        await message.answer("❌ Qidirishda xatolik yuz berdi.", reply_markup=FINISH_KB)
        return

    if count == 0:
        await message.answer(f"❌ «{q}» bo'yicha hech narsa topilmadi. Boshqa so'z yozing:",
                             parse_mode="HTML", reply_markup=FINISH_KB)
        return
    if rows is None:
        await message.answer_document(
            FSInputFile(out_path),
            caption=f"🔍 «{q}» bo'yicha <b>{count}</b> ta natija — Excel faylda.\nYana so'z yozishingiz mumkin.",
            parse_mode="HTML",
            reply_markup=FINISH_KB,
        )
        os.remove(out_path)
        return

    lines = [f"✅ «{q}» bo'yicha <b>{count}</b> ta natija:\n"]
    for row in rows:
        lines.append("▫️ " + " | ".join(f"<b>{html.escape(c)}:</b> {html.escape(v)}" for c, v in row))
    text = "\n".join(lines)
    if len(text) > TELEGRAM_LIMIT:
        text = text[:TELEGRAM_LIMIT].rsplit("\n", 1)[0] + "\n…"
    await message.answer(text + "\n\n<i>Yana so'z yozishingiz mumkin.</i>", parse_mode="HTML", reply_markup=FINISH_KB)


@router.callback_query(F.data == "search_finish")
async def finish_search(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Qidiruv tugatildi")
    remove((await state.get_data()).get("job_dir"))
    await state.clear()
    await callback.message.answer("✅ Qidiruv tugatildi. Bosh menyudan boshqa bo'limni tanlashingiz mumkin.")
