import os
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

router = Router()

class WordToolsStates(StatesGroup):
    choosing_action = State()
    # Shablon to'ldirish uchun holatlar
    waiting_for_template_file = State()
    waiting_for_template_data  = State()
    # Word o'qish uchun holat
    waiting_for_read_file = State()

def get_word_menu():
    pass # No longer needed since word_hub has the inline keyboard

# Entry point removed, handled by word_hub

# Namuna shablon removed

# ──────────────────────────────────────────────
# SHABLON TO'LDIRISH ({{placeholder}} → qiymat)
# ──────────────────────────────────────────────
@router.callback_query(F.data == "word_fill_template")
async def ask_template_file(callback, state: FSMContext):
    await callback.answer()
    await callback.message.answer(
        "📎 Iltimos, to'ldirmoqchi bo'lgan <b>.docx</b> shablon faylni yuboring.\n\n"
        "<i>Fayldagi <b>{{o'zgaruvchi_nomi}}</b> ko'rinishidagi joylar to'ldiriladi.</i>",
        parse_mode="HTML"
    )
    await state.set_state(WordToolsStates.waiting_for_template_file)

@router.message(WordToolsStates.waiting_for_template_file, F.document)
async def receive_template(message: Message, state: FSMContext, bot: Bot):
    doc = message.document
    if not doc.file_name.endswith('.docx'):
        await message.answer("Iltimos, faqat <b>.docx</b> formatidagi fayl yuboring.", parse_mode="HTML")
        return

    os.makedirs("temp", exist_ok=True)
    file_path = f"temp/template_{doc.file_id}.docx"
    await bot.download(doc, destination=file_path)

    # Shablon ichidagi o'zgaruvchilarni aniqlash
    from docx import Document as DocxDoc
    import re
    d = DocxDoc(file_path)
    full_text = " ".join([p.text for p in d.paragraphs])
    placeholders = list(dict.fromkeys(re.findall(r"\{\{(\w+)\}\}", full_text)))

    if not placeholders:
        await message.answer(
            "⚠️ Faylda <b>{{o'zgaruvchi}}</b> ko'rinishidagi joylar topilmadi.\n"
            "Avval shablonni to'g'ri tuzib yuboring.",
            parse_mode="HTML"
        )
        os.remove(file_path)
        await state.clear()
        return

    await state.update_data(
        template_path=file_path,
        original_name=doc.file_name,
        placeholders=placeholders,
        filled={}
    )

    placeholder_list = "\n".join([f"  • <code>{{{{{p}}}}}</code>" for p in placeholders])
    await message.answer(
        f"✅ Shablon qabul qilindi!\n\n"
        f"Faylda quyidagi <b>{len(placeholders)}</b> ta o'zgaruvchi topildi:\n{placeholder_list}\n\n"
        f"Endi har bir qiymatni <b>qator:qiymat</b> formatida yuboring.\n\n"
        f"<b>Misol:</b>\n<code>ism:Elshod Ibodullayev\nsana:04.08.2026\ntelefon:+998901234567</code>",
        parse_mode="HTML"
    )
    await state.set_state(WordToolsStates.waiting_for_template_data)

@router.message(WordToolsStates.waiting_for_template_data, F.text)
async def fill_template(message: Message, state: FSMContext):
    raw = message.text.strip()
    data = await state.get_data()

    template_path = data['template_path']
    original_name = data['original_name']
    placeholders  = data['placeholders']

    # Kiritilgan qiymatlarni parse qilish
    mapping = {}
    errors  = []
    for line in raw.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            mapping[key.strip()] = val.strip()
        else:
            errors.append(line)

    if errors:
        await message.answer(
            f"⚠️ Quyidagi qatorlar noto'g'ri formatda (qoldirildik):\n" +
            "\n".join([f"  • {e}" for e in errors]),
            parse_mode="HTML"
        )

    # Topilmagan o'zgaruvchilar
    missing = [p for p in placeholders if p not in mapping]
    if missing:
        await message.answer(
            "⚠️ Quyidagi o'zgaruvchilar uchun qiymat kiritilmadi (bo'sh qoladi):\n" +
            "\n".join([f"  • <code>{{{{{m}}}}}</code>" for m in missing]),
            parse_mode="HTML"
        )

    msg = await message.answer("Shablon to'ldirilmoqda... ⏳")

    output_path = f"temp/tayyor_{original_name}"
    try:
        from docx import Document as DocxDoc
        doc = DocxDoc(template_path)

        # Paragraphlardagi placeholder'larni almashtirish
        for para in doc.paragraphs:
            for key, val in mapping.items():
                placeholder = "{{" + key + "}}"
                if placeholder in para.text:
                    for run in para.runs:
                        if placeholder in run.text:
                            run.text = run.text.replace(placeholder, val)

        # Jadval ichidagi placeholder'lar
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for para in cell.paragraphs:
                        for key, val in mapping.items():
                            placeholder = "{{" + key + "}}"
                            if placeholder in para.text:
                                for run in para.runs:
                                    if placeholder in run.text:
                                        run.text = run.text.replace(placeholder, val)

        doc.save(output_path)

        result = FSInputFile(output_path, filename=f"tayyor_{original_name}")
        await message.answer_document(
            document=result,
            caption=f"✅ Shablon muvaffaqiyatli to'ldirildi!"
        )
    except Exception as e:
        logging.error(f"Shablon to'ldirishda xato: {e}")
        await message.answer("❌ Xatolik yuz berdi. Fayl formati noto'g'ri bo'lishi mumkin.")
    finally:
        for path in [template_path, output_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
        await msg.delete()
        await state.clear()

# ──────────────────────────────────────────────
# WORD FAYLNI O'QISH
# ──────────────────────────────────────────────
@router.callback_query(F.data == "word_read")
async def ask_read_file(callback, state: FSMContext):
    await callback.answer()
    await callback.message.answer(
        "📎 O'qimoqchi bo'lgan <b>.docx</b> faylni yuboring:",
        parse_mode="HTML"
    )
    await state.set_state(WordToolsStates.waiting_for_read_file)

@router.message(WordToolsStates.waiting_for_read_file, F.document)
async def read_word_file(message: Message, state: FSMContext, bot: Bot):
    doc_file = message.document
    if not doc_file.file_name.endswith('.docx'):
        await message.answer("Iltimos, faqat <b>.docx</b> formatidagi fayl yuboring.", parse_mode="HTML")
        return

    os.makedirs("temp", exist_ok=True)
    file_path = f"temp/read_{doc_file.file_id}.docx"
    await bot.download(doc_file, destination=file_path)

    msg = await message.answer("Fayl o'qilmoqda... ⏳")

    try:
        from docx import Document as DocxDoc
        doc = DocxDoc(file_path)

        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        full_text = "\n".join(paragraphs)

        if not full_text:
            await msg.edit_text("⚠️ Fayl bo'sh yoki matn topilmadi.")
            return

        header = f"📄 <b>{doc_file.file_name}</b>\n{'─' * 28}\n\n"
        max_len = 4096 - len(header)
        
        # Check for signature
        needs_signature = False
        if "imzo:" in full_text.lower() or "____" in full_text:
            needs_signature = True
            
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        markup = None
        if needs_signature:
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✍️ Imzo qo'yish", callback_data=f"sign_doc_{doc_file.file_id}")]
            ])
            await state.update_data(sign_doc_path=file_path, sign_doc_name=doc_file.file_name)

        if len(full_text) <= max_len:
            await msg.edit_text(header + full_text, parse_mode="HTML", reply_markup=markup)
        else:
            await msg.edit_text(header + full_text[:max_len] + "\n\n<i>... (davomi quyida)</i>", parse_mode="HTML")
            remaining = full_text[max_len:]
            while remaining:
                chunk = remaining[:4096]
                remaining = remaining[4096:]
                if not remaining and markup:
                    await message.answer(chunk, reply_markup=markup)
                else:
                    await message.answer(chunk)
                    
        if not needs_signature:
            os.remove(file_path)
            await state.clear()

    except Exception as e:
        logging.error(f"Word faylni o'qishda xato: {e}")
        await msg.edit_text("❌ Xatolik yuz berdi. Fayl shikastlangan bo'lishi mumkin.")
        if os.path.exists(file_path):
            os.remove(file_path)
        await state.clear()

class SignDocStates(StatesGroup):
    waiting_for_signature_image = State()

@router.callback_query(F.data.startswith("sign_doc_"))
async def start_signing_doc(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("🖼 Iltimos, o'z imzoingiz tushirilgan rasmni (orqasi oq yoki shaffof) yuboring:")
    await state.set_state(SignDocStates.waiting_for_signature_image)

@router.message(SignDocStates.waiting_for_signature_image, F.photo | F.document)
async def process_signature_image(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    doc_path = data.get("sign_doc_path")
    doc_name = data.get("sign_doc_name", "imzolangan.docx")
    
    if not doc_path or not os.path.exists(doc_path):
        await message.answer("❌ Kechirasiz, fayl topilmadi. Iltimos Word faylni boshqatdan yuboring.")
        await state.clear()
        return
        
    os.makedirs("temp", exist_ok=True)
    if message.photo:
        photo = message.photo[-1]
        img_path = f"temp/sig_{photo.file_id}.jpg"
        await bot.download(photo.file_id, destination=img_path)
    else:
        doc = message.document
        valid_exts = ('.jpg', '.jpeg', '.png')
        if not any(doc.file_name.lower().endswith(ext) for ext in valid_exts):
            await message.answer("Iltimos, faqat rasm (png, jpg) yuboring.")
            return
        img_path = f"temp/sig_{doc.file_id}.png"
        await bot.download(doc.file_id, destination=img_path)
        
    msg = await message.answer("✍️ Imzo tushirilmoqda... ⏳")
    
    try:
        from docx import Document as DocxDoc
        from docx.shared import Inches
        doc = DocxDoc(doc_path)
        
        signature_added = False
        for para in doc.paragraphs:
            if "imzo:" in para.text.lower() or "____" in para.text:
                para.text = para.text.replace("____", "") # Tozalash
                run = para.add_run()
                run.add_picture(img_path, width=Inches(1.5))
                signature_added = True
                break
                
        if not signature_added:
            # Agar aniq topilmasa oxiriga qo'shamiz
            para = doc.add_paragraph("Imzo: ")
            run = para.add_run()
            run.add_picture(img_path, width=Inches(1.5))
            
        out_path = f"temp/signed_{doc_name}"
        doc.save(out_path)
        
        result = FSInputFile(out_path, filename=f"imzolangan_{doc_name}")
        await message.answer_document(result, caption="✅ Hujjatga imzoingiz muvaffaqiyatli tushirildi!")
        await msg.delete()
    except Exception as e:
        logging.error(f"Imzo qoyish xatosi: {e}")
        await msg.edit_text("❌ Imzo tushirishda xatolik yuz berdi.")
    finally:
        for f in [img_path, doc_path, out_path]:
            if f and os.path.exists(f): os.remove(f)
        await state.clear()

# ──────────────────────────────────────────────
# WORD DAN PDF GA O'GIRISH
# ──────────────────────────────────────────────
class WordToPdfStates(StatesGroup):
    waiting_for_word = State()

@router.callback_query(F.data == "word_to_pdf")
async def word_to_pdf_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer(
        "📎 PDF ga o'girish uchun <b>.docx</b> faylni yuboring:",
        parse_mode="HTML"
    )
    await state.set_state(WordToPdfStates.waiting_for_word)

@router.message(WordToPdfStates.waiting_for_word, F.document)
async def process_word_to_pdf(message: Message, state: FSMContext, bot: Bot):
    doc_file = message.document
    if not doc_file.file_name.endswith('.docx'):
        await message.answer("Iltimos, faqat <b>.docx</b> formatidagi fayl yuboring.", parse_mode="HTML")
        return

    os.makedirs("temp", exist_ok=True)
    input_path = f"temp/to_pdf_{doc_file.file_id}.docx"
    
    await bot.download(doc_file, destination=input_path)
    msg = await message.answer("Word fayli PDF ga o'girilmoqda... ⏳")

    try:
        import subprocess
        # Try LibreOffice first (good for Linux servers like Ubuntu)
        process = subprocess.run(
            ['libreoffice', '--headless', '--convert-to', 'pdf', input_path, '--outdir', 'temp'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        output_path = f"temp/to_pdf_{doc_file.file_id}.pdf"
        
        if not os.path.exists(output_path):
            # Fallback to docx2pdf (works on Windows/Mac)
            from docx2pdf import convert
            output_path = f"temp/converted_{doc_file.file_id}.pdf"
            convert(input_path, output_path)
            
        if os.path.exists(output_path):
            result = FSInputFile(output_path, filename=doc_file.file_name.replace('.docx', '.pdf'))
            await message.answer_document(
                document=result,
                caption="✅ Fayl PDF formatiga o'girildi!"
            )
        else:
            await msg.edit_text("❌ Konvertatsiya jarayonida xatolik yuz berdi.")
            
    except Exception as e:
        logging.error(f"Word -> PDF error: {e}")
        await msg.edit_text("❌ Xatolik yuz berdi. Bu funksiya serverda LibreOffice yoki MS Word o'rnatilgan bo'lishini talab qiladi.")
    finally:
        if os.path.exists(input_path): os.remove(input_path)
        # Try to clean up any created PDF
        for f in os.listdir("temp"):
            if f.startswith(f"to_pdf_{doc_file.file_id}") or f.startswith(f"converted_{doc_file.file_id}"):
                try: os.remove(f"temp/{f}")
                except: pass
        await msg.delete()
        await state.clear()
