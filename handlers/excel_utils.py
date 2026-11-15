"""
🛠 Excel yordamchi: dublikatlarni tozalash, fayllarni birlashtirish, grafik chizish.
"""
import asyncio
import logging
import os

import pandas as pd
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from services.converter_service import run_heavy
from services.excel_common import (
    is_excel, size_error, read_table, column_keyboard, column_by_index,
    too_many_columns_note, esc,
)
from services.tempfiles import new_job_dir, remove, safe_filename

router = Router()

MAX_MERGE_FILES = 20
CHART_TOP = 20

_user_locks: dict[int, asyncio.Lock] = {}


def _lock(user_id: int) -> asyncio.Lock:
    return _user_locks.setdefault(user_id, asyncio.Lock())


class ExcelUtilsStates(StatesGroup):
    dedup_waiting_file = State()
    dedup_waiting_column = State()
    merge_waiting_files = State()
    chart_waiting_file = State()
    chart_waiting_x = State()
    chart_waiting_y = State()


def excel_utils_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📈 Dublikatlarni tozalash", callback_data="eu_dedup")],
        [InlineKeyboardButton(text="🔗 Excel fayllarni birlashtirish", callback_data="eu_merge")],
        [InlineKeyboardButton(text="📉 Grafik (Chart) yasash", callback_data="eu_chart")],
    ])


@router.message(F.text == "🛠 Excel Yordamchi")
async def excel_utils_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🛠 <b>Excel Yordamchi</b>\n\nQaysi amaldan foydalanasiz?",
                         parse_mode="HTML", reply_markup=excel_utils_menu())


async def _download_excel(message: Message, bot: Bot, state: FSMContext, prefix: str):
    """Faylni tekshiradi, yangi ish papkasiga yuklaydi va o'qiydi. Muammo bo'lsa (None, None, None)."""
    doc = message.document
    if not is_excel(doc.file_name):
        await message.answer("❌ Faqat Excel (<b>.xlsx</b> yoki <b>.xls</b>) fayl yuboring.", parse_mode="HTML")
        return None, None, None
    if error := size_error(doc.file_size):
        await message.answer(error)
        return None, None, None
    remove((await state.get_data()).get("job_dir"))
    job_dir = new_job_dir(prefix)
    path = os.path.join(job_dir, "input" + os.path.splitext(doc.file_name)[1].lower())
    await bot.download(doc, destination=path)
    try:
        df = await run_heavy(read_table, path)
    except Exception:
        logging.exception(f"{prefix}: faylni o'qib bo'lmadi")
        remove(job_dir)
        await message.answer("❌ Faylni o'qib bo'lmadi. Fayl buzilgan yoki format noto'g'ri bo'lishi mumkin.")
        await state.clear()
        return None, None, None
    if df.empty:
        remove(job_dir)
        await message.answer("❌ Fayl bo'sh yoki noto'g'ri formatda.")
        await state.clear()
        return None, None, None
    return job_dir, path, df


# ════════════════════════════════════════════════════
#  1. DUBLIKATLARNI TOZALASH
# ════════════════════════════════════════════════════
@router.callback_query(F.data == "eu_dedup")
async def dedup_ask_file(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "📈 <b>Dublikatlarni tozalash</b>\n\nIltimos, Excel (<b>.xlsx</b> yoki <b>.xls</b>) faylni yuboring.",
        parse_mode="HTML",
    )
    await state.set_state(ExcelUtilsStates.dedup_waiting_file)


@router.message(ExcelUtilsStates.dedup_waiting_file, F.document)
async def dedup_receive_file(message: Message, state: FSMContext, bot: Bot):
    job_dir, path, df = await _download_excel(message, bot, state, "xldedup")
    if df is None:
        return
    all_button = InlineKeyboardButton(text="🔁 Barcha ustunlar bo'yicha", callback_data="dedup_col:all")
    await state.update_data(job_dir=job_dir, file_path=path, original_name=message.document.file_name)
    await state.set_state(ExcelUtilsStates.dedup_waiting_column)
    await message.answer(
        f"✅ Fayl qabul qilindi (<b>{len(df)}</b> qator).\n\n"
        "Qaysi ustun bo'yicha dublikatlarni qidiramiz?\n"
        "<i>«Barcha ustunlar» — butun qator bir xil bo'lsa o'chiradi</i>" + too_many_columns_note(df.columns),
        parse_mode="HTML",
        reply_markup=column_keyboard(df.columns, "dedup_col", extra_first=[all_button]),
    )


def _dedup(file_path: str, out_path: str, column_index: int | None):
    df = read_table(file_path)
    before = len(df)
    column = None if column_index is None else df.columns[column_index]
    clean = df.drop_duplicates(subset=None if column is None else [column])
    clean.to_excel(out_path, index=False)
    return before, before - len(clean), len(clean), column


@router.callback_query(ExcelUtilsStates.dedup_waiting_column, F.data.startswith("dedup_col:"))
async def dedup_process(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    job_dir, file_path = data.get("job_dir"), data.get("file_path")
    choice = callback.data.split(":", 1)[1]
    column_index = None if choice == "all" else int(choice)
    await state.clear()

    stem = safe_filename(os.path.splitext(data.get("original_name", ""))[0], "jadval")
    out_path = os.path.join(job_dir, f"{stem}_tozalangan.xlsx")
    msg = await callback.message.edit_text("⏳ Dublikatlar aniqlanmoqda...")
    try:
        before, removed, left, column = await run_heavy(_dedup, file_path, out_path, column_index)
        by = "barcha ustunlar" if column is None else f"«{esc(column)}» ustuni"
        await callback.message.answer_document(
            FSInputFile(out_path),
            caption=(
                f"✅ <b>Tozalash yakunlandi!</b> ({by} bo'yicha)\n\n"
                f"📊 Dastlabki qatorlar: <b>{before}</b>\n"
                f"🗑 O'chirilgan dublikatlar: <b>{removed}</b>\n"
                f"✔️ Qolgan qatorlar: <b>{left}</b>"
            ),
            parse_mode="HTML",
        )
        await msg.delete()
    except Exception:
        logging.exception("Dedup xatosi")
        await msg.edit_text("❌ Dublikatlarni tozalashda xatolik yuz berdi.")
    finally:
        remove(job_dir)


# ════════════════════════════════════════════════════
#  2. EXCEL FAYLLARNI BIRLASHTIRISH
# ════════════════════════════════════════════════════
def _merge_keyboard(count: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ Birlashtirish ({count} ta fayl)", callback_data="eu_merge_done")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="eu_merge_cancel")],
    ])


@router.callback_query(F.data == "eu_merge")
async def merge_ask_files(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    remove((await state.get_data()).get("job_dir"))
    await state.set_state(ExcelUtilsStates.merge_waiting_files)
    await state.update_data(merge_files=[], job_dir=new_job_dir("xlmerge"))
    await callback.message.edit_text(
        "🔗 <b>Excel fayllarni birlashtirish</b>\n\n"
        f"Birlashtirmoqchi bo'lgan Excel fayllarni ketma-ket yuboring (ko'pi bilan {MAX_MERGE_FILES} ta).\n"
        "Bir xil nomli ustunlar ustma-ust qo'shiladi.\n\n"
        "Hammasi yuklangach, <b>✅ Birlashtirish</b> tugmasini bosing yoki <b>/merge_done</b> yozing.",
        parse_mode="HTML",
    )


@router.message(ExcelUtilsStates.merge_waiting_files, F.document)
async def merge_collect_files(message: Message, state: FSMContext, bot: Bot):
    doc = message.document
    if not is_excel(doc.file_name):
        await message.answer("❌ Faqat Excel (<b>.xlsx</b> yoki <b>.xls</b>) fayl yuboring.", parse_mode="HTML")
        return
    if error := size_error(doc.file_size):
        await message.answer(error)
        return
    async with _lock(message.from_user.id):
        if await state.get_state() != ExcelUtilsStates.merge_waiting_files.state:
            return
        data = await state.get_data()
        files = list(data.get("merge_files", []))
        if len(files) >= MAX_MERGE_FILES:
            await message.answer(f"⚠️ Ko'pi bilan {MAX_MERGE_FILES} ta fayl. «✅ Birlashtirish» ni bosing.")
            return
        path = os.path.join(data["job_dir"], f"{len(files) + 1:03d}{os.path.splitext(doc.file_name)[1].lower()}")
        await bot.download(doc, destination=path)
        files.append(path)
        await state.update_data(merge_files=files)
        await message.answer(
            f"✅ <b>{esc(doc.file_name)}</b> qabul qilindi. Jami: <b>{len(files)}</b> ta fayl.",
            parse_mode="HTML",
            reply_markup=_merge_keyboard(len(files)),
        )


@router.callback_query(F.data == "eu_merge_cancel")
async def merge_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Bekor qilindi")
    async with _lock(callback.from_user.id):
        remove((await state.get_data()).get("job_dir"))
        await state.clear()
    await callback.message.edit_text("❌ Bekor qilindi.")


def _merge(files: list[str], out_path: str) -> int:
    merged = pd.concat([read_table(fp) for fp in files], ignore_index=True)
    merged.to_excel(out_path, index=False)
    return len(merged)


@router.message(ExcelUtilsStates.merge_waiting_files, F.text == "/merge_done")
@router.callback_query(F.data == "eu_merge_done")
async def merge_execute(event: Message | CallbackQuery, state: FSMContext):
    message = event.message if isinstance(event, CallbackQuery) else event
    if isinstance(event, CallbackQuery):
        await event.answer()
    async with _lock(event.from_user.id):
        if await state.get_state() != ExcelUtilsStates.merge_waiting_files.state:
            await message.answer("Bu sessiya tugagan. Qaytadan «🔗 Birlashtirish» ni tanlang.")
            return
        data = await state.get_data()
        files, job_dir = data.get("merge_files", []), data.get("job_dir")
        if len(files) < 2:
            await message.answer("❌ Birlashtirish uchun kamida <b>2 ta</b> fayl kerak.", parse_mode="HTML")
            return
        await state.clear()

    out_path = os.path.join(job_dir, "birlashtirilgan.xlsx")
    msg = await message.answer(f"⏳ <b>{len(files)}</b> ta fayl birlashtirilmoqda...", parse_mode="HTML")
    try:
        total = await run_heavy(_merge, files, out_path)
        await message.answer_document(
            FSInputFile(out_path),
            caption=(
                f"✅ <b>Birlashtirish yakunlandi!</b>\n\n"
                f"📁 Birlashtirilgan fayllar: <b>{len(files)}</b> ta\n"
                f"📊 Jami qatorlar: <b>{total}</b> ta"
            ),
            parse_mode="HTML",
        )
        await msg.delete()
    except Exception:
        logging.exception("Merge xatosi")
        await msg.edit_text("❌ Fayllarni birlashtirishda xatolik yuz berdi. Fayllardan biri buzilgan bo'lishi mumkin.")
    finally:
        remove(job_dir)


# ════════════════════════════════════════════════════
#  3. GRAFIK (CHART) YASASH
# ════════════════════════════════════════════════════
@router.callback_query(F.data == "eu_chart")
async def chart_ask_file(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "📉 <b>Grafik (Chart) yasash</b>\n\nExcel (<b>.xlsx</b> yoki <b>.xls</b>) faylini yuboring.",
        parse_mode="HTML",
    )
    await state.set_state(ExcelUtilsStates.chart_waiting_file)


@router.message(ExcelUtilsStates.chart_waiting_file, F.document)
async def chart_receive_file(message: Message, state: FSMContext, bot: Bot):
    job_dir, path, df = await _download_excel(message, bot, state, "xlchart")
    if df is None:
        return
    if len(df.select_dtypes(include="number").columns) == 0:
        remove(job_dir)
        await message.answer("❌ Faylda raqamli ustun topilmadi (grafik chizish uchun raqamlar kerak).")
        await state.clear()
        return
    await state.update_data(job_dir=job_dir, chart_path=path)
    await state.set_state(ExcelUtilsStates.chart_waiting_x)
    await message.answer(
        "📍 <b>X-o'qi (gorizontal)</b> uchun ustunni tanlang:\n"
        "<i>Odatda bu nomlar, toifalar yoki sanalar bo'ladi.</i>" + too_many_columns_note(df.columns),
        parse_mode="HTML",
        reply_markup=column_keyboard(df.columns, "chart_x"),
    )


@router.callback_query(ExcelUtilsStates.chart_waiting_x, F.data.startswith("chart_x:"))
async def chart_select_x(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    df = await run_heavy(read_table, data["chart_path"])
    x_col = column_by_index(df.columns, callback.data)
    if x_col is None:
        return
    numeric = [c for c in df.select_dtypes(include="number").columns if c != x_col]
    if not numeric:
        await callback.message.edit_text("❌ X-o'qidan boshqa raqamli ustun yo'q. Boshqa ustunni tanlang yoki faylni tekshiring.")
        remove(data.get("job_dir"))
        await state.clear()
        return
    # Y tugmalari ham ustunning umumiy jadvaldagi tartib raqami bilan
    all_cols = list(df.columns)
    buttons = [[InlineKeyboardButton(text=str(c)[:40], callback_data=f"chart_y:{all_cols.index(c)}")] for c in numeric[:40]]
    await state.update_data(chart_x=all_cols.index(x_col))
    await state.set_state(ExcelUtilsStates.chart_waiting_y)
    await callback.message.edit_text(
        f"✅ X-o'qi: <b>{esc(x_col)}</b>\n\n📈 <b>Y-o'qi (vertikal)</b> uchun raqamli ustunni tanlang:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


def _draw_chart(file_path: str, x_index: int, y_index: int, img_path: str):
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib.figure import Figure

    df = read_table(file_path)
    x_col, y_col = df.columns[x_index], df.columns[y_index]
    grouped = df.groupby(df[x_col].astype(str))[y_col].sum()
    total_groups = len(grouped)
    plot_data = grouped.sort_values(ascending=False).head(CHART_TOP)

    fig = Figure(figsize=(10, 6), dpi=120)
    ax = fig.subplots()
    ax.bar(plot_data.index, plot_data.values, color="#4C8BF5", edgecolor="#1F3B73")
    ax.set_title(f"{x_col} bo'yicha {y_col}" + (f" (eng katta {CHART_TOP} ta)" if total_groups > CHART_TOP else ""))
    ax.set_xlabel(str(x_col))
    ax.set_ylabel(str(y_col))
    ax.tick_params(axis="x", labelrotation=45)
    for label in ax.get_xticklabels():
        label.set_horizontalalignment("right")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(img_path)
    return x_col, y_col, total_groups


@router.callback_query(ExcelUtilsStates.chart_waiting_y, F.data.startswith("chart_y:"))
async def chart_select_y(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    job_dir, file_path, x_index = data.get("job_dir"), data.get("chart_path"), data.get("chart_x")
    try:
        y_index = int(callback.data.split(":", 1)[1])
    except ValueError:
        return
    await state.clear()

    img_path = os.path.join(job_dir, "grafik.png")
    msg = await callback.message.edit_text("⏳ Grafik chizilmoqda...")
    try:
        x_col, y_col, groups = await run_heavy(_draw_chart, file_path, x_index, y_index, img_path)
        note = f"\n<i>{groups} ta guruhdan eng kattalari ko'rsatildi.</i>" if groups > CHART_TOP else ""
        await callback.message.answer_photo(
            FSInputFile(img_path),
            caption=f"📈 <b>Grafik tayyor!</b>\n\n📌 X-o'qi: {esc(x_col)}\n📊 Y-o'qi: {esc(y_col)} (yig'indi){note}",
            parse_mode="HTML",
        )
        await msg.delete()
    except Exception:
        logging.exception("Chart xatosi")
        await msg.edit_text("❌ Grafik chizishda xatolik yuz berdi.")
    finally:
        remove(job_dir)
