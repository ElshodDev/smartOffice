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
    # Imzo qo'yish uchun holat
    waiting_for_signature = State()

def get_word_menu():
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = [
        [
            InlineKeyboardButton(text="📝 Shablon to'ldirish", callback_data="word_fill_template"),
            InlineKeyboardButton(text="📖 Word faylni o'qish", callback_data="word_read")
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

        if len(full_text) <= max_len:
            await msg.edit_text(header + full_text, parse_mode="HTML")
        else:
            await msg.edit_text(header + full_text[:max_len] + "\n\n<i>... (davomi quyida)</i>", parse_mode="HTML")
            remaining = full_text[max_len:]
            while remaining:
                chunk = remaining[:4096]
                remaining = remaining[4096:]
                await message.answer(chunk)
                
        # Agar matnda Imzo joyi kabi narsalar bo'lsa, imzo qo'yish tugmasini chiqaramiz
        if "imzo:" in full_text.lower() or "____" in full_text:
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            btn = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✍️ Hujjatga Imzo qo'yish", callback_data=f"sign_word:{doc_file.file_id}")]
            ])
            await message.answer("Ushbu hujjatda imzo qo'yish joyi mavjudligini aniqladim. Uni bot orqali imzolamoqchimisiz?", reply_markup=btn)


    except Exception as e:
        logging.error(f"Word faylni o'qishda xato: {e}")
        await msg.edit_text("❌ Xatolik yuz berdi. Fayl shikastlangan bo'lishi mumkin.")
    finally:
        if os.path.exists(file_path):
            try: os.remove(file_path)
            except: pass
        await state.clear()

# ──────────────────────────────────────────────
# WORD FAYLGA IMZO QO'YISH
# ──────────────────────────────────────────────
@router.callback_query(F.data.startswith("sign_word:"))
async def ask_for_signature(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    file_id = callback.data.split(":")[1]
    await state.update_data(sign_file_id=file_id)
    await callback.message.answer(
        "✍️ Iltimos, hujjatga qo'yiladigan Ism-Familiyangizni (yoki matnli imzo) yuboring:\n\n"
        "<i>(Masalan: Elshod Ibodullayev)</i>",
        parse_mode="HTML"
    )
    await state.set_state(WordToolsStates.waiting_for_signature)

@router.message(WordToolsStates.waiting_for_signature, F.text)
async def process_word_signature(message: Message, state: FSMContext, bot: Bot):
    signature_text = message.text.strip()
    data = await state.get_data()
    file_id = data.get("sign_file_id")
    
    if not file_id:
        await message.answer("❌ Fayl topilmadi, iltimos boshqatdan urinib ko'ring.")
        await state.clear()
        return

    os.makedirs("temp", exist_ok=True)
    input_path = f"temp/to_sign_{file_id}.docx"
    output_path = f"temp/signed_{file_id}.docx"
    
    msg = await message.answer("Hujjat imzolanmoqda... ⏳")
    
    try:
        file = await bot.get_file(file_id)
        await bot.download_file(file.file_path, destination=input_path)
        
        from docx import Document as DocxDoc
        doc = DocxDoc(input_path)
        
        signature_added = False
        
        # Replace 'Imzo: _____' or just '_____' near 'Imzo'
        for para in doc.paragraphs:
            if "imzo:" in para.text.lower() or "____" in para.text:
                # Oson almashtirish uchun shunchaki matn oxiriga yoki chiziqchalar o'rniga qo'yamiz
                if "____" in para.text:
                    para.text = para.text.replace("____", signature_text, 1) # faqata bittasini almashtirish
                    # Qolgan chiziqlarni tozalash (agar uzun bo'lsa)
                    import re
                    para.text = re.sub(r'_+', '', para.text)
                else:
                    para.text = para.text + f" {signature_text}"
                signature_added = True
                
        # Jadval ichida ham tekshiramiz
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for para in cell.paragraphs:
                        if "imzo:" in para.text.lower() or "____" in para.text:
                            if "____" in para.text:
                                para.text = para.text.replace("____", signature_text, 1)
                                import re
                                para.text = re.sub(r'_+', '', para.text)
                            else:
                                para.text = para.text + f" {signature_text}"
                            signature_added = True

        doc.save(output_path)
        
        if signature_added:
            result = FSInputFile(output_path, filename=f"Imzolangan_hujjat.docx")
            await message.answer_document(
                document=result,
                caption="✅ Hujjat muvaffaqiyatli imzolandi!"
            )
        else:
            await message.answer("⚠️ Hujjat ichidan 'Imzo' yoki chiziqchalar (____) topilmadi, shuning uchun o'zgarishsiz qoldi.")
            
    except Exception as e:
        logging.error(f"Imzo qo'yishda xato: {e}")
        await message.answer("❌ Xatolik yuz berdi.")
    finally:
        for path in [input_path, output_path]:
            if os.path.exists(path):
                try: os.remove(path)
                except: pass
        await msg.delete()
        await state.clear()



