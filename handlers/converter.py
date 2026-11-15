import os
import logging

from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, FSInputFile,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from deep_translator import GoogleTranslator

from services.transliterator import (
    to_cyrillic, to_latin, to_new_latin,
    transliterate_docx, docx_has_text,
)
from services.converter_service import ConverterService

router = Router()

TEMP_DIR = "temp"
MAX_FILE_SIZE = 20 * 1024 * 1024  # Telegram bot API yuklab olish chegarasi
TELEGRAM_TEXT_LIMIT = 4000

# Alifbo yo'nalishlari: callback -> (nomi, o'girish funksiyasi)
ALPHABET_DIRECTIONS = {
    "conv_lat_cyr": ("Lotin ➡️ Kirill", to_cyrillic),
    "conv_cyr_lat": ("Kirill ➡️ Lotin", to_latin),
    "conv_lat_new": ("Lotin ➡️ Yangi lotin", to_new_latin),
}

TRANSLATE_DIRECTIONS = {
    "trans_en_uz": "Inglizcha ➡️ O'zbekcha",
    "trans_uz_en": "O'zbekcha ➡️ Inglizcha",
    "trans_ru_uz": "Ruscha ➡️ O'zbekcha",
    "trans_uz_ru": "O'zbekcha ➡️ Ruscha",
}


class ConverterStates(StatesGroup):
    waiting_for_text = State()


def get_direction_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(text="🇺🇿 Lotin ➡️ Kirill", callback_data="conv_lat_cyr"),
            InlineKeyboardButton(text="🇺🇿 Kirill ➡️ Lotin", callback_data="conv_cyr_lat"),
        ],
        [
            InlineKeyboardButton(text="🆕 Lotin ➡️ Yangi lotin (ó, ǵ, ş, ç, ñ)", callback_data="conv_lat_new"),
        ],
        [
            InlineKeyboardButton(text="🇬🇧 EN ➡️ 🇺🇿 UZ", callback_data="trans_en_uz"),
            InlineKeyboardButton(text="🇺🇿 UZ ➡️ 🇬🇧 EN", callback_data="trans_uz_en"),
        ],
        [
            InlineKeyboardButton(text="🇷🇺 RU ➡️ 🇺🇿 UZ", callback_data="trans_ru_uz"),
            InlineKeyboardButton(text="🇺🇿 UZ ➡️ 🇷🇺 RU", callback_data="trans_uz_ru"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


TRANSLATOR_TITLE = "🔤 <b>Tarjimon va Alifbo</b>\n\nYo'nalishni tanlang:"


@router.message(F.text == "🔤 Tarjimon va Alifbo")
@router.message(F.text == "🔄 Tarjimon / Alifbo")   # eski tugma nomi
@router.message(F.text == "🔄 Lotin <-> Kirill")    # eski tugma nomi
async def start_converter(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(TRANSLATOR_TITLE, parse_mode="HTML", reply_markup=get_direction_menu())


@router.callback_query(F.data.in_(set(ALPHABET_DIRECTIONS) | set(TRANSLATE_DIRECTIONS)))
async def process_direction(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    direction = callback.data
    await state.update_data(direction=direction)

    if direction in ALPHABET_DIRECTIONS:
        dir_text = ALPHABET_DIRECTIONS[direction][0]
        prompt = (
            f"Siz <b>{dir_text}</b> yo'nalishini tanladingiz.\n\n"
            "Matn yozing yoki fayl yuboring:\n"
            "• 📝 Word (<b>.docx</b>) — Word fayl qaytadi, formatlash saqlanadi\n"
            "• 📄 PDF (<b>.pdf</b>) — Word fayl qaytadi\n"
            "• 🗒 Matn fayl (<b>.txt</b>) — .txt fayl qaytadi"
        )
        if direction == "conv_lat_new":
            prompt += (
                "\n\n<i>Almashtirishlar: o' → ó, g' → ǵ, sh → ş, ch → ç, ng → ñ</i>"
            )
    else:
        dir_text = TRANSLATE_DIRECTIONS[direction]
        prompt = (
            f"Siz <b>{dir_text}</b> yo'nalishini tanladingiz.\n\n"
            "Endi tarjima qilish uchun matnni yuboring:"
        )

    await callback.message.edit_text(prompt, parse_mode="HTML")
    await state.set_state(ConverterStates.waiting_for_text)


@router.message(ConverterStates.waiting_for_text, F.text)
async def convert_text(message: Message, state: FSMContext):
    data = await state.get_data()
    direction = data.get("direction")

    if not direction:
        await message.answer("Iltimos, avval yo'nalishni tanlang!")
        await state.clear()
        return

    text = message.text
    msg = await message.answer("Kuting... ⏳")

    try:
        if direction in ALPHABET_DIRECTIONS:
            result = ALPHABET_DIRECTIONS[direction][1](text)
        else:
            _, src, dest = direction.split("_")
            result = GoogleTranslator(source=src, target=dest).translate(text)

        if len(result) > TELEGRAM_TEXT_LIMIT:
            # Uzun natijani fayl qilib yuboramiz
            os.makedirs(TEMP_DIR, exist_ok=True)
            out_path = os.path.join(TEMP_DIR, f"natija_{message.from_user.id}.txt")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(result)
            try:
                await message.answer_document(FSInputFile(out_path, filename="natija.txt"),
                                              caption="✅ Natija juda uzun bo'lgani uchun fayl qilib yuborildi.")
            finally:
                os.remove(out_path)
            await msg.delete()
            return

        # Natijani oddiy matn sifatida yuboramiz: foydalanuvchi matnidagi * _ ` kabi
        # belgilar Markdown sifatida talqin qilinib, xabarni buzmasligi uchun.
        await msg.edit_text(
            f"Natija:\n\n{result}\n\n"
            "Yana matn yoki fayl yuborishingiz yoki bosh menyudan boshqa bo'limni tanlashingiz mumkin."
        )
    except Exception as e:
        logging.error(f"Tarjimada xatolik: {e}")
        await msg.edit_text("Xatolik yuz berdi. Iltimos keyinroq urinib ko'ring yoki boshqa matn yuboring.")


def _read_text_file(path: str) -> str:
    """Matn faylni o'qiydi (UTF-8, eski Windows fayllari uchun cp1251)."""
    with open(path, "rb") as f:
        raw = f.read()
    for encoding in ("utf-8-sig", "cp1251"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


@router.message(ConverterStates.waiting_for_text, F.document)
async def convert_file(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    direction = data.get("direction")

    if direction not in ALPHABET_DIRECTIONS:
        await message.answer(
            "📄 Fayllar faqat <b>alifbo</b> yo'nalishlarida qabul qilinadi.\n"
            "Tarjima uchun matnni xabar qilib yuboring.",
            parse_mode="HTML",
        )
        return

    doc = message.document
    name = doc.file_name or "fayl"
    base, ext = os.path.splitext(name)
    ext = ext.lower()

    if ext not in (".docx", ".pdf", ".txt"):
        await message.answer(
            "❌ Bu format qo'llab-quvvatlanmaydi.\n"
            "Faqat <b>.docx</b>, <b>.pdf</b> yoki <b>.txt</b> fayl yuboring.\n\n"
            "<i>Eski .doc fayl bo'lsa, uni Word'da .docx qilib saqlab yuboring.</i>",
            parse_mode="HTML",
        )
        return

    if doc.file_size and doc.file_size > MAX_FILE_SIZE:
        await message.answer("❌ Fayl juda katta. 20 MB dan kichik fayl yuboring.")
        return

    convert = ALPHABET_DIRECTIONS[direction][1]
    os.makedirs(TEMP_DIR, exist_ok=True)
    in_path = os.path.join(TEMP_DIR, f"alifbo_in_{doc.file_unique_id}{ext}")
    mid_path = os.path.join(TEMP_DIR, f"alifbo_mid_{doc.file_unique_id}.docx")
    out_ext = ".txt" if ext == ".txt" else ".docx"
    out_path = os.path.join(TEMP_DIR, f"alifbo_out_{doc.file_unique_id}{out_ext}")

    msg = await message.answer("📥 Fayl qabul qilindi, o'girilmoqda... ⏳")
    try:
        await bot.download(doc, destination=in_path)

        if ext == ".txt":
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(convert(_read_text_file(in_path)))
        elif ext == ".docx":
            transliterate_docx(in_path, out_path, convert)
        else:  # .pdf → avval Word'ga, keyin o'giramiz
            if not ConverterService.pdf_to_word(in_path, mid_path) or not docx_has_text(mid_path):
                await msg.edit_text(
                    "❌ PDF ichidan matn topilmadi.\n\n"
                    "Fayl skaner qilingan (rasm ko'rinishidagi) bo'lishi mumkin. "
                    "Bunday faylni avval OCR orqali matnga o'giring."
                )
                return
            transliterate_docx(mid_path, out_path, convert)

        await message.answer_document(
            FSInputFile(out_path, filename=f"{base}_{direction.split('_')[-1]}{out_ext}"),
            caption=f"✅ Tayyor! ({ALPHABET_DIRECTIONS[direction][0]})\n\nYana fayl yoki matn yuborishingiz mumkin.",
        )
        await msg.delete()
    except Exception as e:
        logging.exception(f"Faylni alifboga o'girishda xatolik: {e}")
        await msg.edit_text("❌ Faylni o'girishda xatolik yuz berdi. Fayl buzilgan bo'lishi mumkin.")
    finally:
        for path in (in_path, mid_path, out_path):
            if os.path.exists(path):
                os.remove(path)
