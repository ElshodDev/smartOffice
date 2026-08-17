import os
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, FSInputFile, CallbackQuery
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
    waiting_for_signature = State()

def get_word_menu():
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = [
        [
            InlineKeyboardButton(text="📝 Shablon to'ldirish", callback_data="word_fill_template"),
            InlineKeyboardButton(text="📖 O'qish / Imzo qo'yish", callback_data="word_read")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# ──────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────
@router.message(F.text == "📝 Word Hujjat")
async def start_word_tools(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "📝 <b>Word Hujjat vositalari</b>\n\nQuyidagi amallardan birini tanlang:",
        parse_mode="HTML",
        reply_markup=get_word_menu()
    )

# ──────────────────────────────────────────────
# NAMUNA SHABLON YARATISH
# ──────────────────────────────────────────────
@router.callback_query(F.data == "word_sample")
async def send_sample_template(callback, bot: Bot):
    await callback.answer()
    msg = await callback.message.answer("Namuna shablon yaratilmoqda... ⏳")

    os.makedirs("temp", exist_ok=True)
    sample_path = "temp/namuna_shablon.docx"

    try:
        doc = Document()

        # Sarlavha uslubi
        title = doc.add_heading("XIZMAT KO'RSATISH SHARTNOMASI", level=1)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER

        doc.add_paragraph()

        # Asosiy ma'lumotlar
        p = doc.add_paragraph()
        p.add_run("Sana: ").bold = True
        p.add_run("{{sana}}")

        p = doc.add_paragraph()
        p.add_run("Foydalanuvchi ismi: ").bold = True
        p.add_run("{{ism}}")

        p = doc.add_paragraph()
        p.add_run("Telefon raqami: ").bold = True
        p.add_run("{{telefon}}")

        p = doc.add_paragraph()
        p.add_run("Manzil: ").bold = True
        p.add_run("{{manzil}}")

        p = doc.add_paragraph()
        p.add_run("Xizmat nomi: ").bold = True
        p.add_run("{{xizmat}}")

        p = doc.add_paragraph()
        p.add_run("Narxi: ").bold = True
        p.add_run("{{narx}} so'm")

        doc.add_paragraph()
        doc.add_paragraph("Imzo: _______________________")

        # Izoh qo'shing
        doc.add_paragraph()
        note = doc.add_paragraph()
        run = note.add_run(
            "📌 Eslatma: {{...}} ichidagi so'zlar — o'zgaruvchilar. "
            "Ushbu shablonni botga yuboring va qiymatlarni kiriting."
        )
        run.font.color.rgb = RGBColor(0x88, 0x88, 0x88)
        run.font.size = Pt(10)

        doc.save(sample_path)

        result = FSInputFile(sample_path, filename="namuna_shablon.docx")
        await bot.send_document(
            chat_id=callback.message.chat.id,
            document=result,
            caption=(
                "✅ <b>Namuna shablon!</b>\n\n"
                "Ushbu faylni yuklab oling, kerak bo'lsa tahrirlang.\n"
                "So'ng <b>«📝 Shablon to'ldirish»</b> tugmasini bosib botga yuboring."
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Namuna shablon yaratishda xato: {e}")
        await callback.message.answer("❌ Xatolik yuz berdi.")
    finally:
        if os.path.exists(sample_path):
            os.remove(sample_path)
        await msg.delete()

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
        # 4096 - header uzunligini chegiramiz
        max_len = 4096 - len(header)

        has_signature = False
        if "Imzo:" in full_text or "imzo:" in full_text or "________" in full_text:
            has_signature = True

        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        markup = None
        if has_signature:
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✍️ Imzo qo'yish", callback_data=f"sign_word_{doc_file.file_id}")]
            ])

        if len(full_text) <= max_len:
            await msg.edit_text(header + full_text, parse_mode="HTML", reply_markup=markup)
        else:
            await msg.edit_text(header + full_text[:max_len] + "\n\n<i>... (davomi quyida)</i>", parse_mode="HTML")
            remaining = full_text[max_len:]
            while remaining:
                chunk = remaining[:4096]
                remaining = remaining[4096:]
                if not remaining:
                    await message.answer(chunk, reply_markup=markup)
                else:
                    await message.answer(chunk)

    except Exception as e:
        logging.error(f"Word faylni o'qishda xato: {e}")
        await msg.edit_text("❌ Xatolik yuz berdi. Fayl shikastlangan bo'lishi mumkin.")
    finally:
        if os.path.exists(file_path):
            try: os.remove(file_path)
            except: pass
        await state.clear()

# ──────────────────────────────────────────────
# IMZO QO'YISH
# ──────────────────────────────────────────────
@router.callback_query(F.data.startswith("sign_word_"))
async def ask_for_signature(callback: CallbackQuery, state: FSMContext):
    file_id = callback.data.split("_")[2]
    await callback.answer()
    await callback.message.answer(
        "✍️ <b>Imzo qo'yish</b>\n\nIltimos, imzongiz tushirilgan rasmni yuboring (orqasi oq yoki shaffof bo'lsa yaxshi chiqadi):",
        parse_mode="HTML"
    )
    await state.update_data(sign_file_id=file_id)
    await state.set_state(WordToolsStates.waiting_for_signature)

@router.message(WordToolsStates.waiting_for_signature, F.photo | F.document)
async def process_signature(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    doc_id = data.get("sign_file_id")
    if not doc_id:
        return await message.answer("Xatolik: Hujjat topilmadi.")

    # Get signature image
    os.makedirs("temp", exist_ok=True)
    if message.photo:
        photo = message.photo[-1]
        sign_path = f"temp/sign_{photo.file_id}.jpg"
        await bot.download(photo.file_id, destination=sign_path)
    else:
        doc = message.document
        valid_exts = ('.jpg', '.jpeg', '.png')
        if not any(doc.file_name.lower().endswith(ext) for ext in valid_exts):
            return await message.answer(f"Iltimos, faqat rasm ({', '.join(valid_exts)}) yuboring.")
        sign_path = f"temp/sign_{doc.file_id}.jpg"
        await bot.download(doc.file_id, destination=sign_path)

    msg = await message.answer("Hujjatga imzo joylanmoqda... ⏳")
    doc_path = f"temp/doc_to_sign_{doc_id}.docx"
    out_path = f"temp/signed_{doc_id}.docx"

    try:
        # Download the original word document again using file_id
        await bot.download(doc_id, destination=doc_path)
        
        from docx import Document as DocxDoc
        from docx.shared import Inches
        d = DocxDoc(doc_path)
        
        signature_added = False
        for para in d.paragraphs:
            if "Imzo:" in para.text or "imzo:" in para.text or "________" in para.text:
                run = para.add_run()
                run.add_picture(sign_path, width=Inches(1.5))
                signature_added = True
                break
                
        if not signature_added:
            # If not found in paragraphs, just add at the end
            p = d.add_paragraph("Imzo: ")
            r = p.add_run()
            r.add_picture(sign_path, width=Inches(1.5))
            
        d.save(out_path)
        result = FSInputFile(out_path, filename="imzolangan_hujjat.docx")
        await message.answer_document(result, caption="✅ Imzo hujjatga tushirildi!")
    except Exception as e:
        logging.error(f"Imzo qoyish xatosi: {e}")
        await message.answer("❌ Xatolik yuz berdi. Imzoni joylashning imkoni bo'lmadi.")
    finally:
        for p in [sign_path, doc_path, out_path]:
            if os.path.exists(p):
                try: os.remove(p)
                except: pass
        await msg.delete()
        await state.clear()
