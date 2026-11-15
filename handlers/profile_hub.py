"""👤 Profil: foydalanuvchining shaxsiy kartasi, sinab ko'rilmagan bo'limlar va sozlamalar."""
from datetime import datetime

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from services import activity, database, gemini
from services.alphabet import esc
from services.timeutil import now_tashkent

router = Router()

# "Sinab ko'rmagan bo'limlar" ro'yxatidagi tartib — eng foydalilari oldinda
SUGGEST_ORDER = ["scan", "docgen", "obyektivka", "translate", "format", "excel", "word", "pdf",
                 "ocr", "blanka", "search", "reminders", "qr"]
SUGGEST_LIMIT = 6


def _days_with_bot(joined: str) -> int | None:
    try:
        joined_dt = datetime.fromisoformat(joined[:19])
    except (TypeError, ValueError):
        return None
    return max(0, (now_tashkent().replace(tzinfo=None) - joined_dt).days)


def _format_date(value: str) -> str:
    try:
        return datetime.fromisoformat(value[:19]).strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return "—"


async def _collect(user) -> dict:
    """Profil uchun ma'lumot. Hali bazaga yozilmagan (xotiradagi) faollik ham hisobga olinadi."""
    profile = await database.get_user_profile(user.id) or {}
    sections = await database.get_user_sections(user.id)
    for sec, n in activity.pending_sections_for(user.id).items():
        sections[sec] = sections.get(sec, 0) + n
    return {
        "joined": profile.get("joined_date") or "",
        "sections": sections,
        "uses": sum(sections.values()),
        "referrals": await database.count_referrals(user.id),
        "reminders": await database.count_active_reminders(user.id),
    }


def untried_sections(used: dict[str, int]) -> list[str]:
    return [key for key in SUGGEST_ORDER if key not in used]


async def build_profile(user) -> tuple[str, InlineKeyboardMarkup]:
    info = await _collect(user)
    tool_keys = [k for k in activity.SECTION_TITLES if k != "ai"]
    used_tools = [k for k in tool_keys if k in info["sections"]]
    days = _days_with_bot(info["joined"])

    lines = [
        "👤 <b>Mening profilim</b>",
        "",
        f"🙋 {esc(user.full_name)}",
    ]
    if info["joined"]:
        since = _format_date(info["joined"])
        lines.append(f"📅 Botda: {since} dan beri" + (f" ({days} kun)" if days else " (bugundan)"))
    lines += [
        f"⚙️ Foydalanilgan amallar: <b>{info['uses']} marta</b>",
        f"🧭 Sinab ko'rilgan bo'limlar: <b>{len(used_tools)} / {len(tool_keys)}</b>",
        f"👥 Taklif qilgan do'stlar: <b>{info['referrals']} ta</b>",
        f"⏰ Faol eslatmalar: <b>{info['reminders']} ta</b>",
    ]
    if gemini.is_enabled():
        lines.append(f"🤖 Bugungi AI so'rovlari: <b>{gemini.remaining(user.id)} / {gemini.daily_limit()}</b> qoldi")

    if info["sections"]:
        favourite = max(info["sections"].items(), key=lambda kv: kv[1])[0]
        lines += ["", f"⭐️ Eng ko'p ishlatganingiz: {activity.SECTION_TITLES.get(favourite, favourite)}"]

    untried = untried_sections(info["sections"])
    if untried:
        lines += ["", f"💡 Siz hali <b>{len(untried)} ta</b> bo'limni sinab ko'rmagansiz — pastdagi tugmani bosing."]

    rows = []
    if untried:
        rows.append([InlineKeyboardButton(text="🧭 Sinab ko'rmagan bo'limlarim", callback_data="profile_untried")])
    rows += [
        [InlineKeyboardButton(text=f"⏰ Eslatmalar ({info['reminders']})", callback_data="reminders_menu"),
         InlineKeyboardButton(text=f"🔗 Do'stlarni taklif qilish", callback_data="share_bot")],
        [InlineKeyboardButton(text="⚙️ Sozlamalar va bot haqida", callback_data="hub_settings")],
        [InlineKeyboardButton(text="📞 Adminga murojaat", callback_data="feedback_start"),
         InlineKeyboardButton(text="💻 Dasturchi", callback_data="dev_contact")],
    ]
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(F.text.in_({"👤 Profil va Sozlamalar", "👤 Profil"}))
async def show_profile_hub(message: Message, state: FSMContext):
    await state.clear()
    text, keyboard = await build_profile(message.from_user)
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data == "profile_menu")
async def show_profile_hub_cb(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    text, keyboard = await build_profile(callback.from_user)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    except TelegramBadRequest:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data == "profile_untried")
async def show_untried(callback: CallbackQuery):
    from handlers.ai_assistant import SECTIONS   # bo'limlar tavsifi va go:KALIT tugmalari bitta joyda
    await callback.answer()
    info = await _collect(callback.from_user)
    keys = [k for k in untried_sections(info["sections"]) if k in SECTIONS][:SUGGEST_LIMIT]
    if not keys:
        await callback.message.edit_text(
            "🏆 Ajoyib! Siz botning barcha bo'limlarini sinab ko'rgansiz.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⬅️ Profilga qaytish", callback_data="profile_menu")]]),
        )
        return
    lines = ["🧭 <b>Siz hali sinab ko'rmagan bo'limlar</b>", ""]
    for key in keys:
        title, desc, _ = SECTIONS[key]
        lines.append(f"{title} — {desc}")
    lines += ["", "<i>Birini tanlang — bo'lim shu yerda ochiladi 👇</i>"]
    rows = [[InlineKeyboardButton(text=SECTIONS[k][0], callback_data=f"go:{k}") for k in keys[i:i + 2]]
            for i in range(0, len(keys), 2)]
    rows.append([InlineKeyboardButton(text="⬅️ Profilga qaytish", callback_data="profile_menu")])
    await callback.message.edit_text("\n".join(lines), parse_mode="HTML",
                                     reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data == "hub_settings")
async def redirect_to_settings(callback: CallbackQuery, state: FSMContext, bot):
    from handlers.settings import build_settings_text, get_settings_menu
    await callback.answer()
    text = await build_settings_text(bot, callback.from_user)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_settings_menu())


# ── Web ilova: bo'limlar xaritasidan tanlangan bo'lim (tg.sendData("go:KALIT")) ──
@router.message(F.web_app_data)
async def web_app_open_section(message: Message, state: FSMContext):
    from handlers.ai_assistant import send_section
    data = (message.web_app_data.data or "").strip()
    if data.startswith("go:"):
        key = data[3:]
        await state.clear()
        if await send_section(message, key):
            activity.record_section(message.from_user.id, key)
            return
    await message.answer("🤷 Bu so'rovni tushunmadim. Bosh menyudan kerakli bo'limni tanlang.")
