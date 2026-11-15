"""
📁 Format o'zgartirish bo'limi:
PDF → Word, Rasm(lar) → PDF, PDF → Rasm, PDF siqish, Rasm formati → JPG.
"""
import asyncio
import logging
import os
import shutil

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, FSInputFile,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from services.doc_scanner import scan_image
from services.converter_service import (
    ConverterService, ConversionError, run_heavy, is_busy, human_size,
    MAX_FILE_SIZE, MAX_IMAGES_PER_PDF, MAX_PDF2WORD_PAGES, MAX_PDF2IMG_PAGES,
    IMAGE_EXTENSIONS, HEIC_SUPPORTED, pdf_has_text,
)

router = Router()
TEMP_DIR = "temp"

# Albom (bir nechta rasm birdan) yuborilganda xabarlar parallel keladi —
# har bir foydalanuvchi uchun qulf, rasmlar yo'qolmasligi uchun.
_user_locks: dict[int, asyncio.Lock] = {}


def _lock(user_id: int) -> asyncio.Lock:
    return _user_locks.setdefault(user_id, asyncio.Lock())


class FormatConverterStates(StatesGroup):
    waiting_for_pdf = State()          # PDF → Word
    collecting_images = State()        # Rasm(lar) → PDF
    waiting_for_pdf2img = State()      # PDF → Rasm
    waiting_for_compress = State()     # PDF siqish
    waiting_for_img2jpg = State()      # Rasm formati → JPG


def get_converter_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 PDF ➡️ Word", callback_data="format_pdf2word")],
        [InlineKeyboardButton(text="🖼 Rasm(lar) ➡️ PDF", callback_data="format_img2pdf")],
        [InlineKeyboardButton(text="📸 Hujjatni skanerlash (suratdan toza PDF)", callback_data="format_scan")],
        [InlineKeyboardButton(text="📄 PDF ➡️ Rasm (JPG)", callback_data="format_pdf2img")],
        [InlineKeyboardButton(text="🗜 PDF hajmini kichraytirish", callback_data="format_compress")],
        [InlineKeyboardButton(text="📱 Rasm formati ➡️ JPG (HEIC, WEBP, PNG)", callback_data="format_img2jpg")],
    ])


@router.message(F.text == "🔄 Konvertor")
async def start_converter_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "📁 <b>Fayl formatini o'zgartirish</b>\n\nQaysi formatni xohlaysiz?",
        parse_mode="HTML",
        reply_markup=get_converter_menu(),
    )


# ── Umumiy yordamchilar ────────────────────────────────────────────────────

def _tmp(name: str) -> str:
    os.makedirs(TEMP_DIR, exist_ok=True)
    return os.path.join(TEMP_DIR, name)


def _remove(*paths: str) -> None:
    for path in paths:
        try:
            if path and os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            elif path and os.path.exists(path):
                os.remove(path)
        except OSError:
            pass


async def _check_size(message: Message, file_size: int | None) -> bool:
    if file_size and file_size > MAX_FILE_SIZE:
        await message.answer(
            f"❌ Fayl juda katta ({human_size(file_size)}).\n"
            "Telegram botlari 20 MB gacha bo'lgan fayllarni qabul qila oladi."
        )
        return False
    return True


async def _run(message: Message, status: Message, func, *args):
    """Og'ir ishni navbat orqali bajaradi; band bo'lsa foydalanuvchini ogohlantiradi."""
    if is_busy():
        await status.edit_text("⏳ Server hozir boshqa faylni qayta ishlayapti. Siz navbatdasiz, biroz kuting...")
    return await run_heavy(func, *args)


def _stem(file_name: str | None, default: str) -> str:
    stem = os.path.splitext(os.path.basename(file_name or ""))[0]
    return stem or default


# ── 📄 PDF → Word ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "format_pdf2word")
async def ask_for_pdf(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "📄 <b>PDF dan Word ga o'tkazish</b>\n\n"
        f"Iltimos, .pdf formatidagi faylni yuboring (ko'pi bilan {MAX_PDF2WORD_PAGES} sahifa, 20 MB).",
        parse_mode="HTML",
    )
    await state.set_state(FormatConverterStates.waiting_for_pdf)


@router.message(FormatConverterStates.waiting_for_pdf, F.document)
async def process_pdf_to_word(message: Message, state: FSMContext, bot: Bot):
    doc = message.document
    if not (doc.file_name or "").lower().endswith(".pdf"):
        await message.answer("Iltimos, faqat .pdf formatidagi fayl yuboring.")
        return
    if not await _check_size(message, doc.file_size):
        return

    pdf_path = _tmp(f"p2w_{doc.file_unique_id}.pdf")
    docx_path = _tmp(f"p2w_{doc.file_unique_id}.docx")
    status = await message.answer("Fayl qabul qilindi. Konvertatsiya qilinmoqda, biroz vaqt olishi mumkin... ⏳")
    try:
        await bot.download(doc, destination=pdf_path)
        if not await asyncio.to_thread(pdf_has_text, pdf_path):
            await status.edit_text(
                "❌ PDF ichida matn topilmadi — fayl skaner qilingan (rasm ko'rinishidagi) ko'rinadi.\n\n"
                "Bunday faylni Word'ga o'girish uchun avval undagi matnni OCR orqali o'qish kerak."
            )
            return
        if await _run(message, status, ConverterService.pdf_to_word, pdf_path, docx_path):
            await message.answer_document(
                FSInputFile(docx_path, filename=f"{_stem(doc.file_name, 'hujjat')}.docx"),
                caption="✅ Tayyor! PDF muvaffaqiyatli Word formatiga o'tkazildi.",
            )
            await status.delete()
        else:
            await status.edit_text("❌ Konvertatsiya vaqtida xatolik yuz berdi. Fayl buzilgan bo'lishi mumkin.")
    except ConversionError as e:
        await status.edit_text(str(e))
    except Exception:
        logging.exception("PDF → Word xatolik")
        await status.edit_text("❌ Konvertatsiya vaqtida xatolik yuz berdi.")
    finally:
        _remove(pdf_path, docx_path)
        await state.clear()


# ── 🖼 Rasm(lar) → PDF ─────────────────────────────────────────────────────

def _img2pdf_keyboard(count: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ PDF yaratish ({count} ta rasm)", callback_data="format_img2pdf_done")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="format_img2pdf_cancel")],
    ])


def _user_img_dir(user_id: int) -> str:
    return _tmp(f"img2pdf_{user_id}")


@router.callback_query(F.data == "format_img2pdf")
async def ask_for_image(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    _remove(_user_img_dir(callback.from_user.id))  # avvalgi tugallanmagan sessiya qoldiqlari
    await state.set_state(FormatConverterStates.collecting_images)
    await state.update_data(images=[], status_id=None, purpose="pdf")
    await callback.message.edit_text(
        "🖼 <b>Rasm(lar)dan PDF yaratish</b>\n\n"
        f"Rasmlarni yuboring — bittadan yoki albom qilib (ko'pi bilan {MAX_IMAGES_PER_PDF} ta).\n"
        "Har bir rasm PDF'da alohida sahifa bo'ladi, yuborgan tartibingizda.\n\n"
        "<i>Sifat yo'qolmasligi uchun rasmlarni «Fayl» sifatida yuborish tavsiya etiladi.</i>",
        parse_mode="HTML",
    )


# ── 📸 Hujjat skaneri (rasm yig'ish mexanizmi Rasm → PDF bilan umumiy) ──────

SCAN_MODES = {"bw": "⚫ Oq-qora", "color": "🎨 Rangli"}


@router.callback_query(F.data == "format_scan")
async def ask_scan_mode(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "📸 <b>Hujjatni skanerlash</b>\n\n"
        "Telefonda olingan hujjat suratini skaner qilingandek toza PDF qilib beraman: "
        "qog'oz chetlarini topib qirqaman, qiyshayganini to'g'rilayman, soyani olib tashlayman.\n\n"
        "Qaysi rejim kerak?",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚫ Oq-qora — matnli hujjatlar uchun", callback_data="format_scan_mode:bw")],
            [InlineKeyboardButton(text="🎨 Rangli — muhr, rasm, rangli blanka uchun", callback_data="format_scan_mode:color")],
        ]),
    )


@router.callback_query(F.data.startswith("format_scan_mode:"))
async def ask_scan_images(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    mode = callback.data.split(":", 1)[1]
    if mode not in SCAN_MODES:
        return
    _remove(_user_img_dir(callback.from_user.id))
    await state.set_state(FormatConverterStates.collecting_images)
    await state.update_data(images=[], status_id=None, purpose="scan", mode=mode)
    await callback.message.edit_text(
        f"📸 <b>Skanerlash — {SCAN_MODES[mode]}</b>\n\n"
        f"Hujjat sahifalarining suratlarini yuboring (ko'pi bilan {MAX_IMAGES_PER_PDF} ta, albom qilib ham bo'ladi).\n\n"
        "<b>Yaxshi natija uchun:</b>\n"
        "• qog'ozni qoramtir, bir xil rangli yuzaga qo'ying;\n"
        "• qog'ozning 4 burchagi suratga to'liq tushsin;\n"
        "• yorug' joyda, chaqnoqsiz (vspishkasiz) suratga oling.",
        parse_mode="HTML",
    )


def _scan_all(images: list[str], folder: str, mode: str) -> tuple[list[str], int]:
    """Har bir suratni skanerlaydi. (natija fayllari, qog'ozi topilmagan sahifalar soni)."""
    scanned, not_found = [], 0
    for i, path in enumerate(images, start=1):
        out = os.path.join(folder, f"scan_{i:03d}" + (".png" if mode == "bw" else ".jpg"))
        if not scan_image(path, out, mode):
            not_found += 1
        scanned.append(out)
    return scanned, not_found


@router.message(FormatConverterStates.collecting_images, F.photo | F.document)
async def collect_image(message: Message, state: FSMContext, bot: Bot):
    if message.photo:
        file = message.photo[-1]
        name = "rasm.jpg"
    else:
        file = message.document
        name = file.file_name or "rasm"
        if not name.lower().endswith(IMAGE_EXTENSIONS):
            await message.answer("❌ Bu rasm emas. Qabul qilinadigan formatlar: JPG, PNG, WEBP, HEIC, BMP, TIFF.")
            return
    if not await _check_size(message, file.file_size):
        return

    user_id = message.from_user.id
    async with _lock(user_id):
        if await state.get_state() != FormatConverterStates.collecting_images.state:
            return  # foydalanuvchi bu orada PDF yaratib yoki bekor qilib bo'lgan
        data = await state.get_data()
        images = list(data.get("images", []))
        if len(images) >= MAX_IMAGES_PER_PDF:
            await message.answer(f"⚠️ Ko'pi bilan {MAX_IMAGES_PER_PDF} ta rasm. «✅ PDF yaratish» tugmasini bosing.")
            return

        folder = _user_img_dir(user_id)
        os.makedirs(folder, exist_ok=True)
        ext = os.path.splitext(name)[1].lower() or ".jpg"
        path = os.path.join(folder, f"{len(images) + 1:03d}{ext}")
        await bot.download(file, destination=path)
        images.append(path)

        text = f"📥 Qabul qilindi: <b>{len(images)}</b> ta rasm.\nYana yuboring yoki PDF yarating."
        status_id = data.get("status_id")
        if status_id:
            try:
                await bot.delete_message(message.chat.id, status_id)
            except Exception:
                pass
        status = await message.answer(text, parse_mode="HTML", reply_markup=_img2pdf_keyboard(len(images)))
        await state.update_data(images=images, status_id=status.message_id)


@router.callback_query(F.data == "format_img2pdf_cancel")
async def cancel_images(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Bekor qilindi")
    async with _lock(callback.from_user.id):
        _remove(_user_img_dir(callback.from_user.id))
        await state.clear()
    await callback.message.edit_text("❌ Bekor qilindi.")


@router.message(FormatConverterStates.collecting_images, Command("done"))
@router.callback_query(F.data == "format_img2pdf_done")
async def build_pdf(event: Message | CallbackQuery, state: FSMContext):
    message = event.message if isinstance(event, CallbackQuery) else event
    user_id = event.from_user.id
    if isinstance(event, CallbackQuery):
        await event.answer()

    async with _lock(user_id):
        if await state.get_state() != FormatConverterStates.collecting_images.state:
            await message.answer("Bu sessiya tugagan. Qaytadan «🖼 Rasm(lar) ➡️ PDF» ni tanlang.")
            return
        data = await state.get_data()
        images, purpose, mode = data.get("images", []), data.get("purpose", "pdf"), data.get("mode", "bw")
        await state.clear()

    folder = _user_img_dir(user_id)
    if not images:
        await message.answer("❌ Hali birorta rasm yubormadingiz.")
        _remove(folder)
        return

    pdf_path = _tmp(f"img2pdf_{user_id}.pdf")
    scanning = purpose == "scan"
    status = await message.answer(
        f"⏳ {len(images)} ta sahifa skanerlanmoqda..." if scanning else f"⏳ {len(images)} ta rasmdan PDF yaratilmoqda..."
    )
    try:
        note = ""
        if scanning:
            images, not_found = await _run(message, status, _scan_all, images, folder, mode)
            if not_found:
                note = (f"\n\n⚠️ {not_found} ta suratda qog'oz chegarasi aniqlanmadi — ular butunligicha tozalandi. "
                        "Aniqroq natija uchun qog'ozni qoramtir yuzada, 4 burchagi ko'rinadigan qilib suratga oling.")
        await _run(message, status, ConverterService.images_to_pdf, images, pdf_path)
        await message.answer_document(
            FSInputFile(pdf_path, filename="skan.pdf" if scanning else "rasmlar.pdf"),
            caption=f"✅ Tayyor! {len(images)} sahifali PDF ({human_size(os.path.getsize(pdf_path))}).{note}",
        )
        await status.delete()
    except ConversionError as e:
        await status.edit_text(str(e))
    except Exception:
        logging.exception("Rasm → PDF xatolik")
        await status.edit_text("❌ PDF yaratishda xatolik yuz berdi.")
    finally:
        _remove(folder, pdf_path)


# ── 📄 PDF → Rasm ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "format_pdf2img")
async def ask_pdf2img(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(FormatConverterStates.waiting_for_pdf2img)
    await callback.message.edit_text(
        "📄 <b>PDF dan rasmga</b>\n\n"
        f"PDF faylni yuboring (ko'pi bilan {MAX_PDF2IMG_PAGES} sahifa).\n"
        "Bitta sahifa bo'lsa — JPG rasm, bir nechta bo'lsa — barcha rasmlar ZIP arxivda qaytadi.",
        parse_mode="HTML",
    )


@router.message(FormatConverterStates.waiting_for_pdf2img, F.document)
async def process_pdf2img(message: Message, state: FSMContext, bot: Bot):
    doc = message.document
    if not (doc.file_name or "").lower().endswith(".pdf"):
        await message.answer("Iltimos, faqat .pdf formatidagi fayl yuboring.")
        return
    if not await _check_size(message, doc.file_size):
        return

    pdf_path = _tmp(f"p2i_{doc.file_unique_id}.pdf")
    out_dir = _tmp(f"p2i_{doc.file_unique_id}")
    status = await message.answer("⏳ Sahifalar rasmga aylantirilmoqda...")
    try:
        await bot.download(doc, destination=pdf_path)
        stem = _stem(doc.file_name, "sahifa")
        files = await _run(message, status, ConverterService.pdf_to_images, pdf_path, out_dir, stem)
        await message.answer_document(FSInputFile(files[0]), caption="✅ Tayyor!")
        await status.delete()
    except ConversionError as e:
        await status.edit_text(str(e))
    except Exception:
        logging.exception("PDF → rasm xatolik")
        await status.edit_text("❌ PDF'ni rasmga aylantirishda xatolik yuz berdi.")
    finally:
        _remove(pdf_path, out_dir)
        await state.clear()


# ── 🗜 PDF siqish ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "format_compress")
async def ask_compress(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(FormatConverterStates.waiting_for_compress)
    await callback.message.edit_text(
        "🗜 <b>PDF hajmini kichraytirish</b>\n\n"
        "PDF faylni yuboring. Ichidagi katta rasmlar siqiladi, matn sifati o'zgarmaydi.\n"
        "<i>Rasmli (skaner qilingan) PDF'lar eng ko'p kichrayadi.</i>",
        parse_mode="HTML",
    )


@router.message(FormatConverterStates.waiting_for_compress, F.document)
async def process_compress(message: Message, state: FSMContext, bot: Bot):
    doc = message.document
    if not (doc.file_name or "").lower().endswith(".pdf"):
        await message.answer("Iltimos, faqat .pdf formatidagi fayl yuboring.")
        return
    if not await _check_size(message, doc.file_size):
        return

    in_path = _tmp(f"cmp_in_{doc.file_unique_id}.pdf")
    out_path = _tmp(f"cmp_out_{doc.file_unique_id}.pdf")
    status = await message.answer("⏳ PDF siqilmoqda...")
    try:
        await bot.download(doc, destination=in_path)
        before, after = await _run(message, status, ConverterService.compress_pdf, in_path, out_path)
        if after >= before * 0.9:  # 10% dan kam foyda — yuborishga arzimaydi
            await status.edit_text(
                f"ℹ️ Bu PDF allaqachon ixcham ({human_size(before)}). Sezilarli kichraytirib bo'lmadi."
            )
            return
        saved = round((1 - after / before) * 100)
        await message.answer_document(
            FSInputFile(out_path, filename=f"{_stem(doc.file_name, 'hujjat')}_kichik.pdf"),
            caption=f"✅ Tayyor! {human_size(before)} → {human_size(after)} ({saved}% kichraydi).",
        )
        await status.delete()
    except ConversionError as e:
        await status.edit_text(str(e))
    except Exception:
        logging.exception("PDF siqish xatolik")
        await status.edit_text("❌ PDF'ni siqishda xatolik yuz berdi.")
    finally:
        _remove(in_path, out_path)
        await state.clear()


# ── 📱 Rasm formati → JPG ──────────────────────────────────────────────────

@router.callback_query(F.data == "format_img2jpg")
async def ask_img2jpg(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(FormatConverterStates.waiting_for_img2jpg)
    formats = "HEIC (iPhone), WEBP, PNG, BMP, TIFF" if HEIC_SUPPORTED else "WEBP, PNG, BMP, TIFF"
    await callback.message.edit_text(
        "📱 <b>Rasmni JPG formatiga o'tkazish</b>\n\n"
        f"Rasmni <b>fayl sifatida</b> yuboring ({formats}).\n"
        "Bir nechta faylni ketma-ket yuborishingiz mumkin.\n\n"
        "<i>Tugatish uchun bosh menyudan boshqa bo'limni tanlang.</i>",
        parse_mode="HTML",
    )


@router.message(FormatConverterStates.waiting_for_img2jpg, F.photo)
async def img2jpg_photo_hint(message: Message):
    await message.answer(
        "ℹ️ Telegram «rasm» sifatida yuborilgan suratlarni o'zi JPG qiladi.\n"
        "Formatni o'zgartirish uchun rasmni 📎 → <b>Fayl</b> sifatida yuboring.",
        parse_mode="HTML",
    )


@router.message(FormatConverterStates.waiting_for_img2jpg, F.document)
async def process_img2jpg(message: Message, bot: Bot):
    doc = message.document
    name = doc.file_name or "rasm"
    if not name.lower().endswith(IMAGE_EXTENSIONS):
        await message.answer("❌ Bu rasm emas. Qabul qilinadigan formatlar: HEIC, WEBP, PNG, BMP, TIFF.")
        return
    if not await _check_size(message, doc.file_size):
        return

    ext = os.path.splitext(name)[1].lower()
    in_path = _tmp(f"i2j_in_{doc.file_unique_id}{ext}")
    out_path = _tmp(f"i2j_out_{doc.file_unique_id}.jpg")
    status = await message.answer("⏳ JPG ga o'tkazilmoqda...")
    try:
        await bot.download(doc, destination=in_path)
        await _run(message, status, ConverterService.image_to_jpg, in_path, out_path)
        await message.answer_document(
            FSInputFile(out_path, filename=f"{_stem(name, 'rasm')}.jpg"),
            caption=f"✅ Tayyor! ({human_size(os.path.getsize(out_path))})",
        )
        await status.delete()
    except ConversionError as e:
        await status.edit_text(str(e))
    except Exception:
        logging.exception("Rasm → JPG xatolik")
        await status.edit_text("❌ Rasmni o'tkazishda xatolik yuz berdi.")
    finally:
        _remove(in_path, out_path)
