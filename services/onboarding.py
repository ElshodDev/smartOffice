"""
🚀 Yangi foydalanuvchini tanishtirish.

1. /start — qisqa salom va "Nima qilmoqchisiz?" tugmalari (bir bosishda bo'lim ochiladi).
2. Birinchi natijadan (fayl) keyin — bog'liq bo'lim haqida bitta maslahat.
   Har bir maslahat bir marta, jami 3 tadan ko'p emas, kuniga bittadan ortiq emas.
3. Qo'shilib, 3 kun qaytmaganlarga — bitta foydali eslatma (faqat bir marta).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from services import activity, database
from services.timeutil import now_tashkent, DB_FORMAT

# ── 1. "Nima qilmoqchisiz?" ─────────────────────────────────────────────────
CHOICES = [
    ("scan", "📸 Hujjat rasmini PDF qilish"),
    ("docgen", "✍️ Ariza yoki xat yozish"),
    ("format", "📄 PDF ↔ Word, rasm ↔ PDF"),
    ("translate", "🔤 Tarjima, Lotin ↔ Kirill"),
    ("obyektivka", "📋 Obyektivka tayyorlash"),
    ("excel", "📊 Excel bilan ishlash"),
]


def choices_keyboard() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=title, callback_data=f"onb:{key}")] for key, title in CHOICES]
    rows.append([InlineKeyboardButton(text="🧭 Hammasini ko'rish", callback_data="onb:all")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def greeting(name: str) -> str:
    from services.alphabet import esc
    return (
        f"👋 Assalomu alaykum, {esc(name)}!\n\n"
        "Men — <b>smartOffice</b>, ofis ishlaringiz uchun tekin yordamchi: hujjat, PDF, Word, Excel, "
        "tarjima va ariza — hammasi bir joyda."
    )


QUESTION = "🎯 <b>Nima qilmoqchisiz?</b>\nTanlang — shu zahoti boshlaymiz 👇"


# ── 2. Natijadan keyingi maslahat ───────────────────────────────────────────
# bo'lim → [(taklif qilinadigan bo'lim, maslahat), ...]: foydalanuvchi hali ishlatmagan birinchisi tanlanadi
TIPS: dict[str, list[tuple[str, str]]] = {
    "scan": [("format", "Skan qilingan PDF'ni Word'ga o'girib, matnini tahrirlash ham mumkin."),
             ("ocr", "Hujjat rasmidagi matnni nusxalab olish ham mumkin — qayta yozish shart emas.")],
    "format": [("scan", "Telefonda olingan hujjat suratini toza, skanerdan chiqqandek PDF qilib beraman."),
               ("pdf", "Bir nechta PDF'ni bittaga birlashtirish yoki keraksiz sahifalarni olib tashlash mumkin.")],
    "pdf": [("format", "PDF'ni Word'ga o'girib tahrirlash yoki hajmini kichraytirish ham mumkin."),
            ("scan", "Qog'oz hujjatni telefonda rasmga olsangiz, toza PDF qilib beraman.")],
    "docgen": [("blanka", "Tayyor blanka rasmiga matn yozib, barmoq bilan imzo qo'yish ham mumkin."),
               ("obyektivka", "Obyektivkani ham savollarga javob berib, 3×4 rasm bilan tayyorlab beraman.")],
    "obyektivka": [("docgen", "Ariza, tushuntirish xati, tavsifnomani ham savollarga javob berib tayyorlayman."),
                   ("blanka", "Tayyor blankaga matn va imzo qo'yib, PDF qilib beraman.")],
    "excel": [("search", "Katta jadvaldan ism yoki raqamni bir zumda topib beraman."),
              ("word", "Excel ro'yxatdan har bir odam uchun alohida Word hujjat (sertifikat, taklifnoma) yasash mumkin.")],
    "word": [("excel", "Excel jadvallarni bo'lish, birlashtirish va dublikatlardan tozalash ham mumkin."),
             ("format", "Word'ni PDF ko'rinishida kerak bo'lsa — PDF'dan Word'ga va rasmdan PDF'ga o'giraman.")],
    "ocr": [("translate", "Ko'chirilgan matnni tarjima qilish yoki Kirill ↔ Lotinga o'girish ham mumkin."),
            ("scan", "Hujjat suratini toza PDF qilib ham beraman.")],
    "blanka": [("docgen", "Arizani noldan yozish kerak bo'lsa — savollarga javob bering, tayyor Word beraman.")],
    "search": [("excel", "Jadvalni ustun bo'yicha bo'laklarga ajratish yoki grafik chizish ham mumkin.")],
    "translate": [("ocr", "Rasmdagi matnni avval ko'chirib, keyin tarjima qilish mumkin.")],
    "qr": [("format", "Rasmlarni bitta PDF qilish yoki PDF'ni Word'ga o'girish ham mumkin.")],
}
MAX_TIPS = 3
TIP_DELAY = 2.0          # natija kelgach biroz kutib yuboriladi
RECENT_SECONDS = 15 * 60
_tip_day: dict[int, str] = {}


def pick_tip(section: str, used: set[str]) -> tuple[str, str] | None:
    for key, text in TIPS.get(section, []):
        if key not in used:
            return key, text
    return None


async def maybe_send_tip(bot, user_id: int) -> None:
    """Natija (fayl) yuborilgandan keyin chaqiriladi."""
    try:
        section = activity.last_section(user_id, RECENT_SECONDS)
        if not section or section not in TIPS:
            return
        today = now_tashkent().strftime("%Y-%m-%d")
        if _tip_day.get(user_id) == today:
            return
        if await database.count_flags(user_id, "tip:") >= MAX_TIPS:
            _tip_day[user_id] = today
            return
        used = set(await database.get_user_sections(user_id)) | set(activity.pending_sections_for(user_id))
        tip = pick_tip(section, used)
        if not tip or not await database.set_flag(user_id, f"tip:{section}"):
            return
        _tip_day[user_id] = today
        from handlers.ai_assistant import SECTIONS
        key, text = tip
        await asyncio.sleep(TIP_DELAY)
        await bot.send_message(
            user_id, f"💡 <b>Bilasizmi?</b> {text}", parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text=f"➡️ {SECTIONS[key][0]}", callback_data=f"go:{key}")]]),
        )
    except Exception as e:
        logging.warning(f"Maslahat yuborilmadi (user {user_id}): {e}")


class TipsRequestMiddleware(BaseRequestMiddleware):
    """Bot foydalanuvchiga fayl (natija) yuborgach — fonda maslahat yuborishga urinadi."""

    def __init__(self, admin_id: int | None = None):
        self.admin_id = admin_id

    async def __call__(self, make_request, bot, method):
        result = await make_request(bot, method)
        name = type(method).__name__
        if name in ("SendDocument", "SendPhoto"):
            chat_id = getattr(method, "chat_id", None)
            if isinstance(chat_id, int) and chat_id > 0 and chat_id != self.admin_id:
                asyncio.create_task(maybe_send_tip(bot, chat_id))
        return result


# ── 3. Qaytmaganlarga bitta eslatma ─────────────────────────────────────────
NUDGE_AFTER_DAYS = 3
NUDGE_WINDOW_DAYS = 14     # bundan oldin qo'shilganlarga yuborilmaydi
NUDGE_SUGGEST = ["scan", "docgen", "format", "obyektivka", "translate", "excel"]


async def send_nudges(bot) -> int:
    now = now_tashkent()
    candidates = await database.users_to_nudge(
        (now - timedelta(days=NUDGE_WINDOW_DAYS)).strftime(DB_FORMAT),
        (now - timedelta(days=NUDGE_AFTER_DAYS)).strftime(DB_FORMAT),
    )
    from handlers.ai_assistant import SECTIONS
    from services.alphabet import esc
    sent, blocked = 0, []
    for user_id, name in candidates:
        if not await database.set_flag(user_id, "nudge"):
            continue
        used = set(await database.get_user_sections(user_id))
        keys = [k for k in NUDGE_SUGGEST if k not in used][:3] or NUDGE_SUGGEST[:3]
        first = esc(name.split()[0]) if name.strip() else ""
        text = (
            f"👋 {first + ', ' if first else ''}smartOffice yordamingizga tayyor!\n\n"
            "Ko'pchilik meni shu ishlar uchun ishlatadi — bittasini sinab ko'ring, bir daqiqa ham olmaydi 👇"
        )
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=SECTIONS[k][0], callback_data=f"go:{k}")] for k in keys if k in SECTIONS])
        for _ in range(2):
            try:
                await bot.send_message(user_id, text, parse_mode="HTML", reply_markup=markup)
                sent += 1
                break
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after + 1)
            except (TelegramForbiddenError, TelegramBadRequest):
                blocked.append(user_id)
                break
            except Exception as e:
                logging.warning(f"Eslatma xabari yuborilmadi (user {user_id}): {e}")
                break
        await asyncio.sleep(0.05)
    if blocked:
        await database.mark_bot_blocked(blocked)
    if candidates:
        logging.info(f"Qaytish eslatmasi: {sent} ta yuborildi, {len(blocked)} ta bloklagan.")
    return sent
