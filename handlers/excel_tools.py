"""✂️ Excelni qatorlarga qirqish: ko'rsatilgan oraliqdagi qatorlarni alohida faylga ajratadi."""
import logging
import os
import re

from aiogram import Router, F, Bot
from aiogram.types import Message, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from services.converter_service import run_heavy
from services.excel_common import is_excel, size_error, read_table
from services.tempfiles import new_job_dir, remove, safe_filename

router = Router()


class ExcelSplitterStates(StatesGroup):
    waiting_for_file = State()
    waiting_for_range = State()


@router.message(F.text == "✂️ Excel qirqish")
async def start_excel_split(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Iltimos, qirqmoqchi bo'lgan Excel (.xlsx yoki .xls) faylingizni yuboring.")
    await state.set_state(ExcelSplitterStates.waiting_for_file)


@router.message(ExcelSplitterStates.waiting_for_file, F.document)
async def process_excel_file(message: Message, state: FSMContext, bot: Bot):
    doc = message.document
    if not is_excel(doc.file_name):
        await message.answer("Iltimos, faqat .xlsx yoki .xls formatidagi fayl yuboring.")
        return
    if error := size_error(doc.file_size):
        await message.answer(error)
        return

    remove((await state.get_data()).get("job_dir"))
    job_dir = new_job_dir("xlcut")
    file_path = os.path.join(job_dir, "input" + os.path.splitext(doc.file_name)[1].lower())
    await bot.download(doc, destination=file_path)
    try:
        rows = len(await run_heavy(read_table, file_path))
    except Exception:
        logging.exception("Excel qirqish: faylni o'qib bo'lmadi")
        remove(job_dir)
        await message.answer("❌ Faylni o'qib bo'lmadi. Fayl buzilgan yoki format noto'g'ri bo'lishi mumkin.")
        await state.clear()
        return
    if rows == 0:
        remove(job_dir)
        await message.answer("❌ Faylda ma'lumot qatorlari topilmadi.")
        await state.clear()
        return

    await state.update_data(job_dir=job_dir, file_path=file_path, original_name=doc.file_name, rows=rows)
    await message.answer(
        f"Fayl qabul qilindi: <b>{rows}</b> ta ma'lumot qatori (sarlavhadan tashqari).\n\n"
        "Qaysi qatorlarni qirqib olamiz? Oraliqni kiriting (masalan: <code>1-50</code>):",
        parse_mode="HTML",
    )
    await state.set_state(ExcelSplitterStates.waiting_for_range)


def _cut(file_path: str, out_path: str, start: int, end: int) -> int:
    df = read_table(file_path)
    part = df.iloc[start - 1:end]
    part.to_excel(out_path, index=False)
    return len(part)


@router.message(ExcelSplitterStates.waiting_for_range, F.text)
async def process_excel_range(message: Message, state: FSMContext):
    data = await state.get_data()
    rows = data.get("rows", 0)
    match = re.fullmatch(r"\s*(\d+)\s*[-–—]\s*(\d+)\s*", message.text)
    if not match or int(match.group(1)) < 1 or int(match.group(2)) < int(match.group(1)):
        await message.answer("Noto'g'ri format. Oraliqni kiriting (masalan: <code>1-50</code>):", parse_mode="HTML")
        return
    start, end = int(match.group(1)), min(int(match.group(2)), rows)
    if start > rows:
        await message.answer(f"Faylda faqat {rows} ta qator bor. 1 dan {rows} gacha oraliq kiriting:")
        return

    job_dir = data["job_dir"]
    stem = safe_filename(os.path.splitext(data["original_name"])[0], "jadval")
    out_path = os.path.join(job_dir, f"{stem}_{start}-{end}.xlsx")
    msg = await message.answer("Fayl qirqilmoqda, kuting... ⏳")
    try:
        count = await run_heavy(_cut, data["file_path"], out_path, start, end)
        await message.answer_document(
            FSInputFile(out_path),
            caption=f"✅ Tayyor! {start}–{end} qatorlar ({count} ta) qirqib olindi. Sarlavha qatori saqlandi.",
        )
        await msg.delete()
    except Exception:
        logging.exception("Excelni qirqishda xato")
        await msg.edit_text("❌ Xatolik yuz berdi. Fayl formati noto'g'ri bo'lishi mumkin.")
    finally:
        remove(job_dir)
        await state.clear()
