import os
import sys
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

# Windows uchun Tesseract yo'li (o'rnatgandan keyin avtomatik topiladi)
try:
    import pytesseract
    # Standart Windows o'rnatish joyi
    # Tesseract yo'lini faqat Windowsda ko'rsatamiz. Linux/Docker da u avtomatik topiladi.
    if sys.platform == "win32":
        tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.exists(tesseract_path):
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
except ImportError:
    pass

router = Router()


class OCRStates(StatesGroup):
    waiting_for_image = State()


@router.message(F.text == "🖼 OCR — Rasmdan matn")
async def ocr_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🖼 <b>OCR — Rasmdan matn o'qish</b>\n\n"
        "Matn yozilgan rasmni yuboring (foto yoki fayl sifatida).\n"
        "<i>Inglizcha, Ruscha va O'zbekcha matnlarni taniydi.</i>",
        parse_mode="HTML"
    )
    await state.set_state(OCRStates.waiting_for_image)


@router.message(OCRStates.waiting_for_image, F.photo | F.document)
async def ocr_process(message: Message, state: FSMContext, bot: Bot):
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        await message.answer("❌ OCR kutubxonasi o'rnatilmagan. Administrator bilan bog'laning.")
        await state.clear()
        return

    os.makedirs("temp", exist_ok=True)

    # Faylni aniqlash (rasm yoki dokument)
    if message.photo:
        photo     = message.photo[-1]
        file_id   = photo.file_id
        file_name = f"ocr_{file_id}.jpg"
    else:
        doc = message.document
        valid_exts = (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp")
        if not any(doc.file_name.lower().endswith(e) for e in valid_exts):
            await message.answer(
                "❌ Iltimos, rasm formatidagi fayl yuboring:\n"
                "<i>.jpg, .jpeg, .png, .bmp, .tiff</i>",
                parse_mode="HTML"
            )
            return
        file_id   = doc.file_id
        file_name = f"ocr_{doc.file_id}_{doc.file_name}"

    img_path = f"temp/{file_name}"
    await bot.download(file_id, destination=img_path)

    msg = await message.answer("🔍 Rasm tahlil qilinmoqda, kuting... ⏳")

    try:
        image = Image.open(img_path)

        # Ko'p tilli tanib olish: O'zbek (lotin), Rus, Ingliz
        extracted = pytesseract.image_to_string(
            image,
            lang="eng+rus+uzb",
            config="--oem 3 --psm 6"
        ).strip()

        if not extracted:
            await msg.edit_text(
                "⚠️ Rasmdan matn topilmadi.\n\n"
                "<i>Maslahat: Rasm aniq va yaxshi yoritilgan bo'lsa natija yaxshiroq bo'ladi.</i>",
                parse_mode="HTML"
            )
            return

        # HTML maxsus belgilarni xavfsiz qilish (injection oldini olish)
        import html as html_module
        safe_text = html_module.escape(extracted)

        # Natijani chiqarish (Telegram 4096 belgi limiti)
        LIMIT = 3800
        if len(safe_text) <= LIMIT:
            await msg.edit_text(
                f"✅ <b>Aniqlangan matn:</b>\n\n"
                f"<code>{safe_text}</code>",
                parse_mode="HTML"
            )
        else:
            # Uzun matnni .txt fayl sifatida yuborish
            await msg.delete()
            txt_path = img_path.replace(img_path.split(".")[-1], "txt").replace(
                f"temp/ocr_", "temp/ocr_result_"
            )
            txt_path = f"temp/ocr_result_{file_id}.txt"
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(extracted)

            result_file = FSInputFile(txt_path, filename="ocr_natija.txt")
            await message.answer_document(
                document=result_file,
                caption=(
                    f"✅ <b>Matn aniqlandi!</b>\n\n"
                    f"📝 Belgilar soni: <b>{len(extracted)}</b>\n"
                    f"Matn .txt fayl sifatida yuborildi."
                ),
                parse_mode="HTML"
            )

            if os.path.exists(txt_path):
                os.remove(txt_path)

    except pytesseract.TesseractNotFoundError:
        await msg.edit_text(
            "❌ Tesseract OCR tizimga o'rnatilmagan.\n\n"
            "<b>O'rnatish uchun:</b>\n"
            "<code>https://github.com/UB-Mannheim/tesseract/wiki</code>\n"
            "O'rnatgach, PATH ga qo'shing.",
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"OCR xatosi: {e}")
        await msg.edit_text("❌ Rasmni tahlil qilishda xatolik yuz berdi.")
    finally:
        if os.path.exists(img_path):
            os.remove(img_path)
        await state.clear()
