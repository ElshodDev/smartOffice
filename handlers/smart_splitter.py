"""📊 Excelni teng bo'laklarga bo'lish: har N qatordan alohida fayl, hammasi ZIP'da."""
import logging
import math
import os
import zipfile

from aiogram import Router, F, Bot
from aiogram.types import Message, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from services.converter_service import run_heavy
from services.excel_common import is_excel, size_error, read_table
from services.tempfiles import new_job_dir, remove, safe_filename

router = Router()

MAX_PARTS = 200


class SmartSplitterStates(StatesGroup):
    waiting_for_file = State()
    waiting_for_row_count = State()


@router.message(F.text == "📊 Smart Splitter")
async def start_smart_splitter(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Iltimos, bo'laklarga ajratmoqchi bo'lgan Excel (.xlsx yoki .xls) faylingizni yuboring.")
    await state.set_state(SmartSplitterStates.waiting_for_file)


@router.message(SmartSplitterStates.waiting_for_file, F.document)
async def process_splitter_file(message: Message, state: FSMContext, bot: Bot):
    doc = message.document
    if not is_excel(doc.file_name):
        await message.answer("Iltimos, faqat .xlsx yoki .xls formatidagi Excel fayl yuboring.")
        return
    if error := size_error(doc.file_size):
        await message.answer(error)
        return

    remove((await state.get_data()).get("job_dir"))
    job_dir = new_job_dir("xlsplit")
    file_path = os.path.join(job_dir, "input" + os.path.splitext(doc.file_name)[1].lower())
    await bot.download(doc, destination=file_path)
    try:
        rows = len(await run_heavy(read_table, file_path))
    except Exception:
        logging.exception("Smart splitter: faylni o'qib bo'lmadi")
        remove(job_dir)
        await message.answer("❌ Faylni o'qib bo'lmadi. Fayl buzilgan yoki format noto'g'ri bo'lishi mumkin.")
        await state.clear()
        return
    if rows == 0:
        remove(job_dir)
        await message.answer("❌ Faylda ma'lumot topilmadi (bo'sh fayl).")
        await state.clear()
        return

    await state.update_data(job_dir=job_dir, file_path=file_path, original_name=doc.file_name, rows=rows)
    await message.answer(
        f"Fayl qabul qilindi: <b>{rows}</b> ta qator.\n\n"
        "Har bir bo'lakda nechta qator bo'lsin? (masalan: <code>500</code>)",
        parse_mode="HTML",
    )
    await state.set_state(SmartSplitterStates.waiting_for_row_count)


def _split(file_path: str, job_dir: str, base_name: str, row_count: int) -> tuple[str, int]:
    df = read_table(file_path)
    num_chunks = math.ceil(len(df) / row_count)
    zip_path = os.path.join(job_dir, f"{base_name}_bo'laklar.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for i in range(num_chunks):
            part_path = os.path.join(job_dir, f"part_{i + 1}.xlsx")
            df.iloc[i * row_count:(i + 1) * row_count].to_excel(part_path, index=False)
            zipf.write(part_path, arcname=f"{base_name}_{i + 1:03d}.xlsx")
            os.remove(part_path)
    return zip_path, num_chunks


@router.message(SmartSplitterStates.waiting_for_row_count, F.text)
async def process_row_count(message: Message, state: FSMContext):
    data = await state.get_data()
    rows = data.get("rows", 0)
    try:
        row_count = int(message.text.strip())
        if row_count <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Iltimos, faqat musbat butun son kiriting (masalan: 500):")
        return
    if math.ceil(rows / row_count) > MAX_PARTS:
        await message.answer(
            f"❌ Bu {math.ceil(rows / row_count)} ta fayl bo'ladi — ko'pi bilan {MAX_PARTS} ta.\n"
            f"Kamida {math.ceil(rows / MAX_PARTS)} qatordan bo'ling:"
        )
        return

    job_dir = data["job_dir"]
    base_name = safe_filename(os.path.splitext(data["original_name"])[0], "jadval")
    msg = await message.answer("Fayl bo'laklarga ajratilmoqda va arxivlanmoqda, kuting... ⏳")
    try:
        zip_path, num_chunks = await run_heavy(_split, data["file_path"], job_dir, base_name, row_count)
        await message.answer_document(
            FSInputFile(zip_path),
            caption=f"✅ Tayyor! {rows} qator {num_chunks} ta faylga bo'lindi (har birida ko'pi bilan {row_count} qator, sarlavha bilan).",
        )
        await msg.delete()
    except Exception:
        logging.exception("Smart splitter xatosi")
        await msg.edit_text("❌ Faylni bo'lishda xatolik yuz berdi. Fayl buzilgan bo'lishi mumkin.")
    finally:
        remove(job_dir)
        await state.clear()
