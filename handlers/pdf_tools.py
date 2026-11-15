import asyncio
import html
import logging
import os

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from services.converter_service import (
    ConversionError, run_heavy, pdf_page_count, human_size, MAX_FILE_SIZE,
)
from services.pdf_service import PdfService, parse_page_ranges
from services.tempfiles import new_job_dir, remove, safe_filename

router = Router()

MAX_MERGE_FILES = 20
MAX_WATERMARK_LENGTH = 40

# Albom qilib yuborilgan fayllar parallel keladi — har foydalanuvchi uchun qulf
_user_locks: dict[int, asyncio.Lock] = {}


def _lock(user_id: int) -> asyncio.Lock:
    return _user_locks.setdefault(user_id, asyncio.Lock())


class PdfStates(StatesGroup):
    merge_waiting_files = State()
    extract_waiting_file = State()
    extract_waiting_pages = State()
    watermark_waiting_file = State()
    watermark_waiting_text = State()


def get_pdf_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📎 Birlashtirish", callback_data="pdf_merge")],
        [InlineKeyboardButton(text="✂️ Sahifalarni ajratish", callback_data="pdf_extract")],
        [InlineKeyboardButton(text="©️ Watermark qo'yish", callback_data="pdf_watermark")],
    ])


@router.message(F.text == "📄 PDF bilan ishlash")
async def show_pdf_hub(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "📄 <b>PDF bilan ishlash</b>\n\nQaysi amaldan foydalanasiz?",
        parse_mode="HTML",
        reply_markup=get_pdf_menu(),
    )


async def _receive_pdf(message: Message, bot: Bot, job_dir: str, name: str) -> str | None:
    """PDF faylni tekshirib yuklab oladi. Muammo bo'lsa foydalanuvchiga aytadi va None qaytaradi."""
    doc = message.document
    if not (doc.file_name or "").lower().endswith(".pdf"):
        await message.answer("❌ Faqat <b>.pdf</b> fayl yuboring.", parse_mode="HTML")
        return None
    if doc.file_size and doc.file_size > MAX_FILE_SIZE:
        await message.answer(f"❌ Fayl juda katta ({human_size(doc.file_size)}). Limit — 20 MB.")
        return None
    path = os.path.join(job_dir, name)
    await bot.download(doc, destination=path)
    return path


async def _drop_job(state: FSMContext) -> None:
    """Oldingi tugallanmagan ishning vaqtinchalik papkasini o'chiradi."""
    remove((await state.get_data()).get("job_dir"))


# ── 1. BIRLASHTIRISH ──────────────────────────────────────────────────────

def _merge_keyboard(count: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ Birlashtirish ({count} ta fayl)", callback_data="pdf_merge_done")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="pdf_merge_cancel")],
    ])


@router.callback_query(F.data == "pdf_merge")
async def pdf_merge_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await _drop_job(state)
    await state.set_state(PdfStates.merge_waiting_files)
    await state.update_data(pdf_files=[], job_dir=new_job_dir("pdfmerge"))
    await callback.message.edit_text(
        "📎 <b>PDF Birlashtirish</b>\n\n"
        f"Birlashtirmoqchi bo'lgan PDF fayllarni ketma-ket yuboring (ko'pi bilan {MAX_MERGE_FILES} ta).\n"
        "Fayllar yuborgan tartibingizda birlashtiriladi.\n\n"
        "Barchasi yuborilgach, <b>✅ Birlashtirish</b> tugmasini bosing yoki <b>/done_pdf</b> yozing.",
        parse_mode="HTML",
    )


@router.message(PdfStates.merge_waiting_files, F.document)
async def pdf_merge_collect(message: Message, state: FSMContext, bot: Bot):
    async with _lock(message.from_user.id):
        if await state.get_state() != PdfStates.merge_waiting_files.state:
            return
        data = await state.get_data()
        files = list(data.get("pdf_files", []))
        if len(files) >= MAX_MERGE_FILES:
            await message.answer(f"⚠️ Ko'pi bilan {MAX_MERGE_FILES} ta fayl. «✅ Birlashtirish» ni bosing.")
            return
        path = await _receive_pdf(message, bot, data["job_dir"], f"{len(files) + 1:03d}.pdf")
        if not path:
            return
        files.append(path)
        await state.update_data(pdf_files=files)
        await message.answer(
            f"✅ Qabul qilindi. Jami fayllar: <b>{len(files)}</b> ta.",
            parse_mode="HTML",
            reply_markup=_merge_keyboard(len(files)),
        )


@router.callback_query(F.data == "pdf_merge_cancel")
async def pdf_merge_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Bekor qilindi")
    async with _lock(callback.from_user.id):
        await _drop_job(state)
        await state.clear()
    await callback.message.edit_text("❌ Bekor qilindi.")


@router.message(PdfStates.merge_waiting_files, F.text == "/done_pdf")
@router.callback_query(F.data == "pdf_merge_done")
async def pdf_merge_execute(event: Message | CallbackQuery, state: FSMContext):
    message = event.message if isinstance(event, CallbackQuery) else event
    if isinstance(event, CallbackQuery):
        await event.answer()

    async with _lock(event.from_user.id):
        if await state.get_state() != PdfStates.merge_waiting_files.state:
            await message.answer("Bu sessiya tugagan. Qaytadan «📎 Birlashtirish» ni tanlang.")
            return
        data = await state.get_data()
        files, job_dir = data.get("pdf_files", []), data.get("job_dir")
        if len(files) < 2:
            await message.answer("❌ Birlashtirish uchun kamida 2 ta PDF kerak.")
            return
        await state.clear()

    out_path = os.path.join(job_dir, "birlashtirilgan.pdf")
    msg = await message.answer(f"⏳ {len(files)} ta fayl birlashtirilmoqda...")
    try:
        if await run_heavy(PdfService.merge_pdfs, files, out_path):
            await message.answer_document(
                FSInputFile(out_path, filename="birlashtirilgan.pdf"),
                caption=f"✅ {len(files)} ta PDF birlashtirildi!",
            )
            await msg.delete()
        else:
            await msg.edit_text("❌ Xatolik yuz berdi. Ba'zi fayllar buzilgan yoki parol bilan himoyalangan bo'lishi mumkin.")
    except Exception:
        logging.exception("PDF merge error")
        await msg.edit_text("❌ Xatolik yuz berdi. Ba'zi fayllar buzilgan bo'lishi mumkin.")
    finally:
        remove(job_dir)


# ── 2. SAHIFALARNI AJRATISH ───────────────────────────────────────────────

@router.callback_query(F.data == "pdf_extract")
async def pdf_extract_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await _drop_job(state)
    await state.set_state(PdfStates.extract_waiting_file)
    await callback.message.edit_text("✂️ <b>Sahifalarni ajratish</b>\n\nPDF faylni yuboring.", parse_mode="HTML")


@router.message(PdfStates.extract_waiting_file, F.document)
async def pdf_extract_file(message: Message, state: FSMContext, bot: Bot):
    job_dir = new_job_dir("pdfext")
    path = await _receive_pdf(message, bot, job_dir, "input.pdf")
    if not path:
        remove(job_dir)
        return
    try:
        total = await asyncio.to_thread(pdf_page_count, path)
    except ConversionError as e:
        remove(job_dir)
        await message.answer(str(e))
        await state.clear()
        return
    await state.update_data(job_dir=job_dir, ext_path=path, total=total, original_name=message.document.file_name)
    await state.set_state(PdfStates.extract_waiting_pages)
    await message.answer(
        f"Faylda <b>{total}</b> ta sahifa bor.\n\n"
        "Qaysi sahifalarni ajratib olamiz? (Masalan: <code>1,3,5</code> yoki <code>2-6</code> yoki <code>1-3, 8</code>)",
        parse_mode="HTML",
    )


@router.message(PdfStates.extract_waiting_pages, F.text)
async def pdf_extract_execute(message: Message, state: FSMContext):
    data = await state.get_data()
    in_path, total, job_dir = data.get("ext_path"), data.get("total"), data.get("job_dir")
    try:
        pages = parse_page_ranges(message.text, total)
    except ValueError:
        await message.answer("❌ Noto'g'ri format. Masalan: <code>1,3,5</code> yoki <code>1-5</code> deb yozing.", parse_mode="HTML")
        return
    if not pages:
        await message.answer(f"❌ Bunday sahifa yo'q. Faylda 1 dan {total} gacha sahifa bor. Qaytadan kiriting:")
        return

    out_path = os.path.join(job_dir, "ajratilgan.pdf")
    msg = await message.answer("⏳ Ajratilmoqda...")
    try:
        count = await run_heavy(PdfService.extract_pages, in_path, out_path, pages)
        stem = safe_filename(os.path.splitext(data.get("original_name") or "")[0], "hujjat")
        await message.answer_document(
            FSInputFile(out_path, filename=f"{stem}_ajratilgan.pdf"),
            caption=f"✅ Ajratib olindi: {count} sahifa.",
        )
        await msg.delete()
    except Exception:
        logging.exception("PDF extract error")
        await msg.edit_text("❌ Xatolik yuz berdi.")
    finally:
        remove(job_dir)
        await state.clear()


# ── 3. WATERMARK QO'YISH ──────────────────────────────────────────────────

@router.callback_query(F.data == "pdf_watermark")
async def pdf_watermark_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await _drop_job(state)
    await state.set_state(PdfStates.watermark_waiting_file)
    await callback.message.edit_text("©️ <b>Watermark qo'yish</b>\n\nPDF faylni yuboring.", parse_mode="HTML")


@router.message(PdfStates.watermark_waiting_file, F.document)
async def pdf_watermark_file(message: Message, state: FSMContext, bot: Bot):
    job_dir = new_job_dir("pdfwm")
    path = await _receive_pdf(message, bot, job_dir, "input.pdf")
    if not path:
        remove(job_dir)
        return
    try:
        await asyncio.to_thread(pdf_page_count, path)
    except ConversionError as e:
        remove(job_dir)
        await message.answer(str(e))
        await state.clear()
        return
    await state.update_data(job_dir=job_dir, wm_path=path, original_name=message.document.file_name)
    await state.set_state(PdfStates.watermark_waiting_text)
    await message.answer(f"Endi watermark matnini kiriting (masalan: MAXFIY yoki НАМУНА), {MAX_WATERMARK_LENGTH} belgigacha:")


@router.message(PdfStates.watermark_waiting_text, F.text)
async def pdf_watermark_execute(message: Message, state: FSMContext):
    wm_text = " ".join(message.text.split())
    if not wm_text or len(wm_text) > MAX_WATERMARK_LENGTH:
        await message.answer(f"❌ Matn 1 dan {MAX_WATERMARK_LENGTH} belgigacha bo'lsin. Qaytadan kiriting:")
        return
    data = await state.get_data()
    in_path, job_dir = data.get("wm_path"), data.get("job_dir")
    out_path = os.path.join(job_dir, "watermark.pdf")
    msg = await message.answer("⏳ Watermark qo'yilmoqda...")
    try:
        if await run_heavy(PdfService.add_watermark, in_path, out_path, wm_text, job_dir):
            stem = safe_filename(os.path.splitext(data.get("original_name") or "")[0], "hujjat")
            await message.answer_document(
                FSInputFile(out_path, filename=f"{stem}_wm.pdf"),
                caption=f"✅ «{html.escape(wm_text)}» watermark qo'yildi!",
                parse_mode="HTML",
            )
            await msg.delete()
        else:
            await msg.edit_text("❌ Xatolik yuz berdi. Fayl buzilgan bo'lishi mumkin.")
    except Exception:
        logging.exception("Watermark xato")
        await msg.edit_text("❌ Xatolik yuz berdi.")
    finally:
        remove(job_dir)
        await state.clear()
