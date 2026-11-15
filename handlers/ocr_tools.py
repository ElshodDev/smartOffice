"""🖼 OCR — rasmdan matn o'qish (o'zbek, rus, ingliz). Bir nechta rasmni ketma-ket yuborish mumkin."""
import html
import logging
import os
import sys

from aiogram import Router, F, Bot
from aiogram.types import Message, FSInputFile, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from PIL import Image, ImageOps

from services.converter_service import run_heavy, MAX_FILE_SIZE, human_size, IMAGE_EXTENSIONS
from services.tempfiles import new_job_dir, remove

try:
    import pytesseract
    if sys.platform == "win32":  # Linux/Docker'da Tesseract avtomatik topiladi
        _win_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.exists(_win_path):
            pytesseract.pytesseract.tesseract_cmd = _win_path
except ImportError:
    pytesseract = None

router = Router()

TEXT_LIMIT = 3800
OCR_MAX_SIDE = 3000

OCR_INTRO = (
    "🖼 <b>Rasmdan matn o'qish (OCR)</b>\n\n"
    "Matn yozilgan rasmni yuboring (foto yoki fayl sifatida). O'zbek, rus va ingliz matnlarini taniydi.\n"
    "<i>Bir nechta rasmni ketma-ket yuborishingiz mumkin. Aniq natija uchun rasm tiniq va yaxshi yoritilgan bo'lsin.</i>"
)
FINISH_KB = InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text="✅ Tugatish", callback_data="ocr_finish")
]])


class OCRStates(StatesGroup):
    waiting_for_image = State()


@router.message(F.text == "🖼 OCR — Rasmdan matn")
async def ocr_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(OCR_INTRO, parse_mode="HTML")
    await state.set_state(OCRStates.waiting_for_image)


@router.callback_query(F.data == "tools_ocr")
async def ocr_start_cb(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(OCR_INTRO, parse_mode="HTML")
    await state.set_state(OCRStates.waiting_for_image)


def _recognize(path: str) -> str:
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert("L")
        if max(image.size) > OCR_MAX_SIDE:
            image.thumbnail((OCR_MAX_SIDE, OCR_MAX_SIDE))
        return pytesseract.image_to_string(image, lang="uzb+rus+eng", config="--oem 3 --psm 6").strip()


@router.message(OCRStates.waiting_for_image, F.photo | F.document)
async def ocr_process(message: Message, bot: Bot):
    if pytesseract is None:
        await message.answer("❌ OCR kutubxonasi o'rnatilmagan. Administrator bilan bog'laning.")
        return
    if message.photo:
        file, ext = message.photo[-1], ".jpg"
    else:
        file = message.document
        name = (file.file_name or "").lower()
        if not name.endswith(IMAGE_EXTENSIONS):
            await message.answer("❌ Rasm yuboring: JPG, PNG, WEBP, HEIC, BMP yoki TIFF.\n"
                                 "<i>PDF bo'lsa, avval «PDF ➡️ Rasm» orqali rasmga o'giring.</i>", parse_mode="HTML")
            return
        ext = os.path.splitext(name)[1]
    if file.file_size and file.file_size > MAX_FILE_SIZE:
        await message.answer(f"❌ Fayl juda katta ({human_size(file.file_size)}). Limit — 20 MB.")
        return

    job_dir = new_job_dir("ocr")
    img_path = os.path.join(job_dir, "image" + ext)
    msg = await message.answer("🔍 Rasm tahlil qilinmoqda, kuting... ⏳")
    try:
        await bot.download(file, destination=img_path)
        text = await run_heavy(_recognize, img_path)
        if not text:
            await msg.edit_text(
                "⚠️ Rasmdan matn topilmadi.\n\n<i>Rasm aniq, to'g'ri burchakda va yaxshi yoritilgan bo'lsin.</i>",
                parse_mode="HTML", reply_markup=FINISH_KB,
            )
            return
        safe = html.escape(text)
        if len(safe) <= TEXT_LIMIT:
            await msg.edit_text(f"✅ <b>Aniqlangan matn:</b>\n\n<code>{safe}</code>", parse_mode="HTML", reply_markup=FINISH_KB)
        else:
            txt_path = os.path.join(job_dir, "ocr_natija.txt")
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(text)
            await message.answer_document(
                FSInputFile(txt_path),
                caption=f"✅ Matn aniqlandi ({len(text)} belgi) — .txt faylda.",
                reply_markup=FINISH_KB,
            )
            await msg.delete()
    except Exception as e:
        if pytesseract and isinstance(e, pytesseract.TesseractNotFoundError):
            logging.error("Tesseract o'rnatilmagan")
            await msg.edit_text("❌ Serverda OCR dasturi (Tesseract) o'rnatilmagan. Administrator bilan bog'laning.")
        else:
            logging.exception("OCR xatosi")
            await msg.edit_text("❌ Rasmni tahlil qilishda xatolik yuz berdi. Boshqa rasm yuborib ko'ring.",
                                reply_markup=FINISH_KB)
    finally:
        remove(job_dir)


@router.callback_query(F.data == "ocr_finish")
async def ocr_finish(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Tugatildi")
    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
