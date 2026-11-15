"""
🤖 AI Yordamchi (Gemini): suhbat (xotira bilan), hujjat/rasm/ovoz tahlili, tez buyruqlar
va foydalanuvchini botning kerakli bo'limiga yo'naltirish.
"""
import html
import io
import logging
import os

from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config import ADMIN_ID
from services import gemini
from services.ai_format import to_telegram, extract_sections, strip_html
from services.converter_service import run_heavy, IMAGE_EXTENSIONS

router = Router()

HISTORY_MESSAGES = 10           # suhbatda eslab qolinadigan oxirgi xabarlar
HISTORY_ITEM_CHARS = 3000
DOC_CHARS = 60_000              # hujjatdan AI'ga beriladigan matn (≈15 ming token)
MAX_INPUT_CHARS = 4000
MAX_IMAGE_BYTES = 7 * 1024 * 1024
MAX_VOICE_SECONDS = 180
MAX_DOC_BYTES = 20 * 1024 * 1024


# ── Bot bo'limlari katalogi: AI shu ro'yxatdan foydalanuvchini yo'naltiradi ──
def _menu(module: str, factory: str):
    def build():
        mod = __import__(f"handlers.{module}", fromlist=[factory])
        return getattr(mod, factory)()
    return build


def _single(text: str, callback: str):
    return lambda: InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, callback_data=callback)]])


SECTIONS = {
    # key: (tugma nomi, AI uchun tavsif, menyu)
    "excel": ("📊 Excel", "Excel: qatorlarni qirqish, teng bo'laklarga yoki ustun bo'yicha bo'lish, dublikatlarni tozalash, fayllarni birlashtirish, grafik chizish", _menu("excel_hub", "get_excel_menu")),
    "search": ("🔍 Jadvaldan qidirish", "Excel jadvaldan so'z, ism yoki telefon raqamini qidirish", _single("🔍 Qidirishni boshlash", "tools_search")),
    "pdf": ("📄 PDF", "PDF: birlashtirish, sahifalarni ajratish, watermark qo'yish", _menu("pdf_tools", "get_pdf_menu")),
    "word": ("📝 Word", "Word: {{o'zgaruvchi}} li shablonni to'ldirish, Excel ro'yxatdan ommaviy hujjat yaratish (sertifikat, taklifnoma), Word faylni o'qish", _menu("word_tools", "get_word_menu")),
    "docgen": ("✍️ Rasmiy hujjat", "Rasmiy hujjat yaratish: ariza (ishga kirish, ta'til, ishdan bo'shash), tushuntirish xati, dalolatnoma, tavsifnoma, buyruq — savollarga javob berib tayyor Word", _menu("doc_generator", "doc_types_menu")),
    "obyektivka": ("📋 Obyektivka", "Obyektivka (ma'lumotnoma) tayyorlash — PDF yoki Excel", _single("📋 Obyektivkani boshlash", "hub_obyektivka")),
    "blanka": ("🖊 Blankani to'ldirish", "Blanka yoki ariza rasmi ustiga matn, sana va barmoq bilan imzo qo'yib PDF olish", _single("🖊 Boshlash", "form_fill")),
    "translate": ("🔤 Tarjimon", "Tarjima (UZ↔EN, UZ↔RU), Lotin↔Kirill va yangi lotin alifbosiga o'girish — matn, Word, PDF", _menu("converter", "get_direction_menu")),
    "format": ("📁 Format o'zgartirish", "PDF→Word, rasm(lar)→PDF, PDF→rasm, PDF hajmini kichraytirish, HEIC/WEBP→JPG", _menu("format_converter", "get_converter_menu")),
    "scan": ("📸 Hujjat skaneri", "Telefonda olingan hujjat suratini toza skan PDF qilish (qirqish, tekislash, soyani olish)", _single("📸 Skanerlashni boshlash", "format_scan")),
    "ocr": ("🖼 Rasmdan matn (OCR)", "Rasmdagi matnni (o'zbek, rus, ingliz) ko'chirib olish", _single("🖼 OCR ni boshlash", "tools_ocr")),
    "qr": ("🔳 QR kod", "Matn yoki havoladan QR kod yaratish", _single("🔳 QR kod yaratish", "util_qr")),
    "reminders": ("⏰ Eslatmalar", "Belgilangan vaqtda eslatma (Toshkent vaqti)", _menu("reminders", "get_reminders_menu")),
}


# AI bo'lim belgisini qo'ymasa — foydalanuvchi xabaridagi kalit so'zlar bo'yicha taklif qilamiz
KEYWORD_SECTIONS = [
    (("skaner", "skan", "suratini pdf", "rasmini pdf", "fotodan pdf"), "scan"),
    (("obyektivka", "ma'lumotnoma"), "obyektivka"),
    (("ariza", "tushuntirish xat", "dalolatnoma", "tavsifnoma", "buyruq", "xarakteristika"), "docgen"),
    (("blanka", "imzo qo'y", "imzola"), "blanka"),
    (("rasmdan matn", "ocr", "matnni ko'chir"), "ocr"),
    (("qidir",), "search"),
    (("excel", "jadval", "xlsx"), "excel"),
    (("word", "docx", "shablon", "sertifikat"), "word"),
    (("pdf",), "pdf"),
    (("format", "jpg", "heic", "png", "kichrayt", "siqish"), "format"),
    (("tarjima", "kirill", "lotin", "alifbo", "inglizcha", "ruscha"), "translate"),
    (("qr",), "qr"),
    (("eslat",), "reminders"),
]


def keyword_sections(text: str, limit: int = 2) -> list[str]:
    low = text.lower().replace("‘", "'").replace("’", "'").replace("ʻ", "'")
    found = []
    for words, key in KEYWORD_SECTIONS:
        if key not in found and any(w in low for w in words):
            found.append(key)
    if "pdf" in found and "scan" in found:   # "suratni pdf" — skaner aniqroq
        found.remove("pdf")
    if "pdf" in found and "format" not in found:
        found.append("format")               # PDF bilan bog'liq ishlarning yarmi formatlar bo'limida
    return found[:limit]


def section_keyboard(keys: list[str], extra_rows: list | None = None) -> InlineKeyboardMarkup | None:
    rows = [[InlineKeyboardButton(text=f"➡️ {SECTIONS[k][0]}", callback_data=f"go:{k}")] for k in keys if k in SECTIONS]
    rows += extra_rows or []
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


def _catalog_text() -> str:
    return "\n".join(f"- {key}: {desc}" for key, (_, desc, _) in SECTIONS.items())


SYSTEM_PROMPT = f"""Sen «smartOffice» Telegram botining aqlli yordamchisisan. Foydalanuvchilar asosan O'zbekistondagi ofis xodimlari, o'qituvchilar, talabalar va davlat xizmatchilari.

Vazifang:
1. Savollarga o'zbek tilida (foydalanuvchi boshqa tilda yozsa — o'sha tilda) aniq, foydali va qisqa javob ber.
2. Foydalanuvchining muammosini hal qilishga yordam ber. Agar muammoni botning biror bo'limi hal qila olsa — albatta ayt va javob oxirida maxsus belgi qo'y: [[bo'lim:KALIT]] (ko'pi bilan 2 ta). Bot bu belgini o'sha bo'limni ochadigan tugmaga aylantiradi.
3. Foydalanuvchi biror ish qilmoqchi ekanini yozsa (masalan «PDF yubormoqchiman», «ariza yozishim kerak») — bu yordam so'rovi: matnini qayta yozib berma, balki buni qanday qilishni qisqa tushuntir va mos bo'limni taklif qil.
4. Botda yo'q narsani bor deb aytma. PDF'ga parol qo'yish va Word'dan PDF'ga o'girish botda YO'Q.

Bot bo'limlari (KALIT: imkoniyat):
{_catalog_text()}

Uslub: do'stona, hurmat bilan ("Siz"). Kerak bo'lsa qisqa ro'yxat va **qalin** ajratish ishlat, jadval ishlatma.
Davlat sirlari, shaxsiy ma'lumotlar yoki noqonuniy ishlar bo'yicha yordam berma. Tibbiy, huquqiy, moliyaviy savollarda umumiy ma'lumot ber va mutaxassisga murojaat qilishni maslahat ber."""


QUICK_ACTIONS = {
    "formal": ("✍️ Rasmiy uslubga o'tkazish",
               "Quyidagi matnni o'zbek tilida rasmiy-ish uslubiga o'tkaz. Ma'nosini va faktlarni o'zgartirma, yangi ma'lumot qo'shma. Faqat tayyor matnni yoz."),
    "spell": ("🔤 Imlo xatolarini tuzatish",
              "Quyidagi matndagi imlo, tinish belgisi va grammatik xatolarni tuzat (o'zbekcha bo'lsa — lotin yozuvi qoidalari bo'yicha). Avval tuzatilgan matnni to'liq yoz, so'ng 'Tuzatishlar:' sarlavhasi ostida asosiylarini qisqa sanab o't."),
    "short": ("✂️ Qisqartirish",
              "Quyidagi matnni asosiy fikrlarini saqlab, 2-3 baravar qisqartir. Faqat qisqartirilgan matnni yoz."),
    "letter": ("📨 Rasmiy xat yozish",
               "Quyidagi qisqa tavsif asosida o'zbek tilida rasmiy xat yoz: kimga, murojaat, asosiy qism, iltimos/xulosa, hurmat bilan. Ma'lum bo'lmagan ism, sana va raqamlar o'rniga [ ] qavsda joy qoldir."),
}


class AIStates(StatesGroup):
    chatting = State()


def _is_admin(user_id: int) -> bool:
    return bool(ADMIN_ID) and str(user_id) == str(ADMIN_ID).lstrip("@")


def main_keyboard() -> InlineKeyboardMarkup:
    acts = [InlineKeyboardButton(text=title, callback_data=f"ai_act:{key}") for key, (title, _) in QUICK_ACTIONS.items()]
    return InlineKeyboardMarkup(inline_keyboard=[
        acts[:2], acts[2:],
        [InlineKeyboardButton(text="❓ Bot nimalar qila oladi?", callback_data="ai_help")],
        [InlineKeyboardButton(text="🔄 Yangi suhbat", callback_data="ai_reset")],
    ])


AFTER_ANSWER_ROWS = [[
    InlineKeyboardButton(text="🔄 Yangi suhbat", callback_data="ai_reset"),
    InlineKeyboardButton(text="⚡ Tez buyruqlar", callback_data="ai_menu"),
]]


def _intro(user_id: int) -> str:
    if not gemini.is_enabled():
        return ("🤖 <b>AI Yordamchi</b>\n\n⚠️ AI hozircha o'chirilgan. Lekin botning barcha bo'limlarini "
                "«❓ Bot nimalar qila oladi?» tugmasi orqali ko'rishingiz mumkin.")
    left = "cheksiz" if _is_admin(user_id) else f"{gemini.remaining(user_id)} / {gemini.daily_limit()}"
    return (
        "🤖 <b>AI Yordamchi</b>\n\n"
        "Menga savol yozing — men eslab qolaman, shuning uchun suhbatni davom ettirishingiz mumkin. Yana:\n"
        "📄 <b>Word yoki PDF</b> yuboring — qisqacha mazmunini chiqaraman va savollaringizga javob beraman;\n"
        "🖼 <b>rasm</b> yuboring — tahlil qilib tushuntiraman;\n"
        "🎙 <b>ovozli xabar</b> yuboring — tinglab javob beraman.\n\n"
        "<i>Masalan: «Ishdan bo'shash arizasini qanday yozaman?», «Excelda bir xil qatorlarni qanday o'chiraman?»</i>\n\n"
        f"📊 Bugungi so'rovlar: <b>{left}</b>"
    )


async def _open(message: Message, state: FSMContext, user_id: int, edit: bool = False):
    await state.clear()
    await state.set_state(AIStates.chatting)
    await state.update_data(history=[])
    send = message.edit_text if edit else message.answer
    await send(_intro(user_id), parse_mode="HTML", reply_markup=main_keyboard())


@router.message(F.text == "🤖 AI Yordamchi (Savol-javob)")
async def start_ai_chat(message: Message, state: FSMContext):
    await _open(message, state, message.from_user.id)


@router.callback_query(F.data == "ai_menu")
async def ai_menu(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    await state.set_state(AIStates.chatting)
    await state.update_data(history=data.get("history", []), action=None)
    await callback.message.answer(_intro(callback.from_user.id), parse_mode="HTML", reply_markup=main_keyboard())


@router.callback_query(F.data == "ai_reset")
async def ai_reset(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Yangi suhbat boshlandi")
    await _open(callback.message, state, callback.from_user.id)


# ── Bo'limlarga yo'naltirish (AI limitini sarflamaydi) ─────────────────────
@router.callback_query(F.data == "ai_help")
async def ai_help(callback: CallbackQuery):
    await callback.answer()
    lines = ["❓ <b>Bot nimalar qila oladi?</b>\n"]
    lines += [f"{title} — {html.escape(desc)}" for title, desc, _ in SECTIONS.values()]
    keys = list(SECTIONS)
    rows = [[InlineKeyboardButton(text=SECTIONS[k][0], callback_data=f"go:{k}") for k in keys[i:i + 2]]
            for i in range(0, len(keys), 2)]
    await callback.message.answer("\n".join(lines) + "\n\n<i>Kerakli bo'limni tanlang 👇</i>",
                                  parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data.startswith("go:"))
async def go_section(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split(":", 1)[1]
    if key not in SECTIONS:
        await callback.answer()
        return
    await callback.answer()
    await state.clear()
    title, _, build = SECTIONS[key]
    await callback.message.answer(f"{title}\n\nKerakli amalni tanlang 👇", reply_markup=build())


# ── Tez buyruqlar ──────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("ai_act:"))
async def ai_action(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split(":", 1)[1]
    if key not in QUICK_ACTIONS:
        await callback.answer()
        return
    await callback.answer()
    data = await state.get_data()
    await state.set_state(AIStates.chatting)
    await state.update_data(action=key, history=data.get("history", []))
    hint = "qisqacha tavsifini (kimga, nima haqida)" if key == "letter" else "matnni"
    await callback.message.answer(
        f"{QUICK_ACTIONS[key][0]}\n\nEndi {hint} yuboring 👇\n"
        "<i>Keyingi yuboradigan xabaringiz shu amal uchun ishlatiladi. Savol bermoqchi bo'lsangiz — «Bekor qilish» ni bosing.</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="ai_act_cancel")]]),
    )


@router.callback_query(F.data == "ai_act_cancel")
async def ai_action_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Bekor qilindi")
    await state.update_data(action=None)
    await callback.message.edit_text("❌ Tez buyruq bekor qilindi. Endi savolingizni yozishingiz mumkin.")


# ── Javob yuborish ─────────────────────────────────────────────────────────
async def _send_answer(message: Message, status: Message, raw: str, user_id: int,
                       header: str = "", fallback_keys: list[str] | None = None):
    text, keys = extract_sections(raw, set(SECTIONS))
    keys = keys or (fallback_keys or [])
    chunks = to_telegram(text)
    if header:
        chunks[0] = f"<b>{html.escape(header, quote=False)}</b>\n\n{chunks[0]}"
    left = gemini.remaining(user_id, _is_admin(user_id))
    if left <= 5:
        chunks[-1] += f"\n\n<i>📊 Bugun yana {left} ta so'rov qoldi.</i>"
    keyboard = section_keyboard(keys, AFTER_ANSWER_ROWS)
    for i, chunk in enumerate(chunks):
        markup = keyboard if i == len(chunks) - 1 else None
        try:
            if i == 0:
                await status.edit_text(chunk, parse_mode="HTML", reply_markup=markup)
            else:
                await message.answer(chunk, parse_mode="HTML", reply_markup=markup)
        except TelegramBadRequest:  # formatlash Telegram'ga yoqmasa — oddiy matn
            plain = strip_html(chunk)
            if i == 0:
                await status.edit_text(plain, reply_markup=markup)
            else:
                await message.answer(plain, reply_markup=markup)


def _history_contents(history: list[dict], doc_text: str | None, doc_name: str | None):
    from google.genai import types
    contents = []
    if doc_text:
        contents.append(types.Content(role="user", parts=[types.Part.from_text(
            text=f"Men «{doc_name}» hujjatini yubordim. Uning matni:\n\n{doc_text}")]))
        contents.append(types.Content(role="model", parts=[types.Part.from_text(text="Hujjatni o'qidim.")]))
    for item in history:
        contents.append(types.Content(role=item["r"], parts=[types.Part.from_text(text=item["t"])]))
    return contents


async def _ask(message: Message, state: FSMContext, user_parts: list, history_text: str,
               header: str = "", fallback_keys: list[str] | None = None):
    """Limitni tekshiradi, AI'ga yuboradi, javobni ko'rsatadi va tarixga yozadi."""
    from google.genai import types
    user_id = message.from_user.id
    if not gemini.is_enabled():
        await message.answer(gemini.USER_MESSAGES["disabled"], reply_markup=section_keyboard([], [[
            InlineKeyboardButton(text="❓ Bot nimalar qila oladi?", callback_data="ai_help")]]))
        return
    if not gemini.consume(user_id, _is_admin(user_id)):
        await message.answer(
            f"⏳ Bugungi AI limiti ({gemini.daily_limit()} ta so'rov) tugadi. Ertaga yana foydalanishingiz mumkin.\n\n"
            "Bungacha botning boshqa bo'limlari cheklovsiz ishlaydi 👇",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="❓ Bot nimalar qila oladi?", callback_data="ai_help")]]),
        )
        return

    data = await state.get_data()
    history = list(data.get("history", []))
    contents = _history_contents(history, data.get("doc_text"), data.get("doc_name"))
    contents.append(types.Content(role="user", parts=user_parts))

    status = await message.answer("✍️ <i>AI o'ylamoqda...</i>", parse_mode="HTML")
    try:
        answer = await gemini.generate(contents, system_instruction=SYSTEM_PROMPT)
    except gemini.AIError as e:
        gemini.refund(user_id)
        await status.edit_text(gemini.USER_MESSAGES.get(e.kind, gemini.USER_MESSAGES["error"]))
        return

    history += [{"r": "user", "t": history_text[:HISTORY_ITEM_CHARS]},
                {"r": "model", "t": extract_sections(answer, set(SECTIONS))[0][:HISTORY_ITEM_CHARS]}]
    await state.update_data(history=history[-HISTORY_MESSAGES:], action=None)
    await _send_answer(message, status, answer, user_id, header, fallback_keys)


# ── Matn ───────────────────────────────────────────────────────────────────
@router.message(AIStates.chatting, F.text)
async def process_ai_message(message: Message, state: FSMContext):
    from google.genai import types
    text = message.text.strip()
    if text.startswith("/") or not text:
        return
    if len(text) > MAX_INPUT_CHARS:
        await message.answer(f"❌ Matn juda uzun ({len(text)} belgi). {MAX_INPUT_CHARS} belgigacha yuboring "
                             "yoki uni .txt / Word fayl qilib yuboring.")
        return
    action = (await state.get_data()).get("action")
    if action in QUICK_ACTIONS:
        prompt = f"{QUICK_ACTIONS[action][1]}\n\nMatn:\n{text}"
        await _ask(message, state, [types.Part.from_text(text=prompt)], prompt,
                   header=f"{QUICK_ACTIONS[action][0]} — natija:")
    else:
        await _ask(message, state, [types.Part.from_text(text=text)], text, fallback_keys=keyword_sections(text))


# ── Hujjat (Word / PDF / TXT) ──────────────────────────────────────────────
def _extract_document_text(path: str, ext: str) -> str:
    if ext == ".docx":
        from docx import Document
        from services.docx_template import iter_all_paragraphs
        return "\n".join(p.text for p in iter_all_paragraphs(Document(path)) if p.text.strip())
    if ext == ".pdf":
        import fitz
        with fitz.open(path) as doc:
            return "\n".join(page.get_text() for page in doc)
    with open(path, "rb") as f:
        raw = f.read()
    for encoding in ("utf-8-sig", "cp1251"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


@router.message(AIStates.chatting, F.document & F.document.file_name.lower().regexp(r".*\.(docx|pdf|txt)$"))
async def ai_document(message: Message, state: FSMContext, bot: Bot):
    from google.genai import types
    doc = message.document
    if doc.file_size and doc.file_size > MAX_DOC_BYTES:
        await message.answer("❌ Fayl juda katta. 20 MB gacha bo'lgan fayl yuboring.")
        return
    ext = os.path.splitext(doc.file_name.lower())[1]
    buffer = io.BytesIO()
    await bot.download(doc, destination=buffer)
    from services.tempfiles import new_job_dir, remove
    job_dir = new_job_dir("aidoc")
    path = os.path.join(job_dir, "doc" + ext)
    try:
        with open(path, "wb") as f:
            f.write(buffer.getvalue())
        text = (await run_heavy(_extract_document_text, path, ext)).strip()
    except Exception:
        logging.exception("AI: hujjatni o'qib bo'lmadi")
        await message.answer("❌ Faylni o'qib bo'lmadi. Fayl buzilgan bo'lishi mumkin.")
        return
    finally:
        remove(job_dir)
    if not text:
        await message.answer(
            "⚠️ Bu fayl ichida matn yo'q — u skaner qilingan (rasm ko'rinishidagi) hujjatga o'xshaydi.\n"
            "Sahifani rasm qilib yuborsangiz, men uni o'qib tushuntiraman. Yoki matnni OCR orqali ko'chirib oling 👇",
            reply_markup=section_keyboard(["ocr"]),
        )
        return
    truncated = len(text) > DOC_CHARS
    await state.update_data(doc_text=text[:DOC_CHARS], doc_name=doc.file_name, history=[])
    question = (message.caption or "").strip() or (
        "Ushbu hujjatning qisqacha mazmunini yoz: hujjat turi, asosiy maqsadi, muhim sanalar, summalar, "
        "majburiyatlar va e'tibor berish kerak bo'lgan joylar. Oxirida foydalanuvchi hujjat bo'yicha "
        "qanday savollar berishi mumkinligini 2-3 ta misol bilan ko'rsat.")
    note = " (hujjat juda uzun — faqat boshlang'ich qismi o'qildi)" if truncated else ""
    await message.answer(f"📄 «{html.escape(doc.file_name)}» qabul qilindi{note}. Endi u bo'yicha savol berishingiz mumkin.",
                         parse_mode="HTML")
    await _ask(message, state, [types.Part.from_text(text=question)], question)


# ── Rasm ───────────────────────────────────────────────────────────────────
def _image_to_jpeg(raw: bytes) -> bytes:
    from PIL import Image, ImageOps
    with Image.open(io.BytesIO(raw)) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((2048, 2048))
        out = io.BytesIO()
        im.save(out, "JPEG", quality=88)
        return out.getvalue()


@router.message(AIStates.chatting, F.photo | (F.document & F.document.file_name.lower().regexp(
    r".*\.(" + "|".join(e.lstrip(".") for e in IMAGE_EXTENSIONS) + r")$")))
async def ai_image(message: Message, state: FSMContext, bot: Bot):
    from google.genai import types
    file = message.photo[-1] if message.photo else message.document
    if file.file_size and file.file_size > MAX_IMAGE_BYTES:
        await message.answer("❌ Rasm juda katta (7 MB gacha).")
        return
    buffer = io.BytesIO()
    await bot.download(file, destination=buffer)
    try:
        jpeg = await run_heavy(_image_to_jpeg, buffer.getvalue())
    except Exception:
        await message.answer("❌ Rasmni ochib bo'lmadi.")
        return
    question = (message.caption or "").strip() or (
        "Rasmni tahlil qilib tushuntir. Agar unda hujjat, jadval yoki matn bo'lsa — mazmunini va asosiy "
        "ma'lumotlarni yoz. Agar xato xabari bo'lsa — sababini va yechimini tushuntir.")
    await _ask(message, state,
               [types.Part.from_bytes(data=jpeg, mime_type="image/jpeg"), types.Part.from_text(text=question)],
               f"[rasm yubordim] {question}")


# ── Ovozli xabar ───────────────────────────────────────────────────────────
@router.message(AIStates.chatting, F.voice | F.audio)
async def ai_voice(message: Message, state: FSMContext, bot: Bot):
    from google.genai import types
    media = message.voice or message.audio
    if (media.duration or 0) > MAX_VOICE_SECONDS:
        await message.answer(f"❌ Ovozli xabar juda uzun. {MAX_VOICE_SECONDS // 60} daqiqagacha yuboring.")
        return
    buffer = io.BytesIO()
    await bot.download(media, destination=buffer)
    mime = "audio/ogg" if message.voice else (media.mime_type or "audio/mpeg")
    instruction = ("Foydalanuvchi ovozli xabar yubordi. Uni diqqat bilan tingla va savoliga javob ber. "
                   "Javob boshida bir qatorda «🎙 Savolingiz: ...» deb uning savolini qisqa yozib qo'y.")
    await _ask(message, state,
               [types.Part.from_bytes(data=buffer.getvalue(), mime_type=mime), types.Part.from_text(text=instruction)],
               "[ovozli savol yubordim]")


@router.message(AIStates.chatting, F.document)
async def ai_unsupported_document(message: Message):
    await message.answer("📎 AI quyidagi fayllarni o'qiy oladi: Word (.docx), PDF, .txt va rasmlar.\n"
                         "Excel jadval bo'lsa — «📊 Excel» bo'limidan foydalaning 👇",
                         reply_markup=section_keyboard(["excel", "search"]))
