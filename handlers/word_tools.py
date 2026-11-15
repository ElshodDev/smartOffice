"""
📝 Word vositalari: shablon to'ldirish, Word faylni o'qish va imzo (ism-familiya) qo'yish.
"""
import html
import logging
import os
import re

from aiogram import Router, F, Bot
from aiogram.types import Message, FSInputFile, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from docx import Document

from services.converter_service import run_heavy, MAX_FILE_SIZE, human_size
from services.docx_template import (
    fill_template, template_placeholders, iter_all_paragraphs, normalize_key,
)
from services.excel_common import is_excel, size_error, read_table, column_keyboard, esc
from services.mass_fill import MAX_ROWS, make_sample_excel, match_columns, generate_documents
from services.tempfiles import new_job_dir, remove, safe_filename
from services.alphabet import esc as uesc, raw

router = Router()

MAX_PLACEHOLDERS_SHOWN = 40
TELEGRAM_LIMIT = 4000


class WordToolsStates(StatesGroup):
    mass_waiting_template = State()
    mass_waiting_excel = State()
    mass_choose_name = State()
    waiting_for_template_file = State()
    waiting_for_template_data = State()
    waiting_for_read_file = State()
    waiting_for_signature = State()


def get_word_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Shablonni to'ldirish (bitta hujjat)", callback_data="word_fill_template")],
        [InlineKeyboardButton(text="📋 Excel ro'yxatdan ommaviy to'ldirish", callback_data="word_mass")],
        [InlineKeyboardButton(text="📖 Word hujjatni o'qish", callback_data="word_read")],
    ])


@router.message(F.text == "📝 Word Hujjat")
async def start_word_tools(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("📝 <b>Word Hujjat vositalari</b>\n\nQuyidagi amallardan birini tanlang:",
                         parse_mode="HTML", reply_markup=get_word_menu())


async def _download_docx(message: Message, bot: Bot, prefix: str):
    doc = message.document
    if not (doc.file_name or "").lower().endswith(".docx"):
        await message.answer(
            "Iltimos, faqat <b>.docx</b> formatidagi fayl yuboring.\n"
            "<i>Eski .doc fayl bo'lsa, Word'da «Saqlash» → .docx qilib saqlang.</i>",
            parse_mode="HTML",
        )
        return None, None
    if doc.file_size and doc.file_size > MAX_FILE_SIZE:
        await message.answer(f"❌ Fayl juda katta ({human_size(doc.file_size)}). Limit — 20 MB.")
        return None, None
    job_dir = new_job_dir(prefix)
    path = os.path.join(job_dir, "input.docx")
    await bot.download(doc, destination=path)
    return job_dir, path


# ──────────────────────────────────────────────
# SHABLON TO'LDIRISH ({{o'zgaruvchi}} → qiymat)
# ──────────────────────────────────────────────
@router.callback_query(F.data == "word_fill_template")
async def ask_template_file(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    remove((await state.get_data()).get("job_dir"))
    await state.clear()
    await callback.message.answer(
        "📎 Iltimos, to'ldirmoqchi bo'lgan <b>.docx</b> shablon faylni yuboring.\n\n"
        "<i>Fayldagi <b>{{ism}}</b>, <b>{{o'qituvchi}}</b>, <b>{{Tug'ilgan sana}}</b> ko'rinishidagi joylar "
        "to'ldiriladi — matnda, jadvallarda va kolontitullarda.</i>",
        parse_mode="HTML",
    )
    await state.set_state(WordToolsStates.waiting_for_template_file)


@router.message(WordToolsStates.waiting_for_template_file, F.document)
async def receive_template(message: Message, state: FSMContext, bot: Bot):
    job_dir, path = await _download_docx(message, bot, "wordtpl")
    if not path:
        return
    try:
        placeholders = await run_heavy(template_placeholders, path)
    except Exception:
        logging.exception("Shablonni o'qib bo'lmadi")
        remove(job_dir)
        await message.answer("❌ Faylni o'qib bo'lmadi. Fayl shikastlangan bo'lishi mumkin.")
        await state.clear()
        return
    if not placeholders:
        remove(job_dir)
        await message.answer(
            "⚠️ Faylda <b>{{o'zgaruvchi}}</b> ko'rinishidagi joylar topilmadi.\n"
            "Shablonda to'ldiriladigan joylarni qo'sh jingalak qavsga oling, masalan: <code>{{ism}}</code>",
            parse_mode="HTML",
        )
        await state.clear()
        return

    await state.update_data(job_dir=job_dir, template_path=path, original_name=message.document.file_name,
                            placeholders=placeholders)
    shown = placeholders[:MAX_PLACEHOLDERS_SHOWN]
    listing = "\n".join(f"  • <code>{uesc(p)}</code>" for p in shown)
    if len(placeholders) > len(shown):
        listing += f"\n  … va yana {len(placeholders) - len(shown)} ta"
    example = "\n".join(f"{uesc(p)}: ..." for p in placeholders[:3])
    await message.answer(
        f"✅ Shablon qabul qilindi! <b>{len(placeholders)}</b> ta o'zgaruvchi topildi:\n{listing}\n\n"
        "Endi qiymatlarni <b>nom: qiymat</b> ko'rinishida, har birini yangi qatorda yuboring.\n\n"
        f"<b>Namuna:</b>\n<code>{example}</code>",
        parse_mode="HTML",
    )
    await state.set_state(WordToolsStates.waiting_for_template_data)


@router.message(WordToolsStates.waiting_for_template_data, F.text)
async def fill_template_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    placeholders = data["placeholders"]
    known = {normalize_key(p): p for p in placeholders}

    values, bad_lines, unknown = {}, [], []
    for line in message.text.splitlines():
        if not line.strip():
            continue
        key, sep, value = line.partition(":")
        if not sep:
            bad_lines.append(line)
            continue
        if normalize_key(key) in known:
            values[key] = value.strip()
        else:
            unknown.append(key.strip())
    if not values:
        await message.answer(
            "❌ Birorta ham o'zgaruvchi nomi mos kelmadi. Har bir qatorni <b>nom: qiymat</b> ko'rinishida yozing.",
            parse_mode="HTML",
        )
        return

    filled = {normalize_key(k) for k in values}
    missing = [p for p in placeholders if normalize_key(p) not in filled]
    job_dir = data["job_dir"]
    stem = safe_filename(os.path.splitext(data["original_name"])[0], "hujjat")
    out_path = os.path.join(job_dir, f"{stem}_tayyor.docx")
    msg = await message.answer("Shablon to'ldirilmoqda... ⏳")
    try:
        await run_heavy(fill_template, data["template_path"], out_path, values)
        notes = []
        if missing:
            notes.append("⚠️ To'ldirilmagan (o'zgarishsiz qoldi): " + ", ".join(html.escape(m) for m in missing))
        if unknown:
            notes.append("ℹ️ Shablonda yo'q nomlar (e'tiborsiz qoldirildi): " + ", ".join(html.escape(u) for u in unknown))
        if bad_lines:
            notes.append(f"ℹ️ «nom: qiymat» ko'rinishida bo'lmagan {len(bad_lines)} ta qator o'tkazib yuborildi.")
        await message.answer_document(
            FSInputFile(out_path),
            caption="✅ Shablon to'ldirildi!" + ("\n\n" + "\n".join(notes) if notes else ""),
            parse_mode="HTML",
        )
        await msg.delete()
    except Exception:
        logging.exception("Shablon to'ldirishda xato")
        await msg.edit_text("❌ Xatolik yuz berdi. Fayl formati noto'g'ri bo'lishi mumkin.")
    finally:
        remove(job_dir)
        await state.clear()


# ──────────────────────────────────────────────
# WORD FAYLNI O'QISH
# ──────────────────────────────────────────────
_SIGN_LINE = re.compile(r"imzo", re.IGNORECASE)


def _read_text(path: str) -> tuple[str, bool]:
    document = Document(path)
    lines = [p.text for p in iter_all_paragraphs(document) if p.text.strip()]
    has_sign_place = any(_SIGN_LINE.search(line) and ("__" in line or ":" in line) for line in lines)
    return "\n".join(lines), has_sign_place


@router.callback_query(F.data == "word_read")
async def ask_read_file(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.answer("📎 O'qimoqchi bo'lgan <b>.docx</b> faylni yuboring:", parse_mode="HTML")
    await state.set_state(WordToolsStates.waiting_for_read_file)


@router.message(WordToolsStates.waiting_for_read_file, F.document)
async def read_word_file(message: Message, state: FSMContext, bot: Bot):
    job_dir, path = await _download_docx(message, bot, "wordread")
    if not path:
        return
    msg = await message.answer("Fayl o'qilmoqda... ⏳")
    try:
        full_text, has_sign_place = await run_heavy(_read_text, path)
        if not full_text:
            await msg.edit_text("⚠️ Fayl bo'sh yoki matn topilmadi.")
            return
        # Matn foydalanuvchi faylidan — HTML sifatida emas, oddiy matn sifatida yuboriladi,
        # shunda "A & B" yoki "<...>" kabi belgilar xabarni buzmaydi.
        header = f"📄 {raw(message.document.file_name)}\n{'─' * 28}\n\n"
        chunks, rest = [], header + full_text
        while rest:
            chunks.append(raw(rest[:TELEGRAM_LIMIT]))
            rest = rest[TELEGRAM_LIMIT:]
        await msg.edit_text(chunks[0])
        for chunk in chunks[1:]:
            await message.answer(chunk)

        if has_sign_place:
            await state.update_data(sign_file_id=message.document.file_id, sign_name=message.document.file_name)
            await message.answer(
                "Ushbu hujjatda imzo joyi borligini aniqladim. Ism-familiyangizni imzo joyiga yozib beraymi?",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="✍️ Imzo joyiga ism yozish", callback_data="sign_word")
                ]]),
            )
    except Exception:
        logging.exception("Word faylni o'qishda xato")
        await msg.edit_text("❌ Xatolik yuz berdi. Fayl shikastlangan bo'lishi mumkin.")
    finally:
        remove(job_dir)
        if await state.get_state() == WordToolsStates.waiting_for_read_file.state:
            await state.set_state(None)


# ──────────────────────────────────────────────
# IMZO JOYIGA ISM-FAMILIYA YOZISH
# ──────────────────────────────────────────────
def _sign_document(src: str, dst: str, signature: str) -> int:
    """
    Faqat "imzo" so'zi bor qatorlarda ishlaydi: birinchi ____ chizig'i o'rniga ismni yozadi
    (chiziq bo'lmasa — qator oxiriga qo'shadi). Boshqa bo'sh joylar (sana va h.k.) o'zgarmaydi,
    qatorning formatlashi saqlanadi.
    """
    document = Document(src)
    signed = 0
    for paragraph in iter_all_paragraphs(document):
        if not _SIGN_LINE.search(paragraph.text):
            continue
        done = False
        for run in paragraph.runs:
            if "__" in run.text:
                run.text = re.sub(r"_{2,}", signature, run.text, count=1)
                done = True
                break
        if not done and paragraph.text.rstrip().endswith(":"):
            paragraph.add_run(" " + signature)
            done = True
        signed += done
    document.save(dst)
    return signed


@router.callback_query(F.data.in_({"sign_word"}) | F.data.startswith("sign_word:"))
async def ask_for_signature(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if ":" in callback.data:  # eski xabarlardagi tugmalar uchun
        await state.update_data(sign_file_id=callback.data.split(":", 1)[1], sign_name="hujjat.docx")
    if not (await state.get_data()).get("sign_file_id"):
        await callback.message.answer("❌ Fayl topilmadi. Hujjatni qaytadan yuboring.")
        return
    await callback.message.answer(
        "✍️ Hujjatga yoziladigan ism-familiyani yuboring:\n<i>(Masalan: Aliyev Vali)</i>",
        parse_mode="HTML",
    )
    await state.set_state(WordToolsStates.waiting_for_signature)


@router.message(WordToolsStates.waiting_for_signature, F.text)
async def process_word_signature(message: Message, state: FSMContext, bot: Bot):
    signature = " ".join(message.text.split())[:100]
    data = await state.get_data()
    file_id = data.get("sign_file_id")
    if not file_id:
        await message.answer("❌ Fayl topilmadi, iltimos boshqatdan urinib ko'ring.")
        await state.clear()
        return

    job_dir = new_job_dir("wordsign")
    in_path, out_path = os.path.join(job_dir, "input.docx"), os.path.join(job_dir, "imzolangan.docx")
    msg = await message.answer("Hujjat imzolanmoqda... ⏳")
    try:
        await bot.download(file_id, destination=in_path)
        signed = await run_heavy(_sign_document, in_path, out_path, signature)
        if signed:
            stem = safe_filename(os.path.splitext(data.get("sign_name") or "")[0], "hujjat")
            await message.answer_document(
                FSInputFile(out_path, filename=f"{stem}_imzolangan.docx"),
                caption=f"✅ Ism-familiya {signed} ta imzo joyiga yozildi.",
            )
            await msg.delete()
        else:
            await msg.edit_text("⚠️ Hujjatda «Imzo: ____» ko'rinishidagi joy topilmadi, hujjat o'zgartirilmadi.")
    except Exception:
        logging.exception("Imzo qo'yishda xato")
        await msg.edit_text("❌ Xatolik yuz berdi.")
    finally:
        remove(job_dir)
        await state.clear()


# ──────────────────────────────────────────────
# EXCEL RO'YXATDAN OMMAVIY TO'LDIRISH
# ──────────────────────────────────────────────
@router.callback_query(F.data == "word_mass")
async def mass_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    remove((await state.get_data()).get("job_dir"))
    await state.clear()
    await callback.message.answer(
        "📋 <b>Excel ro'yxatdan ommaviy to'ldirish</b>\n\n"
        "Bitta Word shablon va Excel ro'yxat asosida har bir qator uchun alohida hujjat yarataman "
        "(sertifikat, taklifnoma, buyruq, ma'lumotnoma...).\n\n"
        "<b>1-qadam:</b> <code>{{ism}}</code>, <code>{{lavozim}}</code> kabi joylari bor <b>.docx</b> shablonni yuboring.",
        parse_mode="HTML",
    )
    await state.set_state(WordToolsStates.mass_waiting_template)


@router.message(WordToolsStates.mass_waiting_template, F.document)
async def mass_template(message: Message, state: FSMContext, bot: Bot):
    job_dir, path = await _download_docx(message, bot, "wordmass")
    if not path:
        return
    try:
        placeholders = await run_heavy(template_placeholders, path)
    except Exception:
        logging.exception("Ommaviy: shablonni o'qib bo'lmadi")
        remove(job_dir)
        await message.answer("❌ Faylni o'qib bo'lmadi. Fayl shikastlangan bo'lishi mumkin.")
        return
    if not placeholders:
        remove(job_dir)
        await message.answer(
            "⚠️ Shablonda <b>{{o'zgaruvchi}}</b> ko'rinishidagi joylar topilmadi.\n"
            "To'ldiriladigan joylarni qo'sh jingalak qavsga oling, masalan: <code>{{ism}}</code>",
            parse_mode="HTML",
        )
        return

    sample = os.path.join(job_dir, "royxat_namunasi.xlsx")
    await run_heavy(make_sample_excel, placeholders, sample)
    await state.update_data(job_dir=job_dir, template_path=path, placeholders=placeholders,
                            original_name=message.document.file_name)
    await state.set_state(WordToolsStates.mass_waiting_excel)
    listing = ", ".join(f"<code>{uesc(p)}</code>" for p in placeholders[:MAX_PLACEHOLDERS_SHOWN])
    await message.answer_document(
        FSInputFile(sample),
        caption=(
            f"✅ Shablonda {len(placeholders)} ta o'zgaruvchi topildi: {listing}\n\n"
            "<b>2-qadam:</b> shu jadvalni to'ldirib yuboring — har bir qator bitta hujjat bo'ladi "
            f"(ko'pi bilan {MAX_ROWS} ta).\n"
            "<i>O'z Excel faylingizni ham yuborishingiz mumkin — ustun nomlari o'zgaruvchilar bilan bir xil bo'lsin.</i>"
        ),
        parse_mode="HTML",
    )


@router.message(WordToolsStates.mass_waiting_excel, F.document)
async def mass_excel(message: Message, state: FSMContext, bot: Bot):
    doc = message.document
    if not is_excel(doc.file_name):
        await message.answer("❌ Excel (<b>.xlsx</b> yoki <b>.xls</b>) ro'yxat yuboring.", parse_mode="HTML")
        return
    if error := size_error(doc.file_size):
        await message.answer(error)
        return
    data = await state.get_data()
    path = os.path.join(data["job_dir"], "royxat" + os.path.splitext(doc.file_name)[1].lower())
    await bot.download(doc, destination=path)
    try:
        df = await run_heavy(read_table, path)
    except Exception:
        logging.exception("Ommaviy: Excelni o'qib bo'lmadi")
        await message.answer("❌ Excel faylni o'qib bo'lmadi. Boshqa fayl yuboring:")
        return
    df = df.dropna(how="all")
    if df.empty:
        await message.answer("❌ Jadvalda ma'lumot qatorlari yo'q. To'ldirib qaytadan yuboring:")
        return
    if len(df) > MAX_ROWS:
        await message.answer(f"❌ Jadvalda {len(df)} ta qator bor — ko'pi bilan {MAX_ROWS} ta. Bo'lib yuboring:")
        return

    matched, missing = match_columns(data["placeholders"], df.columns)
    if not matched:
        await message.answer(
            "❌ Jadval ustunlari shablondagi o'zgaruvchilarga mos kelmadi.\n"
            "Ustun nomlari shablondagi nomlar bilan bir xil bo'lishi kerak: "
            + ", ".join(f"<code>{uesc(p)}</code>" for p in data["placeholders"]),
            parse_mode="HTML",
        )
        return

    await state.update_data(excel_path=path)
    await state.set_state(WordToolsStates.mass_choose_name)
    text = f"✅ Jadval qabul qilindi: <b>{len(df)}</b> ta qator.\n🔗 Mos kelgan ustunlar: " + ", ".join(esc(m) for m in matched)
    if missing:
        text += "\n⚠️ Jadvalda yo'q (shablonda o'zgarishsiz qoladi): " + ", ".join(esc(m) for m in missing)
    text += "\n\n<b>3-qadam:</b> fayl nomlari qaysi ustundan olinsin?"
    seq_button = InlineKeyboardButton(text="🔢 Tartib raqami (1, 2, 3...)", callback_data="mass_name:seq")
    await message.answer(text, parse_mode="HTML", reply_markup=column_keyboard(df.columns, "mass_name", extra_first=[seq_button]))


@router.callback_query(WordToolsStates.mass_choose_name, F.data.startswith("mass_name:"))
async def mass_generate(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    await state.clear()
    choice = callback.data.split(":", 1)[1]
    name_index = None if choice == "seq" else int(choice)
    job_dir = data["job_dir"]
    stem = safe_filename(os.path.splitext(data.get("original_name") or "")[0], "hujjat")
    status = await callback.message.edit_text("⏳ Hujjatlar yaratilmoqda...")
    try:
        zip_path, count = await run_heavy(
            generate_documents, data["template_path"], data["excel_path"], job_dir, stem, name_index
        )
        await callback.message.answer_document(
            FSInputFile(zip_path),
            caption=f"✅ Tayyor! {count} ta hujjat yaratildi va ZIP arxivga joylandi.",
        )
        await status.delete()
    except Exception:
        logging.exception("Ommaviy to'ldirishda xato")
        await status.edit_text("❌ Hujjatlarni yaratishda xatolik yuz berdi.")
    finally:
        remove(job_dir)
