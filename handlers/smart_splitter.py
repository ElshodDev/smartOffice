import os
import math
import zipfile
import logging
import traceback
import pandas as pd
from aiogram import Router, F, Bot
from aiogram.types import Message, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from config import ADMIN_ID

router = Router()

class SmartSplitterStates(StatesGroup):
    waiting_for_file = State()
    waiting_for_row_count = State()

@router.message(F.text == "📊 Smart Splitter")
async def start_smart_splitter(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Iltimos, bo'laklarga ajratmoqchi bo'lgan Excel (.xlsx) faylingizni yuboring.")
    await state.set_state(SmartSplitterStates.waiting_for_file)

@router.message(SmartSplitterStates.waiting_for_file, F.document)
async def process_splitter_file(message: Message, state: FSMContext, bot: Bot):
    document = message.document
    if not document.file_name.endswith('.xlsx'):
        await message.answer("Iltimos, faqat .xlsx formatidagi Excel fayl yuboring.")
        return

    os.makedirs('temp', exist_ok=True)
    file_path = f"temp/split_target_{document.file_id}_{document.file_name}"
    
    await bot.download(document, destination=file_path)
    
    await state.update_data(file_path=file_path, original_name=document.file_name)
    await message.answer("Fayl qabul qilindi. Har bir bo'lakda nechta qator bo'lishini xohlaysiz? (masalan, 500):")
    await state.set_state(SmartSplitterStates.waiting_for_row_count)

@router.message(SmartSplitterStates.waiting_for_row_count, F.text)
async def process_row_count(message: Message, state: FSMContext, bot: Bot):
    # 1. Kiritilgan ma'lumot butun son ekanligini tekshirish
    try:
        row_count = int(message.text.strip())
        if row_count <= 0:
            raise ValueError("Qatorlar soni musbat bo'lishi kerak")
    except ValueError:
        await message.answer("Iltimos, faqat musbat butun raqam kiriting (masalan, 500):")
        return
        
    data = await state.get_data()
    file_path = data.get('file_path')
    original_name = data.get('original_name')
    
    if not file_path or not os.path.exists(file_path):
        await message.answer("Fayl topilmadi. Iltimos, amalni boshidan boshlang.")
        await state.clear()
        return

    base_name, ext = os.path.splitext(original_name)
    msg = await message.answer("Fayl bo'laklarga ajratilmoqda va arxivlanmoqda, kuting... ⏳")
    
    created_files = []
    zip_filename = f"temp/{base_name}_parts.zip"
    
    # 2. Asosiy mantiq try...except...finally bloki ichida
    try:
        # Pandas yordamida faylni o'qish
        df = pd.read_excel(file_path)
        total_rows = len(df)
        
        if total_rows == 0:
            await msg.edit_text("Faylda ma'lumot topilmadi (bo'sh fayl).")
            return
            
        num_chunks = math.ceil(total_rows / row_count)
        
        # Bo'laklarga ajratish va alohida Excel fayllarga saqlash
        for i in range(num_chunks):
            start_row = i * row_count
            end_row = start_row + row_count
            chunk_df = df.iloc[start_row:end_row]
            
            chunk_name = f"temp/{base_name}_part_{i+1}{ext}"
            chunk_df.to_excel(chunk_name, index=False)
            created_files.append(chunk_name)
            
        # Ularning barchasini ZIP qilish
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in created_files:
                zipf.write(file, arcname=os.path.basename(file))
                
        # Foydalanuvchiga ZIP arxivni yuborish
        result_file = FSInputFile(zip_filename, filename=f"{base_name}_parts.zip")
        await message.answer_document(
            document=result_file, 
            caption=f"✅ Tayyor! Faylingiz {num_chunks} ta bo'lakka ajratildi (har birida maksimum {row_count} qator) va arxivlandi."
        )
        await msg.delete()
        
    except Exception as e:
        error_msg = f"Xatolik: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        logging.error(f"Smart splitter xatosi: {error_msg}")
        
        # Foydalanuvchiga tushunarli xabar
        await msg.edit_text("Faylni bo'lishda xatolik yuz berdi. Bu fayl formati buzilganligi yoki ma'lumotlar bilan bog'liq xato bo'lishi mumkin.")
        
        # Adminga xato haqida xabar yuborish
        if ADMIN_ID:
            try:
                admin_id = int(ADMIN_ID)
                await bot.send_message(
                    chat_id=admin_id,
                    text=f"⚠️ <b>Smart Splitter xatosi</b>\n\nFoydalanuvchi: {message.from_user.id}\nFayl: {original_name}\n\nXato:\n<code>{str(e)}</code>",
                    parse_mode="HTML"
                )
            except Exception as admin_err:
                logging.error(f"Adminga xato haqida xabar yuborishda muammo: {admin_err}")
                
    finally:
        # Avto-tozalash: barcha vaqtinchalik fayllarni o'chirish
        files_to_delete = [file_path, zip_filename] + created_files
        for f in files_to_delete:
            if f and os.path.exists(f):
                try:
                    os.remove(f)
                except Exception as ex:
                    logging.error(f"Vaqtinchalik faylni o'chirishda xatolik yuz berdi: {f} - {ex}")
                    
        # FSM holatini tozalash
        await state.clear()
