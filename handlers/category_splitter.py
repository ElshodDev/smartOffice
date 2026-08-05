import os
import zipfile
import logging
import traceback
import pandas as pd
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from config import ADMIN_ID

router = Router()


class CategorySplitterStates(StatesGroup):
    waiting_for_excel  = State()
    waiting_for_column = State()


@router.message(F.text == "📑 Toifa bo'yicha bo'lish")
async def start_category_splitter(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "📑 <b>Toifa bo'yicha bo'lish</b>\n\n"
        "Iltimos, bo'laklarga ajratmoqchi bo'lgan Excel (<b>.xlsx</b>) faylni yuboring.",
        parse_mode="HTML"
    )
    await state.set_state(CategorySplitterStates.waiting_for_excel)


@router.message(CategorySplitterStates.waiting_for_excel, F.document)
async def receive_excel(message: Message, state: FSMContext, bot: Bot):
    doc = message.document

    if not doc.file_name.lower().endswith(".xlsx"):
        await message.answer("❌ Iltimos, faqat <b>.xlsx</b> formatidagi Excel fayl yuboring.", parse_mode="HTML")
        return

    os.makedirs("temp", exist_ok=True)
    file_path = f"temp/cat_{doc.file_id}_{doc.file_name}"

    await bot.download(doc, destination=file_path)

    try:
        df = pd.read_excel(file_path)
        if df.empty or len(df.columns) == 0:
            await message.answer("❌ Fayl bo'sh yoki noto'g'ri formatda.")
            await state.clear()
            if os.path.exists(file_path):
                os.remove(file_path)
            return

        # Ustun nomlaridan Inline Keyboard yasash
        buttons = []
        for col in df.columns:
            safe_col = str(col)[:64]          # Telegram callback_data limit
            buttons.append(
                [InlineKeyboardButton(text=str(col), callback_data=f"catcol:{safe_col}")]
            )

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await state.update_data(file_path=file_path, original_name=doc.file_name)
        await state.set_state(CategorySplitterStates.waiting_for_column)

        await message.answer(
            f"✅ Fayl qabul qilindi! (<b>{len(df)}</b> qator, <b>{len(df.columns)}</b> ustun)\n\n"
            "📌 Qaysi <b>ustun</b> bo'yicha ajratmoqchisiz?",
            parse_mode="HTML",
            reply_markup=keyboard
        )

    except Exception as e:
        logging.error(f"Category splitter — fayl o'qishda xato: {e}")
        await message.answer("❌ Faylni o'qishda xatolik. Fayl buzilgan yoki format noto'g'ri bo'lishi mumkin.")
        await state.clear()
        if os.path.exists(file_path):
            os.remove(file_path)


@router.callback_query(CategorySplitterStates.waiting_for_column, F.data.startswith("catcol:"))
async def split_by_column(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()

    selected_column = callback.data.removeprefix("catcol:")
    data = await state.get_data()
    file_path    = data.get("file_path")
    original_name = data.get("original_name", "result")
    base_name    = os.path.splitext(original_name)[0]

    if not file_path or not os.path.exists(file_path):
        await callback.message.answer("❌ Fayl topilmadi. Iltimos, amalni boshidan boshlang.")
        await state.clear()
        return

    msg = await callback.message.edit_text(
        f"⏳ <b>«{selected_column}»</b> ustuni bo'yicha ajratilmoqda...",
        parse_mode="HTML"
    )

    created_files = []
    zip_path = f"temp/{base_name}_by_{selected_column}.zip"

    try:
        df = pd.read_excel(file_path)

        # Ustun mavjudligini tekshirish (foydalanuvchi yoki fayl o'zgargan bo'lsa)
        if selected_column not in df.columns:
            await msg.edit_text(f"❌ <b>«{selected_column}»</b> ustuni faylda topilmadi.", parse_mode="HTML")
            await state.clear()
            return

        groups = list(df.groupby(selected_column))
        total_groups = len(groups)

        if total_groups == 0:
            await msg.edit_text("❌ Tanlangan ustunda guruhlanadigan ma'lumot topilmadi.")
            await state.clear()
            return

        # Har bir guruh uchun alohida .xlsx fayl yaratish
        for category, group_df in groups:
            # Fayl nomidan xavfli belgilarni tozalash
            safe_cat = str(category).replace("/", "-").replace("\\", "-").replace(":", "-")[:50]
            chunk_path = f"temp/{base_name}_{safe_cat}.xlsx"
            group_df.to_excel(chunk_path, index=False)
            created_files.append(chunk_path)

        # Barcha fayllarni ZIP ga yig'ish
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for f in created_files:
                zipf.write(f, arcname=os.path.basename(f))

        # Natijani foydalanuvchiga yuborish
        result_file = FSInputFile(
            zip_path,
            filename=f"{base_name}_by_{selected_column}.zip"
        )
        await callback.message.answer_document(
            document=result_file,
            caption=(
                f"✅ <b>Tayyor!</b>\n\n"
                f"📊 Ustun: <b>{selected_column}</b>\n"
                f"📁 Yaratilgan fayllar: <b>{total_groups} ta</b>\n\n"
                f"Har bir toifa alohida Excel fayl sifatida ZIP ichida."
            ),
            parse_mode="HTML"
        )
        await msg.delete()

    except Exception as e:
        err_trace = traceback.format_exc()
        logging.error(f"Category splitter xatosi: {err_trace}")

        await msg.edit_text(
            "❌ Ajratish jarayonida xatolik yuz berdi. Fayl buzilgan yoki tuzilmasi noto'g'ri bo'lishi mumkin."
        )

        # Adminga xato haqida batafsil xabar
        if ADMIN_ID:
            try:
                await bot.send_message(
                    chat_id=int(ADMIN_ID),
                    text=(
                        f"⚠️ <b>Category Splitter xatosi</b>\n\n"
                        f"👤 Foydalanuvchi: <code>{callback.from_user.id}</code>\n"
                        f"📁 Fayl: {original_name}\n"
                        f"📌 Ustun: {selected_column}\n\n"
                        f"<code>{str(e)}</code>"
                    ),
                    parse_mode="HTML"
                )
            except Exception:
                pass

    finally:
        # Avto-tozalash: barcha vaqtinchalik fayllarni o'chirish
        for f in created_files + [file_path, zip_path]:
            if f and os.path.exists(f):
                try:
                    os.remove(f)
                except Exception as ex:
                    logging.warning(f"Faylni o'chirishda xato: {f} — {ex}")

        await state.clear()
