import os
import logging
import pandas as pd
from aiogram import Router, F, Bot
from aiogram.types import Message, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

router = Router()

class SearchDataStates(StatesGroup):
    waiting_for_file = State()
    waiting_for_query = State()

@router.message(F.text == "🔍 Ma'lumot qidirish")
async def start_search(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Qidirish amalga oshiriladigan Excel (.xlsx yoki .xls) faylni yuboring."
    )
    await state.set_state(SearchDataStates.waiting_for_file)

@router.message(SearchDataStates.waiting_for_file, F.document)
async def process_search_file(message: Message, state: FSMContext, bot: Bot):
    document = message.document
    if not (document.file_name.endswith('.xlsx') or document.file_name.endswith('.xls')):
        await message.answer("Iltimos, faqat .xlsx yoki .xls formatidagi fayl yuboring.")
        return

    os.makedirs('temp', exist_ok=True)
    file_path = f"temp/search_{document.file_id}_{document.file_name}"
    await bot.download(document, destination=file_path)

    await state.update_data(file_path=file_path, original_name=document.file_name)
    await message.answer(
        "Fayl qabul qilindi! Endi qidirmoqchi bo'lgan so'z yoki raqamni kiriting:"
    )
    await state.set_state(SearchDataStates.waiting_for_query)

@router.message(SearchDataStates.waiting_for_query, F.text)
async def process_search_query(message: Message, state: FSMContext):
    query = message.text.strip()
    data = await state.get_data()
    file_path = data['file_path']
    original_name = data['original_name']
    base_name, ext = os.path.splitext(original_name)

    msg = await message.answer(f"🔍 <b>{query}</b> so'zi qidirilmoqda...", parse_mode="HTML")

    result_path = None
    try:
        df = pd.read_excel(file_path)

        if df.empty:
            await msg.edit_text("Fayl bo'sh, hech qanday ma'lumot topilmadi.")
            return

        # Barcha ustunlar bo'ylab katta-kichik harfga e'tibor bermay qidirish
        mask = df.astype(str).apply(
            lambda col: col.str.contains(query, case=False, na=False)
        ).any(axis=1)

        result_df = df[mask]
        found_count = len(result_df)

        if found_count == 0:
            await msg.edit_text(
                f"❌ <b>{query}</b> so'zi bo'yicha hech narsa topilmadi.\n\n"
                "Boshqa so'z bilan qaytadan urinib ko'ring:",
                parse_mode="HTML"
            )
            # Holatni o'zgartirmaymiz — foydalanuvchi yangi query kiritishi mumkin
            return

        # Natijalarni ko'rsatish usulini aniqlash
        if found_count <= 20:
            # 20 ta va undan kam bo'lsa — matn ko'rinishida chiqar
            lines = [f"✅ <b>{found_count}</b> ta natija topildi:\n"]
            for idx, row in result_df.iterrows():
                row_text = " | ".join(
                    [f"<b>{col}:</b> {val}" for col, val in row.items() if str(val) != 'nan']
                )
                lines.append(f"▫️ {row_text}")

            # Telegram xabar limiti (4096 belgi) ga e'tibor berish
            full_text = "\n".join(lines)
            if len(full_text) <= 4096:
                await msg.edit_text(full_text, parse_mode="HTML")
            else:
                # Matn juda uzun bo'lsa — Excel fayl sifatida yuborish
                await msg.edit_text(
                    f"✅ <b>{found_count}</b> ta natija topildi. Matn hajmi katta bo'lgani uchun Excel fayl sifatida yuborilmoqda...",
                    parse_mode="HTML"
                )
                result_path = f"temp/qidiruv_{query[:20]}_{base_name}{ext}"
                result_df.to_excel(result_path, index=False)
                result_file = FSInputFile(result_path, filename=f"qidiruv_natijalari{ext}")
                await message.answer_document(
                    document=result_file,
                    caption=f"🔍 <b>{query}</b> so'zi bo'yicha {found_count} ta natija.",
                    parse_mode="HTML"
                )
        else:
            # 20 dan ko'p bo'lsa — Excel fayl sifatida yuborish
            result_path = f"temp/qidiruv_{query[:20]}_{base_name}{ext}"
            result_df.to_excel(result_path, index=False)
            result_file = FSInputFile(result_path, filename=f"qidiruv_natijalari{ext}")
            await msg.edit_text(
                f"✅ <b>{found_count}</b> ta natija topildi. Excel fayl sifatida yuborilmoqda...",
                parse_mode="HTML"
            )
            await message.answer_document(
                document=result_file,
                caption=f"🔍 <b>{query}</b> so'zi bo'yicha {found_count} ta natija.",
                parse_mode="HTML"
            )

        await message.answer(
            "Yana boshqa so'z qidirmoqchimisiz? Yangi so'zni yuboring yoki bosh menyudan boshqa bo'limni tanlang."
        )

    except Exception as e:
        logging.error(f"Qidirishda xatolik: {e}")
        await msg.edit_text("Xatolik yuz berdi. Fayl formati noto'g'ri bo'lishi mumkin.")
        await state.clear()
    finally:
        # Fayllarni tozalash
        for path in [file_path, result_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception as ex:
                    logging.error(f"Faylni o'chirishda xatolik: {path} - {ex}")

        # Faqat xato bo'lmagan holda state'ni query bosqichida ushlab turamiz
        # Foydalanuvchi yangi query yubora olishi uchun
        await state.clear()
