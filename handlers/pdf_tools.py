import os
import traceback
import logging
import sys
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from pypdf import PdfReader, PdfWriter

router = Router()

class PdfStates(StatesGroup):
    merge_waiting_files = State()
    lock_waiting_file = State()
    lock_waiting_password = State()
    extract_waiting_file = State()
    extract_waiting_pages = State()
    watermark_waiting_file = State()
    watermark_waiting_text = State()
    docx_waiting_file = State()

def get_pdf_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📎 Birlashtirish", callback_data="pdf_merge")],
        [InlineKeyboardButton(text="🔒 Parol qo'yish", callback_data="pdf_lock")],
        [InlineKeyboardButton(text="✂️ Sahifalarni ajratish", callback_data="pdf_extract")],
        [InlineKeyboardButton(text="©️ Watermark qo'yish", callback_data="pdf_watermark")],
        [InlineKeyboardButton(text="🔄 PDF ➡️ Word", callback_data="pdf_to_docx")],
    ])

@router.message(F.text == "📄 PDF Asboblari")
async def show_pdf_tools(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "📄 <b>PDF Asboblari</b>\n\nQaysi amaldan foydalanasiz?",
        parse_mode="HTML",
        reply_markup=get_pdf_menu()
    )

# ── 1. BIRLASHTIRISH ──
@router.callback_query(F.data == "pdf_merge")
async def pdf_merge_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "📎 <b>PDF Birlashtirish</b>\n\n"
        "Birlashtirmoqchi bo'lgan PDF fayllarni ketma-ket yuboring.\n"
        "Barchasi yuborilgach, <b>/done_pdf</b> yozing.",
        parse_mode="HTML"
    )
    await state.update_data(pdf_files=[])
    await state.set_state(PdfStates.merge_waiting_files)

@router.message(PdfStates.merge_waiting_files, F.document)
async def pdf_merge_collect(message: Message, state: FSMContext, bot: Bot):
    doc = message.document
    if not doc.file_name.lower().endswith(".pdf"):
        await message.answer("❌ Faqat <b>.pdf</b> fayl yuboring.", parse_mode="HTML")
        return
    
    os.makedirs("temp", exist_ok=True)
    path = f"temp/merge_{doc.file_id}.pdf"
    await bot.download(doc, destination=path)
    
    data = await state.get_data()
    files = data.get("pdf_files", [])
    files.append(path)
    await state.update_data(pdf_files=files)
    
    await message.answer(f"✅ Qabul qilindi. Jami fayllar: <b>{len(files)}</b> ta.\n\nTugatish uchun <b>/done_pdf</b> yozing.", parse_mode="HTML")

@router.message(PdfStates.merge_waiting_files, F.text == "/done_pdf")
async def pdf_merge_execute(message: Message, state: FSMContext):
    data = await state.get_data()
    files = data.get("pdf_files", [])
    
    if len(files) < 2:
        await message.answer("❌ Birlashtirish uchun kamida 2 ta PDF kerak.")
        return
    
    msg = await message.answer("⏳ Birlashtirilmoqda...")
    out_path = "temp/merged_result.pdf"
    
    try:
        writer = PdfWriter()
        for f in files:
            reader = PdfReader(f)
            writer.append(reader)
            
        with open(out_path, "wb") as f_out:
            writer.write(f_out)
            
        result = FSInputFile(out_path, filename="birlashtirilgan.pdf")
        await message.answer_document(result, caption="✅ PDF fayllar birlashtirildi!")
        await msg.delete()
    except Exception as e:
        logging.error(f"PDF merge error: {traceback.format_exc()}")
        await msg.edit_text("❌ Xatolik yuz berdi. Ba'zi fayllar buzilgan bo'lishi mumkin.")
    finally:
        for f in files + [out_path]:
            if os.path.exists(f): os.remove(f)
        await state.clear()

# ── 2. PAROL QO'YISH ──
@router.callback_query(F.data == "pdf_lock")
async def pdf_lock_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "🔒 <b>PDF ga parol qo'yish</b>\n\n"
        "Parol o'rnatmoqchi bo'lgan PDF faylni yuboring.",
        parse_mode="HTML"
    )
    await state.set_state(PdfStates.lock_waiting_file)

@router.message(PdfStates.lock_waiting_file, F.document)
async def pdf_lock_file(message: Message, state: FSMContext, bot: Bot):
    doc = message.document
    if not doc.file_name.lower().endswith(".pdf"):
        return await message.answer("❌ Faqat PDF fayl qabul qilinadi.")
        
    os.makedirs("temp", exist_ok=True)
    path = f"temp/lock_{doc.file_id}.pdf"
    await bot.download(doc, destination=path)
    
    await state.update_data(lock_path=path, original_name=doc.file_name)
    await state.set_state(PdfStates.lock_waiting_password)
    await message.answer("✍️ Endi o'rnatmoqchi bo'lgan parolni yozing:")

@router.message(PdfStates.lock_waiting_password, F.text)
async def pdf_lock_execute(message: Message, state: FSMContext):
    password = message.text
    data = await state.get_data()
    in_path = data.get("lock_path")
    original_name = data.get("original_name")
    out_path = f"temp/locked_{original_name}"
    
    msg = await message.answer("⏳ Parol o'rnatilmoqda...")
    try:
        reader = PdfReader(in_path)
        writer = PdfWriter()
        writer.append_pages_from_reader(reader)
        writer.encrypt(password)
        
        with open(out_path, "wb") as f_out:
            writer.write(f_out)
            
        result = FSInputFile(out_path, filename=f"locked_{original_name}")
        await message.answer_document(result, caption=f"✅ Faylga parol o'rnatildi.\n\n🔑 Parol: ||{password}||", parse_mode="MarkdownV2")
        await msg.delete()
    except Exception as e:
        await msg.edit_text("❌ Xatolik yuz berdi.")
    finally:
        for f in [in_path, out_path]:
            if f and os.path.exists(f): os.remove(f)
        await state.clear()
        
# ── 3. SAHIFALARNI QIRQISH ──
@router.callback_query(F.data == "pdf_extract")
async def pdf_extract_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "✂️ <b>Sahifalarni ajratish</b>\n\n"
        "PDF faylni yuboring.",
        parse_mode="HTML"
    )
    await state.set_state(PdfStates.extract_waiting_file)

@router.message(PdfStates.extract_waiting_file, F.document)
async def pdf_extract_file(message: Message, state: FSMContext, bot: Bot):
    doc = message.document
    if not doc.file_name.lower().endswith(".pdf"):
        return await message.answer("❌ Faqat PDF!")
        
    os.makedirs("temp", exist_ok=True)
    path = f"temp/ext_{doc.file_id}.pdf"
    await bot.download(doc, destination=path)
    
    try:
        reader = PdfReader(path)
        total_pages = len(reader.pages)
        await state.update_data(ext_path=path, total=total_pages)
        await state.set_state(PdfStates.extract_waiting_pages)
        await message.answer(
            f"Faylda <b>{total_pages}</b> ta sahifa bor.\n\n"
            "Qaysi sahifalarni ajratib olamiz? (Masalan: 1,3,5 yoki 1-5)",
            parse_mode="HTML"
        )
    except:
        if os.path.exists(path): os.remove(path)
        await message.answer("❌ Faylni o'qib bo'lmadi.")
        await state.clear()

@router.message(PdfStates.extract_waiting_pages, F.text)
async def pdf_extract_execute(message: Message, state: FSMContext):
    text = message.text.strip()
    data = await state.get_data()
    in_path = data.get("ext_path")
    total = data.get("total")
    out_path = "temp/extracted.pdf"
    
    pages_to_extract = set()
    try:
        for part in text.split(","):
            if "-" in part:
                start, end = map(int, part.split("-"))
                pages_to_extract.update(range(start, end + 1))
            else:
                pages_to_extract.add(int(part))
    except:
        return await message.answer("❌ Noto'g'ri format. Masalan: 1,3,5 yoki 1-5 deb yozing.")
        
    msg = await message.answer("⏳ Ajratilmoqda...")
    try:
        reader = PdfReader(in_path)
        writer = PdfWriter()
        
        for p in sorted(pages_to_extract):
            if 1 <= p <= total:
                writer.add_page(reader.pages[p - 1])
                
        if len(writer.pages) == 0:
            return await msg.edit_text("❌ Hech qaysi sahifa topilmadi (raqamlar fayl hajmidan katta bo'lishi mumkin).")
            
        with open(out_path, "wb") as f_out:
            writer.write(f_out)
            
        result = FSInputFile(out_path, filename="ajratilgan_sahifalar.pdf")
        await message.answer_document(result, caption=f"✅ Ajratib olindi: {len(writer.pages)} sahifa.")
        await msg.delete()
    except Exception as e:
        await msg.edit_text("❌ Xatolik yuz berdi.")
    finally:
        for f in [in_path, out_path]:
            if f and os.path.exists(f): os.remove(f)
        await state.clear()

# ── 4. WATERMARK QO'YISH ──
@router.callback_query(F.data == "pdf_watermark")
async def pdf_watermark_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "©️ <b>Watermark qo'yish</b>\n\nPDF faylni yuboring.",
        parse_mode="HTML"
    )
    await state.set_state(PdfStates.watermark_waiting_file)

@router.message(PdfStates.watermark_waiting_file, F.document)
async def pdf_watermark_file(message: Message, state: FSMContext, bot: Bot):
    doc = message.document
    if not doc.file_name.lower().endswith(".pdf"):
        return await message.answer("❌ Faqat PDF!")
        
    os.makedirs("temp", exist_ok=True)
    path = f"temp/wm_{doc.file_id}.pdf"
    await bot.download(doc, destination=path)
    
    await state.update_data(wm_path=path, original_name=doc.file_name)
    await state.set_state(PdfStates.watermark_waiting_text)
    await message.answer("Endi Watermark matnini kiriting (Masalan: MAXFIY):")

@router.message(PdfStates.watermark_waiting_text, F.text)
async def pdf_watermark_execute(message: Message, state: FSMContext):
    wm_text = message.text.strip()
    data = await state.get_data()
    in_path = data.get("wm_path")
    original_name = data.get("original_name")
    
    wm_pdf = "temp/watermark_layer.pdf"
    out_path = f"temp/watermarked_{original_name}"
    msg = await message.answer("⏳ Watermark qo'yilmoqda...")
    
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from pypdf import PdfReader, PdfWriter
        
        # 1. Matnli pdf yaratamiz (watermark qatlami)
        c = canvas.Canvas(wm_pdf, pagesize=A4)
        c.setFont("Helvetica-Bold", 60)
        c.setFillColorRGB(0.5, 0.5, 0.5, alpha=0.3) # Yarim shaffof kulrang
        c.translate(300, 400)
        c.rotate(45)
        c.drawCentredString(0, 0, wm_text)
        c.save()
        
        # 2. Birlashtirish
        watermark = PdfReader(wm_pdf).pages[0]
        reader = PdfReader(in_path)
        writer = PdfWriter()
        
        for page in reader.pages:
            page.merge_page(watermark)
            writer.add_page(page)
            
        with open(out_path, "wb") as f_out:
            writer.write(f_out)
            
        result = FSInputFile(out_path, filename=f"wm_{original_name}")
        await message.answer_document(result, caption="✅ Watermark o'rnatildi!")
        await msg.delete()
    except Exception as e:
        logging.error(f"Watermark xato: {e}")
        await msg.edit_text("❌ Xatolik yuz berdi.")
    finally:
        for f in [in_path, wm_pdf, out_path]:
            if f and os.path.exists(f): os.remove(f)
        await state.clear()


# ── 5. PDF DAN WORD GA O'GIRISH ──
@router.callback_query(F.data == "pdf_to_docx")
async def pdf_to_docx_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "🔄 <b>PDF dan Word ga</b>\n\nPDF faylni yuboring.",
        parse_mode="HTML"
    )
    await state.set_state(PdfStates.docx_waiting_file)

@router.message(PdfStates.docx_waiting_file, F.document)
async def pdf_to_docx_execute(message: Message, state: FSMContext, bot: Bot):
    doc = message.document
    if not doc.file_name.lower().endswith(".pdf"):
        return await message.answer("❌ Faqat PDF!")
        
    msg = await message.answer("⏳ O'girilmoqda... Bu biroz vaqt olishi mumkin.")
    
    os.makedirs("temp", exist_ok=True)
    in_path = f"temp/to_docx_{doc.file_id}.pdf"
    base_name = os.path.splitext(doc.file_name)[0]
    out_path = f"temp/{base_name}.docx"
    
    await bot.download(doc, destination=in_path)
    
    try:
        from pdf2docx import Converter
        cv = Converter(in_path)
        cv.convert(out_path, start=0, end=None)
        cv.close()
        
        result = FSInputFile(out_path, filename=f"{base_name}.docx")
        await message.answer_document(result, caption="✅ PDF muvaffaqiyatli Word formatiga o'girildi!")
        await msg.delete()
    except Exception as e:
        logging.error(f"PDF2Docx xato: {e}")
        await msg.edit_text("❌ Konvertatsiya vaqtida xato yuz berdi (Fayl juda murakkab yoki himoyalangan bo'lishi mumkin).")
    finally:
        for f in [in_path, out_path]:
            if f and os.path.exists(f): os.remove(f)
        await state.clear()
