import os
import logging
import traceback
import pandas as pd
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from config import ADMIN_ID

router = Router()


# ════════════════════════════════════════════════════
#  STATES
# ════════════════════════════════════════════════════
class ExcelUtilsStates(StatesGroup):
    # Dublikat tozalash
    dedup_waiting_file    = State()
    dedup_waiting_column  = State()
    # Fayl birlashtirish
    merge_waiting_files   = State()
    merge_confirming      = State()
    # Grafik chizish
    chart_waiting_file    = State()
    chart_waiting_x       = State()
    chart_waiting_y       = State()


# ════════════════════════════════════════════════════
#  MENU
# ════════════════════════════════════════════════════
def excel_utils_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📈 Dublikatlarni tozalash", callback_data="eu_dedup")],
        [InlineKeyboardButton(text="🔗 Excel fayllarni birlashtirish", callback_data="eu_merge")],
        [InlineKeyboardButton(text="📉 Grafik (Chart) yasash", callback_data="eu_chart")],
    ])


@router.message(F.text == "🛠 Excel Yordamchi")
async def excel_utils_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🛠 <b>Excel Yordamchi</b>\n\nQaysi amaldan foydalanasiz?",
        parse_mode="HTML",
        reply_markup=excel_utils_menu()
    )


# ════════════════════════════════════════════════════
#  1. DUBLIKATLARNI TOZALASH
# ════════════════════════════════════════════════════
@router.callback_query(F.data == "eu_dedup")
async def dedup_ask_file(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "📈 <b>Dublikatlarni tozalash</b>\n\n"
        "Iltimos, tahlil qilmoqchi bo'lgan Excel (<b>.xlsx</b>) faylni yuboring.",
        parse_mode="HTML"
    )
    await state.set_state(ExcelUtilsStates.dedup_waiting_file)


@router.message(ExcelUtilsStates.dedup_waiting_file, F.document)
async def dedup_receive_file(message: Message, state: FSMContext, bot: Bot):
    doc = message.document
    if not doc.file_name.lower().endswith(".xlsx"):
        await message.answer("❌ Faqat <b>.xlsx</b> fayl yuboring.", parse_mode="HTML")
        return

    os.makedirs("temp", exist_ok=True)
    file_path = f"temp/dedup_{doc.file_id}_{doc.file_name}"
    await bot.download(doc, destination=file_path)

    try:
        df = pd.read_excel(file_path)
        if df.empty:
            await message.answer("❌ Fayl bo'sh yoki noto'g'ri formatda.")
            await state.clear()
            os.remove(file_path)
            return

        # Ustunlar ro'yxatini chiqarish + "Barcha ustunlar" opsiyasi
        buttons = [[InlineKeyboardButton(
            text="🔁 Barcha ustunlar bo'yicha",
            callback_data="dedup_col:__ALL__"
        )]]
        for col in df.columns:
            safe = str(col)[:60]
            buttons.append([InlineKeyboardButton(
                text=str(col), callback_data=f"dedup_col:{safe}"
            )])

        await state.update_data(file_path=file_path, original_name=doc.file_name)
        await state.set_state(ExcelUtilsStates.dedup_waiting_column)
        await message.answer(
            f"✅ Fayl qabul qilindi (<b>{len(df)}</b> qator).\n\n"
            "Qaysi ustun bo'yicha dublikatlarni qidiramiz?\n"
            "<i>«Barcha ustunlar» — butun qator bir xil bo'lsa o'chiradi</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
    except Exception as e:
        logging.error(f"Dedup fayl o'qish xatosi: {e}")
        await message.answer("❌ Faylni o'qishda xatolik yuz berdi.")
        await state.clear()
        if os.path.exists(file_path): os.remove(file_path)


@router.callback_query(ExcelUtilsStates.dedup_waiting_column, F.data.startswith("dedup_col:"))
async def dedup_process(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    col = callback.data.removeprefix("dedup_col:")
    data = await state.get_data()
    file_path     = data.get("file_path")
    original_name = data.get("original_name", "result")
    base_name, _  = os.path.splitext(original_name)
    out_path      = f"temp/{base_name}_tozalangan.xlsx"

    msg = await callback.message.edit_text("⏳ Dublikatlar aniqlanmoqda...", parse_mode="HTML")

    try:
        df       = pd.read_excel(file_path)
        before   = len(df)
        subset   = None if col == "__ALL__" else [col]
        df_clean = df.drop_duplicates(subset=subset)
        removed  = before - len(df_clean)

        df_clean.to_excel(out_path, index=False)
        result = FSInputFile(out_path, filename=f"{base_name}_tozalangan.xlsx")

        await callback.message.answer_document(
            document=result,
            caption=(
                f"✅ <b>Tozalash yakunlandi!</b>\n\n"
                f"📊 Dastlabki qatorlar: <b>{before}</b>\n"
                f"🗑 O'chirilgan dublikatlar: <b>{removed}</b>\n"
                f"✔️ Qolgan qatorlar: <b>{len(df_clean)}</b>"
            ),
            parse_mode="HTML"
        )
        await msg.delete()

    except Exception as e:
        logging.error(f"Dedup xatosi: {traceback.format_exc()}")
        await msg.edit_text("❌ Dublikatlarni tozalashda xatolik yuz berdi.")
    finally:
        for f in [file_path, out_path]:
            if f and os.path.exists(f):
                try: os.remove(f)
                except: pass
        await state.clear()


# ════════════════════════════════════════════════════
#  2. EXCEL FAYLLARNI BIRLASHTIRISH
# ════════════════════════════════════════════════════
@router.callback_query(F.data == "eu_merge")
async def merge_ask_files(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "🔗 <b>Excel fayllarni birlashtirish</b>\n\n"
        "Birlashtirmoqchi bo'lgan Excel fayllarni ketma-ket yuboring.\n"
        "Hammasi yuklangach, <b>/merge_done</b> deb yozing.",
        parse_mode="HTML"
    )
    await state.update_data(merge_files=[], merge_names=[])
    await state.set_state(ExcelUtilsStates.merge_waiting_files)


@router.message(ExcelUtilsStates.merge_waiting_files, F.document)
async def merge_collect_files(message: Message, state: FSMContext, bot: Bot):
    doc = message.document
    if not doc.file_name.lower().endswith(".xlsx"):
        await message.answer("❌ Faqat <b>.xlsx</b> fayl yuboring.", parse_mode="HTML")
        return

    os.makedirs("temp", exist_ok=True)
    file_path = f"temp/merge_{doc.file_id}_{doc.file_name}"
    await bot.download(doc, destination=file_path)

    data  = await state.get_data()
    files = data.get("merge_files", [])
    names = data.get("merge_names", [])
    files.append(file_path)
    names.append(doc.file_name)
    await state.update_data(merge_files=files, merge_names=names)

    await message.answer(
        f"✅ <b>{doc.file_name}</b> qabul qilindi. "
        f"Jami: <b>{len(files)}</b> ta fayl.\n\n"
        "Yana fayl yuboring yoki birlashtirish uchun <b>/merge_done</b> yozing.",
        parse_mode="HTML"
    )


@router.message(ExcelUtilsStates.merge_waiting_files, F.text == "/merge_done")
async def merge_execute(message: Message, state: FSMContext, bot: Bot):
    data  = await state.get_data()
    files = data.get("merge_files", [])
    names = data.get("merge_names", [])
    out_path = "temp/birlashtirilgan.xlsx"

    if len(files) < 2:
        await message.answer("❌ Birlashtirish uchun kamida <b>2 ta</b> fayl kerak.", parse_mode="HTML")
        return

    msg = await message.answer(f"⏳ <b>{len(files)}</b> ta fayl birlashtirilmoqda...", parse_mode="HTML")

    try:
        dfs = []
        for fp in files:
            df = pd.read_excel(fp)
            dfs.append(df)

        merged = pd.concat(dfs, ignore_index=True)
        merged.to_excel(out_path, index=False)

        result = FSInputFile(out_path, filename="birlashtirilgan.xlsx")
        await message.answer_document(
            document=result,
            caption=(
                f"✅ <b>Birlashtirish yakunlandi!</b>\n\n"
                f"📁 Birlashtirilgan fayllar: <b>{len(files)}</b> ta\n"
                f"📊 Jami qatorlar: <b>{len(merged)}</b> ta"
            ),
            parse_mode="HTML"
        )
        await msg.delete()

    except Exception as e:
        logging.error(f"Merge xatosi: {traceback.format_exc()}")
        await msg.edit_text("❌ Fayllarni birlashtirishda xatolik yuz berdi.")
    finally:
        for f in files + [out_path]:
            if os.path.exists(f):
                try: os.remove(f)
                except: pass
        await state.clear()

# ════════════════════════════════════════════════════
#  3. GRAFIK (CHART) YASASH
# ════════════════════════════════════════════════════
@router.callback_query(F.data == "eu_chart")
async def chart_ask_file(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "📉 <b>Grafik (Chart) yasash</b>\n\n"
        "Excel (<b>.xlsx</b>) faylini yuboring.",
        parse_mode="HTML"
    )
    await state.set_state(ExcelUtilsStates.chart_waiting_file)

@router.message(ExcelUtilsStates.chart_waiting_file, F.document)
async def chart_receive_file(message: Message, state: FSMContext, bot: Bot):
    doc = message.document
    if not doc.file_name.lower().endswith(".xlsx"):
        return await message.answer("❌ Faqat Excel fayl yuboring.")

    os.makedirs("temp", exist_ok=True)
    file_path = f"temp/chart_{doc.file_id}.xlsx"
    await bot.download(doc, destination=file_path)

    try:
        import pandas as pd
        df = pd.read_excel(file_path)
        if df.empty:
            raise Exception("Fayl bo'sh")

        buttons = []
        for col in df.columns:
            buttons.append([InlineKeyboardButton(text=str(col), callback_data=f"chart_x:{str(col)[:50]}")])

        await state.update_data(chart_path=file_path)
        await state.set_state(ExcelUtilsStates.chart_waiting_x)
        await message.answer(
            "📍 <b>X-o'qi (gorizontal)</b> uchun ustunni tanlang:\n"
            "<i>Odatda bu Nomlar, Toifalar yoki Sanalar bo'ladi.</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
    except:
        if os.path.exists(file_path): os.remove(file_path)
        await message.answer("❌ Faylni o'qib bo'lmadi.")
        await state.clear()

@router.callback_query(ExcelUtilsStates.chart_waiting_x, F.data.startswith("chart_x:"))
async def chart_select_x(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    x_col = callback.data.removeprefix("chart_x:")
    await state.update_data(chart_x=x_col)

    data = await state.get_data()
    file_path = data.get("chart_path")
    
    try:
        import pandas as pd
        df = pd.read_excel(file_path)
        # Raqamli ustunlarni topish (Y-o'qi faqat raqam bo'lishi kerak)
        num_cols = df.select_dtypes(include=['number']).columns
        if len(num_cols) == 0:
            await callback.message.edit_text("❌ Faylda raqamli ustun topilmadi (grafik chizish uchun raqamlar kerak).")
            await state.clear()
            return

        buttons = []
        for col in num_cols:
            buttons.append([InlineKeyboardButton(text=str(col), callback_data=f"chart_y:{str(col)[:50]}")])

        await state.set_state(ExcelUtilsStates.chart_waiting_y)
        await callback.message.edit_text(
            f"✅ X-o'qi: <b>{x_col}</b>\n\n"
            "📈 <b>Y-o'qi (vertikal)</b> uchun ustunni tanlang:\n"
            "<i>Bu ustun albatta raqamlardan iborat bo'lishi shart!</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
    except:
        await callback.message.edit_text("❌ Xatolik yuz berdi.")
        await state.clear()

@router.callback_query(ExcelUtilsStates.chart_waiting_y, F.data.startswith("chart_y:"))
async def chart_select_y(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    y_col = callback.data.removeprefix("chart_y:")
    data = await state.get_data()
    x_col = data.get("chart_x")
    file_path = data.get("chart_path")
    
    msg = await callback.message.edit_text("⏳ Grafik chizilmoqda...", parse_mode="HTML")
    
    try:
        import matplotlib.pyplot as plt
        import matplotlib
        import pandas as pd
        matplotlib.use('Agg') # GUI bo'lmagan muhit uchun
        
        df = pd.read_excel(file_path)
        
        # Grafik chizish
        plt.figure(figsize=(10, 6))
        # Gruppalash (agar bir xil X nomlar bo'lsa, ularni qo'shish)
        plot_data = df.groupby(x_col)[y_col].sum().sort_values(ascending=False).head(20)
        
        plot_data.plot(kind='bar', color='skyblue', edgecolor='black')
        plt.title(f"{x_col} bo'yicha {y_col} (Top 20)")
        plt.xlabel(x_col)
        plt.ylabel(y_col)
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        
        img_path = f"temp/plot_{callback.from_user.id}.png"
        plt.savefig(img_path)
        plt.close()
        
        photo = FSInputFile(img_path)
        await callback.message.answer_photo(
            photo=photo,
            caption=f"📈 <b>Grafik tayyor!</b>\n\n📌 X-o'qi: {x_col}\n📊 Y-o'qi: {y_col}",
            parse_mode="HTML"
        )
        await msg.delete()
        if os.path.exists(img_path): os.remove(img_path)
    except Exception as e:
        import traceback
        logging.error(f"Chart xatosi: {traceback.format_exc()}")
        await msg.edit_text("❌ Grafik chizishda xatolik yuz berdi.")
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        await state.clear()

