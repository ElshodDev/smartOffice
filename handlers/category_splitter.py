"""📑 Ustun qiymatlari bo'yicha alohida fayllarga bo'lish (masalan, har bir viloyat — alohida fayl)."""
import logging
import os
import zipfile

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from services.converter_service import run_heavy
from services.excel_common import (
    is_excel, size_error, read_table, column_keyboard,
    too_many_columns_note, esc, unique_name,
)
from services.tempfiles import new_job_dir, remove, safe_filename

router = Router()

MAX_GROUPS = 200
EMPTY_GROUP = "(bo'sh)"


class CategorySplitterStates(StatesGroup):
    waiting_for_excel = State()
    waiting_for_column = State()


@router.message(F.text == "📑 Toifa bo'yicha bo'lish")
async def start_category_splitter(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "📑 <b>Toifa bo'yicha bo'lish</b>\n\n"
        "Iltimos, bo'laklarga ajratmoqchi bo'lgan Excel (<b>.xlsx</b> yoki <b>.xls</b>) faylni yuboring.",
        parse_mode="HTML",
    )
    await state.set_state(CategorySplitterStates.waiting_for_excel)


@router.message(CategorySplitterStates.waiting_for_excel, F.document)
async def receive_excel(message: Message, state: FSMContext, bot: Bot):
    doc = message.document
    if not is_excel(doc.file_name):
        await message.answer("❌ Iltimos, faqat <b>.xlsx</b> yoki <b>.xls</b> formatidagi Excel fayl yuboring.", parse_mode="HTML")
        return
    if error := size_error(doc.file_size):
        await message.answer(error)
        return

    remove((await state.get_data()).get("job_dir"))
    job_dir = new_job_dir("xlcat")
    file_path = os.path.join(job_dir, "input" + os.path.splitext(doc.file_name)[1].lower())
    await bot.download(doc, destination=file_path)
    try:
        df = await run_heavy(read_table, file_path)
    except Exception:
        logging.exception("Category splitter — fayl o'qishda xato")
        remove(job_dir)
        await message.answer("❌ Faylni o'qishda xatolik. Fayl buzilgan yoki format noto'g'ri bo'lishi mumkin.")
        await state.clear()
        return
    if df.empty or len(df.columns) == 0:
        remove(job_dir)
        await message.answer("❌ Fayl bo'sh yoki noto'g'ri formatda.")
        await state.clear()
        return

    await state.update_data(job_dir=job_dir, file_path=file_path, original_name=doc.file_name)
    await state.set_state(CategorySplitterStates.waiting_for_column)
    await message.answer(
        f"✅ Fayl qabul qilindi! (<b>{len(df)}</b> qator, <b>{len(df.columns)}</b> ustun)\n\n"
        "📌 Qaysi <b>ustun</b> bo'yicha ajratmoqchisiz?" + too_many_columns_note(df.columns),
        parse_mode="HTML",
        reply_markup=column_keyboard(df.columns, "catcol"),
    )


def _split_by_column(file_path: str, job_dir: str, base_name: str, column_index: int):
    df = read_table(file_path)
    column = df.columns[column_index]
    keys = df[column].astype(object).where(df[column].notna(), EMPTY_GROUP)
    groups = list(df.groupby(keys, sort=False, dropna=False))  # sort=False: aralash turdagi qiymatlar ham ishlaydi
    if len(groups) > MAX_GROUPS:
        return None, column, len(groups), 0, len(df)

    zip_path = os.path.join(job_dir, f"{base_name}_ustun_boyicha.zip")
    used: set[str] = set()
    empty_rows = int(df[column].isna().sum())
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for i, (category, group_df) in enumerate(groups):
            part_path = os.path.join(job_dir, f"part_{i}.xlsx")
            group_df.to_excel(part_path, index=False)
            name = unique_name(f"{safe_filename(category, EMPTY_GROUP, 50)}.xlsx", used)
            zipf.write(part_path, arcname=name)
            os.remove(part_path)
    return zip_path, column, len(groups), empty_rows, len(df)


@router.callback_query(CategorySplitterStates.waiting_for_column, F.data.startswith("catcol:"))
async def split_by_column(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    job_dir, file_path = data.get("job_dir"), data.get("file_path")
    if not file_path or not os.path.exists(file_path):
        await callback.message.answer("❌ Fayl topilmadi. Iltimos, amalni boshidan boshlang.")
        await state.clear()
        return
    try:
        column_index = int(callback.data.split(":", 1)[1])
    except ValueError:
        return
    await state.clear()

    base_name = safe_filename(os.path.splitext(data.get("original_name", ""))[0], "jadval")
    msg = await callback.message.edit_text("⏳ Ajratilmoqda...")
    try:
        zip_path, column, total_groups, empty_rows, total_rows = await run_heavy(
            _split_by_column, file_path, job_dir, base_name, column_index
        )
        if zip_path is None:
            await msg.edit_text(
                f"❌ «{esc(column)}» ustunida {total_groups} xil qiymat bor — bu {total_groups} ta fayl bo'ladi "
                f"(ko'pi bilan {MAX_GROUPS}).\nTakrorlanadigan qiymatli ustunni tanlang (masalan, viloyat yoki bo'lim).",
                parse_mode="HTML",
            )
            return
        note = f"\n⚠️ «{EMPTY_GROUP}» fayliga ustuni bo'sh bo'lgan {empty_rows} ta qator tushdi." if empty_rows else ""
        await callback.message.answer_document(
            FSInputFile(zip_path),
            caption=(
                f"✅ <b>Tayyor!</b>\n\n"
                f"📊 Ustun: <b>{esc(column)}</b>\n"
                f"📁 Yaratilgan fayllar: <b>{total_groups} ta</b> (jami {total_rows} qator){esc(note)}"
            ),
            parse_mode="HTML",
        )
        await msg.delete()
    except Exception:
        logging.exception("Category splitter xatosi")
        await msg.edit_text("❌ Ajratish jarayonida xatolik yuz berdi. Fayl tuzilmasi noto'g'ri bo'lishi mumkin.")
    finally:
        remove(job_dir)
