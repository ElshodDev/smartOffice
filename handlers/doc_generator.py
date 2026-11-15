"""✍️ Rasmiy hujjat yaratish: turini tanlash → savollarga javob → Word hujjat."""
import html
import logging
import os

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from services import ai_text
from services.converter_service import run_heavy
from services.doc_generator import DOC_TYPES, ai_prompt, body_paragraphs, build_docx
from services.tempfiles import new_job_dir, remove, safe_filename

router = Router()

MAX_ANSWER_LENGTH = 600


class DocGenStates(StatesGroup):
    answering = State()
    choosing_alphabet = State()


def doc_types_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=doc.title, callback_data=f"docgen_type:{key}")] for key, doc in DOC_TYPES.items()
    ])


@router.callback_query(F.data == "docgen")
async def docgen_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "✍️ <b>Rasmiy hujjat yaratish</b>\n\n"
        "Hujjat turini tanlang. Bir nechta savolga javob berasiz — bot rasmiy shakldagi Word hujjatni tayyorlab beradi.",
        parse_mode="HTML",
        reply_markup=doc_types_menu(),
    )


async def _ask(message: Message, state: FSMContext):
    data = await state.get_data()
    doc = DOC_TYPES[data["doc_key"]]
    index = data["index"]
    item = doc.fields[index]
    text = f"<b>{index + 1}/{len(doc.fields)}. {html.escape(item.question)}</b>"
    if item.example:
        text += f"\n\n<i>Masalan:</i>\n<code>{html.escape(item.example)}</code>"
    keyboard = None
    if item.optional:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="⏩ O'tkazib yuborish", callback_data="docgen_skip")
        ]])
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data.startswith("docgen_type:"))
async def docgen_choose(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    key = callback.data.split(":", 1)[1]
    if key not in DOC_TYPES:
        return
    await state.clear()
    await state.set_state(DocGenStates.answering)
    await state.update_data(doc_key=key, index=0, values={})
    await callback.message.edit_text(
        f"{DOC_TYPES[key].title}\n\nSavollarga javob bering. Bekor qilish uchun /cancel yozing.",
    )
    await _ask(callback.message, state)


async def _next(message: Message, state: FSMContext, value: str):
    data = await state.get_data()
    doc = DOC_TYPES[data["doc_key"]]
    values = dict(data["values"])
    values[doc.fields[data["index"]].key] = value
    index = data["index"] + 1
    await state.update_data(values=values, index=index)
    if index < len(doc.fields):
        await _ask(message, state)
        return
    await state.set_state(DocGenStates.choosing_alphabet)
    await message.answer(
        "✅ Barcha ma'lumotlar yig'ildi! Hujjat qaysi yozuvda bo'lsin?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Lotin", callback_data="docgen_alpha:lat"),
            InlineKeyboardButton(text="Кирилл", callback_data="docgen_alpha:cyr"),
        ]]),
    )


@router.message(DocGenStates.answering, F.text)
async def docgen_answer(message: Message, state: FSMContext):
    text = message.text.strip()
    if text.startswith("/"):
        return
    if len(text) > MAX_ANSWER_LENGTH:
        await message.answer(f"❌ Javob juda uzun ({len(text)} belgi). {MAX_ANSWER_LENGTH} belgigacha qisqartirib yozing:")
        return
    await _next(message, state, text)


@router.callback_query(DocGenStates.answering, F.data == "docgen_skip")
async def docgen_skip(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    item = DOC_TYPES[data["doc_key"]].fields[data["index"]]
    if not item.optional:
        await callback.answer("Bu savol majburiy", show_alert=True)
        return
    await callback.answer("O'tkazib yuborildi")
    await callback.message.edit_reply_markup(reply_markup=None)
    await _next(callback.message, state, "")


@router.callback_query(DocGenStates.choosing_alphabet, F.data.startswith("docgen_alpha:"))
async def docgen_build(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    await state.clear()
    doc = DOC_TYPES[data["doc_key"]]
    values = data["values"]
    cyrillic = callback.data.endswith(":cyr")

    await callback.message.edit_text("⏳ Hujjat tayyorlanmoqda... (AI asosiy matnni yozmoqda)")
    generated = await ai_text.generate(ai_prompt(doc, values))
    body = body_paragraphs(doc, values, generated)

    job_dir = new_job_dir("docgen")
    name = safe_filename(doc.heading.title().replace(" ", "_"), "hujjat")
    path = os.path.join(job_dir, f"{name}.docx")
    try:
        await run_heavy(build_docx, doc, values, body, path, cyrillic)
        note = (
            "🤖 Asosiy matn AI yordamida yozildi — yuborishdan oldin o'qib chiqing va kerak bo'lsa tahrirlang."
            if generated else
            "📄 Hujjat tayyor shablon asosida tuzildi. Word'da ochib, kerak bo'lsa tahrirlashingiz mumkin."
        )
        await callback.message.answer_document(FSInputFile(path), caption=f"✅ {doc.title} tayyor!\n\n{note}")
        await callback.message.delete()
    except Exception:
        logging.exception("Hujjat yaratishda xato")
        await callback.message.edit_text("❌ Hujjat yaratishda xatolik yuz berdi. Qaytadan urinib ko'ring.")
    finally:
        remove(job_dir)
