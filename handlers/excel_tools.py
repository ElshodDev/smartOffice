import os
import logging
import pandas as pd
from aiogram import Router, F, Bot
from aiogram.types import Message, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

router = Router()

class ExcelSplitterStates(StatesGroup):
    waiting_for_file = State()
    waiting_for_range = State()

@router.message(F.text == "✂️ Excel qirqish")
async def start_excel_split(message: Message, state: FSMContext):
    await message.answer("Iltimos, qirqmoqchi bo'lgan Excel (.xlsx yoki .xls) faylingizni yuboring.")
    await state.set_state(ExcelSplitterStates.waiting_for_file)

@router.message(ExcelSplitterStates.waiting_for_file, F.document)
async def process_excel_file(message: Message, state: FSMContext, bot: Bot):
    document = message.document
    if not (document.file_name.endswith('.xlsx') or document.file_name.endswith('.xls')):
        await message.answer("Iltimos, faqat .xlsx yoki .xls formatidagi fayl yuboring.")
        return

    os.makedirs('temp', exist_ok=True)
    file_path = f"temp/{document.file_id}_{document.file_name}"
    
    # Faylni yuklab olish
    await bot.download(document, destination=file_path)
    
    await state.update_data(file_path=file_path, original_name=document.file_name)
    await message.answer("Fayl qabul qilindi. Endi qirqib olinadigan qatorlar oraliqni kiriting (masalan: 1-50):")
    await state.set_state(ExcelSplitterStates.waiting_for_range)

@router.message(ExcelSplitterStates.waiting_for_range, F.text)
async def process_excel_range(message: Message, state: FSMContext):
    range_text = message.text.strip()
    
    try:
        start_str, end_str = range_text.split('-')
        start_row = int(start_str.strip())
        end_row = int(end_str.strip())
        
        if start_row <= 0 or end_row < start_row:
            raise ValueError
    except ValueError:
        await message.answer("Noto'g'ri format. Iltimos, diapazonni to'g'ri kiriting (masalan: 1-50):")
        return
    
    data = await state.get_data()
    file_path = data['file_path']
    original_name = data['original_name']
    
    msg = await message.answer("Fayl qirqilmoqda, kuting... ⏳")
    
    try:
        # Pandas orqali o'qish
        df = pd.read_excel(file_path)
        
        # Qatorlarni qirqish (iloc 0-dan boshlanadi, foydalanuvchi kiritgan 1-qator -> index 0)
        sliced_df = df.iloc[start_row - 1 : end_row]
        
        # Yangi fayl nomi va yo'li
        output_file_name = f"qirqilgan_{start_row}_{end_row}_{original_name}"
        output_file_path = f"temp/{output_file_name}"
        
        # Excelga yozish
        sliced_df.to_excel(output_file_path, index=False)
        
        # Faylni yuborish
        result_file = FSInputFile(output_file_path, filename=output_file_name)
        await message.answer_document(
            document=result_file, 
            caption=f"Tayyor! {start_row} dan {end_row} gacha bo'lgan qatorlar qirqib olindi."
        )
        
        # Vaqtinchalik fayllarni o'chirish
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            if os.path.exists(output_file_path):
                os.remove(output_file_path)
        except Exception as e:
            logging.error(f"Fayllarni o'chirishda xatolik yuz berdi: {e}")
            
    except Exception as e:
        logging.error(f"Excelni qirqishda xato: {e}")
        await message.answer("Xatolik yuz berdi. Fayl formati noto'g'ri yoki diapazon fayldagi qatorlar sonidan ko'p bo'lishi mumkin.")
    finally:
        await msg.delete()
        await state.clear()
