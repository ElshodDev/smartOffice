import os
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from services.converter_service import ConverterService

router = Router()

class FormatConverterStates(StatesGroup):
    waiting_for_pdf = State()
    waiting_for_image = State()

def get_converter_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(text="📄 PDF ➡️ Word", callback_data="format_pdf2word")
        ],
        [
            InlineKeyboardButton(text="🖼 Rasm ➡️ PDF", callback_data="format_img2pdf")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@router.message(F.text == "🔄 Konvertor")
async def start_converter_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🔄 <b>Format Konvertori</b>\n\nQaysi amallardan birini tanlaysiz?",
        parse_mode="HTML",
        reply_markup=get_converter_menu()
    )

@router.callback_query(F.data == "format_pdf2word")
async def ask_for_pdf(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "📄 <b>PDF dan Word ga o'tkazish</b>\n\nIltimos, .pdf formatidagi faylni yuboring:",
        parse_mode="HTML"
    )
    await state.set_state(FormatConverterStates.waiting_for_pdf)

@router.message(FormatConverterStates.waiting_for_pdf, F.document)
async def process_pdf_to_word(message: Message, state: FSMContext, bot: Bot):
    doc = message.document
    if not doc.file_name.lower().endswith('.pdf'):
        await message.answer("Iltimos, faqat .pdf formatidagi fayl yuboring.")
        return

    os.makedirs('temp', exist_ok=True)
    pdf_path = f"temp/input_{doc.file_id}.pdf"
    docx_path = f"temp/output_{doc.file_id}.docx"
    
    await bot.download(doc, destination=pdf_path)
    msg = await message.answer("Fayl qabul qilindi. Konvertatsiya qilinmoqda, bu fayl hajmiga qarab biroz vaqt olishi mumkin... ⏳")
    
    try:
        success = ConverterService.pdf_to_word(pdf_path, docx_path)
        if success:
            result = FSInputFile(docx_path, filename=doc.file_name.replace('.pdf', '.docx').replace('.PDF', '.docx'))
            await message.answer_document(
                document=result,
                caption="✅ Tayyor! PDF muvaffaqiyatli Word formatiga o'tkazildi."
            )
        else:
            await message.answer("❌ Konvertatsiya vaqtida xatolik yuz berdi. PDF fayl ichida skaner qilingan rasmlar bo'lsa yoki fayl buzilgan bo'lsa shunday bo'lishi mumkin.")
    except Exception as e:
        await message.answer("❌ Konvertatsiya vaqtida xatolik yuz berdi.")
    finally:
        await msg.delete()
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        if os.path.exists(docx_path):
            os.remove(docx_path)
        await state.clear()

@router.callback_query(F.data == "format_img2pdf")
async def ask_for_image(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "🖼 <b>Rasm dan PDF ga o'tkazish</b>\n\nIltimos, rasmni (Photo ko'rinishida yoki File ko'rinishida) yuboring:",
        parse_mode="HTML"
    )
    await state.set_state(FormatConverterStates.waiting_for_image)

@router.message(FormatConverterStates.waiting_for_image, F.photo | F.document)
async def process_image_to_pdf(message: Message, state: FSMContext, bot: Bot):
    os.makedirs('temp', exist_ok=True)
    
    if message.photo:
        photo = message.photo[-1]
        file_id = photo.file_id
        original_name = f"image_{file_id}.jpg"
    else:
        doc = message.document
        valid_exts = ('.jpg', '.jpeg', '.png', '.bmp')
        if not any(doc.file_name.lower().endswith(ext) for ext in valid_exts):
            await message.answer(f"Iltimos, faqat rasm formatidagi ({', '.join(valid_exts)}) fayl yuboring.")
            return
        file_id = doc.file_id
        original_name = doc.file_name

    img_path = f"temp/input_{file_id}_{original_name}"
    pdf_path = f"temp/output_{file_id}.pdf"
    
    await bot.download(file_id, destination=img_path)
    msg = await message.answer("Rasm qabul qilindi. PDF ga o'tkazilmoqda... ⏳")
    
    try:
        success = ConverterService.img_to_pdf(img_path, pdf_path)
        if success:
            result = FSInputFile(pdf_path, filename=original_name.rsplit('.', 1)[0] + ".pdf")
            await message.answer_document(
                document=result,
                caption="✅ Tayyor! Rasm PDF formatiga o'tkazildi."
            )
        else:
            await message.answer("❌ Konvertatsiya vaqtida xatolik yuz berdi.")
    except Exception as e:
        await message.answer("❌ Konvertatsiya vaqtida xatolik yuz berdi.")
    finally:
        await msg.delete()
        if os.path.exists(img_path):
            os.remove(img_path)
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        await state.clear()
