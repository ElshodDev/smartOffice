"""
👑 Admin panel (/admin): statistika, xabar tarqatish (oldindan ko'rish va tasdiqlash bilan),
foydalanuvchini topish / xabar yozish / bloklash, Excel ro'yxat va bot holati.
"""
import asyncio
import io
import logging
from datetime import timedelta

from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile,
)

from config import ADMIN_ID
from services import activity, botinfo, database, db, gemini
from services.alphabet import esc
from services.timeutil import now_tashkent, DB_FORMAT

try:
    _ADMIN_ID = int(ADMIN_ID) if ADMIN_ID else None
except (ValueError, TypeError):
    _ADMIN_ID = None

router = Router()
router.message.filter(F.from_user.id == _ADMIN_ID)
router.callback_query.filter(F.from_user.id == _ADMIN_ID)

BROADCAST_PAUSE = 0.05          # ~20 xabar/soniya — Telegram cheklovidan past
PROGRESS_EVERY = 25


class AdminStates(StatesGroup):
    waiting_for_broadcast_message = State()
    confirm_broadcast = State()
    waiting_for_user_query = State()
    waiting_for_direct_message = State()


def get_admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats"),
         InlineKeyboardButton(text="✉️ Xabar tarqatish", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🔎 Foydalanuvchini topish", callback_data="admin_find"),
         InlineKeyboardButton(text="📥 Ro'yxat (Excel)", callback_data="admin_export")],
        [InlineKeyboardButton(text="🩺 Bot holati", callback_data="admin_health")],
    ])


BACK_ROW = [InlineKeyboardButton(text="🔙 Admin panel", callback_data="admin_back")]
ADMIN_TITLE = "👑 <b>Admin Panel</b>\n\nQuyidagi amallardan birini tanlang:"


def _back_kb(*rows) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[*rows, BACK_ROW])


async def _edit_or_send(callback: CallbackQuery, text: str, markup=None):
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    except TelegramBadRequest:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=markup)


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(ADMIN_TITLE, parse_mode="HTML", reply_markup=get_admin_menu())


@router.callback_query(F.data == "admin_back")
async def go_back_to_admin(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await _edit_or_send(callback, ADMIN_TITLE, get_admin_menu())


# ── 📊 Statistika ──────────────────────────────────────────────────────────
def _period_starts():
    now = now_tashkent()
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return (day.strftime(DB_FORMAT), (day - timedelta(days=6)).strftime(DB_FORMAT),
            (day - timedelta(days=29)).strftime(DB_FORMAT))


def _percent(part: int, whole: int) -> str:
    return f"{round(part * 100 / whole)}%" if whole else "—"


ONBOARDING_TITLES = {"all": "🧭 Hammasini ko'rish"}


def onboarding_lines(o: dict, picks: list[tuple[str, int]]) -> list[str]:
    """🚀 Yangi kelganlar (30 kun): tanishuv qanchalik ishlayapti."""
    from services.onboarding import CHOICES
    titles = dict(CHOICES) | ONBOARDING_TITLES
    lines = ["", "🚀 <b>Yangi kelganlar (30 kun)</b>",
             f"👋 Qo'shildi: <b>{o['joined']}</b>",
             f"⚡️ Birinchi sutkada bo'lim ishlatdi: <b>{_percent(o['activated'], o['joined'])}</b> ({o['activated']} kishi)",
             f"🔁 Keyingi kunlarda qaytdi: <b>{_percent(o['returned'], o['eligible'])}</b> ({o['returned']} / {o['eligible']})"]
    if picks:
        lines.append("🎯 «Nima qilmoqchisiz?» tanlovlari: " +
                     ", ".join(f"{titles.get(k, k)} — {n}" for k, n in picks[:6]))
    return lines


async def build_stats_text() -> str:
    await activity.flush()
    day, week, month = _period_starts()
    s = await database.admin_stats(day, week, month)
    sections = await database.top_sections(since=week, limit=8)
    referrers = await database.top_referrers(5)
    ai_requests, ai_users = gemini.usage_today()

    lines = [
        "📊 <b>Bot statistikasi</b>",
        "",
        f"👥 Jami foydalanuvchilar: <b>{s['total']}</b>",
        f"🆕 Yangi: bugun <b>{s['new_day']}</b> · 7 kun <b>{s['new_week']}</b> · 30 kun <b>{s['new_month']}</b>",
        f"🔥 Faol: bugun <b>{s['active_day']}</b> · 7 kun <b>{s['active_week']}</b> · 30 kun <b>{s['active_month']}</b>",
        f"🔗 Taklif orqali kelganlar: <b>{s['referred']}</b>",
        f"🚫 Botni bloklaganlar: <b>{s['blocked']}</b> · ⛔️ Admin cheklagan: <b>{s['banned']}</b>",
        f"⏰ Faol eslatmalar: <b>{s['reminders']}</b>",
        f"🤖 Bugun AI: <b>{ai_requests}</b> ta so'rov, <b>{ai_users}</b> kishi",
    ]
    if sections:
        lines += ["", "🏆 <b>Eng ko'p ishlatilgan bo'limlar (7 kun)</b>"]
        for i, (sec, users, uses) in enumerate(sections, 1):
            lines.append(f"{i}. {activity.SECTION_TITLES.get(sec, sec)} — {users} kishi, {uses} marta")
    if referrers:
        lines += ["", "🤝 <b>Eng faol taklif qiluvchilar</b>"]
        for i, (uid, name, n) in enumerate(referrers, 1):
            lines.append(f"{i}. {esc(name) or uid} (<code>{uid}</code>) — {n} ta")
    lines += onboarding_lines(await database.onboarding_stats(month, now_tashkent().strftime(DB_FORMAT)),
                              await database.flag_stats("onb:", month))
    lines += ["", "<i>«Faol» — shu davrda botga kamida bir marta yozgan yoki tugma bosgan.</i>"]
    return "\n".join(lines)


@router.callback_query(F.data == "admin_stats")
async def show_stats(callback: CallbackQuery):
    await callback.answer()
    await _edit_or_send(callback, await build_stats_text(),
                        _back_kb([InlineKeyboardButton(text="🔄 Yangilash", callback_data="admin_stats")]))


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    await message.answer(await build_stats_text(), parse_mode="HTML", reply_markup=_back_kb())


# ── ✉️ Xabar tarqatish ─────────────────────────────────────────────────────
_broadcast = {"running": False, "stop": False}


@router.callback_query(F.data == "admin_broadcast")
async def ask_broadcast_message(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if _broadcast["running"]:
        await callback.message.answer("⏳ Oldingi xabar tarqatish hali tugamagan.")
        return
    await state.set_state(AdminStates.waiting_for_broadcast_message)
    await _edit_or_send(
        callback,
        "✉️ <b>Xabar tarqatish</b>\n\n"
        "Barcha foydalanuvchilarga yubormoqchi bo'lgan xabaringizni yuboring.\n"
        "<i>Matn, rasm, video, fayl — istalgan format. Yuborishdan oldin qanday ko'rinishini ko'rsataman.</i>",
        _back_kb(),
    )


@router.message(AdminStates.waiting_for_broadcast_message)
async def preview_broadcast(message: Message, state: FSMContext, bot: Bot):
    if message.text and message.text.startswith("/"):
        return
    await activity.flush()
    total = len(await database.get_broadcast_targets())
    if total == 0:
        await state.clear()
        await message.answer("Bazada hali foydalanuvchi yo'q.", reply_markup=_back_kb())
        return
    await state.set_state(AdminStates.confirm_broadcast)
    await state.update_data(bc_chat=message.chat.id, bc_msg=message.message_id)
    await message.answer("👆 Foydalanuvchilar xabarni aynan shunday ko'radi (pastda nusxasi):")
    await bot.copy_message(chat_id=message.chat.id, from_chat_id=message.chat.id, message_id=message.message_id)
    await message.answer(
        f"📨 Xabar <b>{total}</b> ta foydalanuvchiga yuborilsinmi?",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ Ha, {total} kishiga yuborish", callback_data="admin_bc_go")],
            [InlineKeyboardButton(text="✏️ Boshqa xabar", callback_data="admin_broadcast"),
             InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_back")],
        ]),
    )


async def _send_copy(bot: Bot, user_id: int, chat_id: int, message_id: int) -> str:
    """'ok' | 'blocked' | 'error'"""
    for _ in range(3):
        try:
            await bot.copy_message(chat_id=user_id, from_chat_id=chat_id, message_id=message_id)
            return "ok"
        except TelegramRetryAfter as e:              # Telegram "biroz kuting" desa — kutib, qayta urinamiz
            await asyncio.sleep(e.retry_after + 1)
        except TelegramForbiddenError:
            return "blocked"
        except TelegramBadRequest as e:
            text = str(e).lower()
            return "blocked" if ("chat not found" in text or "deactivated" in text) else "error"
        except Exception as e:
            logging.error(f"Broadcast — kutilmagan xato (user {user_id}): {e}")
            return "error"
    return "error"


def _progress_text(done: int, total: int, ok: int, blocked: int, failed: int, finished: bool = False) -> str:
    head = "✅ <b>Xabar tarqatish yakunlandi!</b>" if finished else "📤 <b>Xabar yuborilmoqda...</b>"
    percent = round(done * 100 / total) if total else 100
    return (f"{head}\n\n"
            f"📊 {done} / {total} ({percent}%)\n"
            f"📨 Yetkazildi: <b>{ok}</b>\n"
            f"🚫 Botni bloklagan: <b>{blocked}</b>\n"
            f"⚠️ Xato: <b>{failed}</b>")


async def run_broadcast(bot: Bot, status: Message, chat_id: int, message_id: int, targets: list[int]):
    _broadcast.update(running=True, stop=False)
    ok = blocked = failed = 0
    blocked_ids: list[int] = []
    stop_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⏹ To'xtatish", callback_data="admin_bc_stop")]])
    total = len(targets)
    try:
        for i, user_id in enumerate(targets, 1):
            if _broadcast["stop"]:
                break
            result = await _send_copy(bot, user_id, chat_id, message_id)
            if result == "ok":
                ok += 1
            elif result == "blocked":
                blocked += 1
                blocked_ids.append(user_id)
            else:
                failed += 1
            if i % PROGRESS_EVERY == 0 and i < total:
                try:
                    await status.edit_text(_progress_text(i, total, ok, blocked, failed),
                                           parse_mode="HTML", reply_markup=stop_kb)
                except TelegramBadRequest:
                    pass
            await asyncio.sleep(BROADCAST_PAUSE)
        if blocked_ids:
            await database.mark_bot_blocked(blocked_ids)
        done = ok + blocked + failed
        text = _progress_text(done, total, ok, blocked, failed, finished=True)
        if _broadcast["stop"]:
            text += "\n\n⏹ <i>Admin tomonidan to'xtatildi.</i>"
        await status.edit_text(text, parse_mode="HTML", reply_markup=_back_kb())
    except Exception:
        logging.exception("Xabar tarqatishda xato")
    finally:
        _broadcast.update(running=False, stop=False)


@router.callback_query(AdminStates.confirm_broadcast, F.data == "admin_bc_go")
async def confirm_broadcast(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    await state.clear()
    if _broadcast["running"]:
        await callback.answer("Oldingi tarqatish hali tugamagan.", show_alert=True)
        return
    await callback.answer("Boshlandi")
    targets = await database.get_broadcast_targets()
    status = await callback.message.edit_text(_progress_text(0, len(targets), 0, 0, 0), parse_mode="HTML")
    # Fonda yuboriladi — bot shu vaqtda boshqa foydalanuvchilarga javob berishda davom etadi
    asyncio.create_task(run_broadcast(bot, status, data["bc_chat"], data["bc_msg"], targets))


@router.callback_query(F.data == "admin_bc_go")
async def confirm_broadcast_expired(callback: CallbackQuery):
    await callback.answer("Bu so'rov eskirgan. Xabarni qaytadan yuboring.", show_alert=True)


@router.callback_query(F.data == "admin_bc_stop")
async def stop_broadcast(callback: CallbackQuery):
    _broadcast["stop"] = True
    await callback.answer("To'xtatilmoqda...")


# ── 🔎 Foydalanuvchini topish ───────────────────────────────────────────────
def _fmt_date(value: str) -> str:
    return value[:16] if value else "—"


async def user_card(uid: int) -> tuple[str, InlineKeyboardMarkup] | None:
    await activity.flush()
    found = await database.find_users(str(uid))
    if not found:
        return None
    u = found[0]
    sections = await database.get_user_sections(uid)
    referrals = await database.count_referrals(uid)
    reminders = await database.count_active_reminders(uid)
    used = ", ".join(activity.SECTION_TITLES.get(k, k) for k, _ in
                     sorted(sections.items(), key=lambda kv: -kv[1])) or "—"
    status = "⛔️ Admin cheklagan" if u["banned"] else ("🚫 Botni bloklagan" if u["blocked"] else "✅ Faol")
    text = (
        f"👤 <b>{esc(u['name']) or 'Ismsiz'}</b>\n"
        f"🆔 ID: <code>{u['id']}</code> · <a href='tg://user?id={u['id']}'>profilni ochish</a>\n\n"
        f"📅 Qo'shilgan: {_fmt_date(u['joined'])}\n"
        f"🕐 Oxirgi faollik: {_fmt_date(u['last_active'])}\n"
        f"⚙️ Amallar: {u['usage']} marta\n"
        f"🧭 Bo'limlar: {used}\n"
        f"👥 Taklif qilganlari: {referrals} ta" + (f" · uni taklif qilgan: <code>{u['referrer_id']}</code>"
                                                  if u["referrer_id"] else "") + "\n"
        f"⏰ Faol eslatmalar: {reminders}\n"
        f"📌 Holati: {status}\n\n"
        "<i>💬 Shu xabarga Reply qilib ham javob yozishingiz mumkin.</i>"
    )
    ban_btn = (InlineKeyboardButton(text="✅ Cheklovni olib tashlash", callback_data=f"admin_unban:{uid}")
               if u["banned"] else InlineKeyboardButton(text="⛔️ Cheklash", callback_data=f"admin_ban:{uid}"))
    kb = _back_kb([InlineKeyboardButton(text="✉️ Xabar yozish", callback_data=f"admin_dm:{uid}"), ban_btn],
                  [InlineKeyboardButton(text="🔎 Boshqasini topish", callback_data="admin_find")])
    return text, kb


@router.callback_query(F.data == "admin_find")
async def ask_user_query(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AdminStates.waiting_for_user_query)
    await _edit_or_send(callback, "🔎 Foydalanuvchining <b>Telegram ID</b> raqamini yoki <b>ismini</b> yozing.\n"
                                  "<i>Uning xabarini shu yerga forward qilsangiz ham bo'ladi.</i>", _back_kb())


async def _show_search(message: Message, query: str):
    await activity.flush()
    users = await database.find_users(query)
    if not users:
        await message.answer("❌ Hech kim topilmadi. Boshqa ID yoki ism yozing:", reply_markup=_back_kb())
        return
    if len(users) == 1:
        text, kb = await user_card(users[0]["id"])
        await message.answer(text, parse_mode="HTML", reply_markup=kb)
        return
    rows = [[InlineKeyboardButton(text=f"{u['name'][:30] or 'Ismsiz'} · {u['id']}", callback_data=f"admin_user:{u['id']}")]
            for u in users]
    await message.answer(f"🔎 {len(users)} ta foydalanuvchi topildi:", reply_markup=_back_kb(*rows))


@router.message(AdminStates.waiting_for_user_query)
async def find_user(message: Message, state: FSMContext):
    origin = getattr(message, "forward_origin", None)
    sender = getattr(origin, "sender_user", None)
    if sender:
        query = str(sender.id)
    elif message.text and not message.text.startswith("/"):
        query = message.text
    else:
        await message.answer("ID raqam yoki ism yozing (yoki foydalanuvchi xabarini forward qiling).")
        return
    await state.clear()
    await _show_search(message, query)


@router.message(Command("user"))
async def cmd_user(message: Message, command: CommandObject):
    if not command.args:
        await message.answer("Foydalanish: <code>/user 123456789</code> yoki <code>/user Ism</code>", parse_mode="HTML")
        return
    await _show_search(message, command.args)


@router.callback_query(F.data.startswith("admin_user:"))
async def open_user(callback: CallbackQuery):
    await callback.answer()
    card = await user_card(int(callback.data.split(":", 1)[1]))
    if card:
        await _edit_or_send(callback, *card)


@router.callback_query(F.data.startswith("admin_ban:") | F.data.startswith("admin_unban:"))
async def toggle_ban(callback: CallbackQuery):
    action, uid = callback.data.split(":", 1)
    uid = int(uid)
    if uid == _ADMIN_ID:
        await callback.answer("O'zingizni cheklay olmaysiz 🙂", show_alert=True)
        return
    banned = action == "admin_ban"
    await activity.flush()
    ok = await activity.set_banned(uid, banned)
    await callback.answer(("⛔️ Cheklandi" if banned else "✅ Cheklov olib tashlandi") if ok else "Topilmadi",
                          show_alert=not ok)
    card = await user_card(uid)
    if card:
        await _edit_or_send(callback, *card)


@router.callback_query(F.data.startswith("admin_dm:"))
async def ask_direct_message(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    uid = int(callback.data.split(":", 1)[1])
    await state.set_state(AdminStates.waiting_for_direct_message)
    await state.update_data(dm_user=uid)
    await callback.message.answer(
        f"✉️ <code>{uid}</code> ga yuboriladigan xabarni yozing (matn, rasm yoki fayl).",
        parse_mode="HTML", reply_markup=_back_kb(),
    )


@router.message(AdminStates.waiting_for_direct_message)
async def send_direct_message(message: Message, state: FSMContext, bot: Bot):
    if message.text and message.text.startswith("/"):
        return
    uid = (await state.get_data()).get("dm_user")
    await state.clear()
    try:
        await bot.send_message(chat_id=uid, text="📬 <b>Admin xabari:</b>", parse_mode="HTML")
        await bot.copy_message(chat_id=uid, from_chat_id=message.chat.id, message_id=message.message_id)
        await message.answer("✅ Xabar yetkazildi.", reply_markup=_back_kb(
            [InlineKeyboardButton(text="👤 Foydalanuvchiga qaytish", callback_data=f"admin_user:{uid}")]))
    except TelegramForbiddenError:
        await database.mark_bot_blocked([uid])
        await message.answer("❌ Yetkazilmadi — foydalanuvchi botni bloklagan.", reply_markup=_back_kb())
    except Exception as e:
        await message.answer(f"❌ Yetkazilmadi: {esc(e)}", parse_mode="HTML", reply_markup=_back_kb())


# ── 📥 Excel ro'yxat ───────────────────────────────────────────────────────
def _users_xlsx(users: list[dict]) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    ws = wb.active
    ws.title = "Foydalanuvchilar"
    ws.append(["Telegram ID", "Ism", "Qo'shilgan", "Oxirgi faollik", "Amallar", "Taklif qilgan (ID)",
               "Botni bloklagan", "Admin cheklagan"])
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for u in users:
        ws.append([u["id"], u["name"], u["joined"][:19], u["last_active"][:19], u["usage"],
                   u["referrer_id"] or "", "ha" if u["blocked"] else "", "ha" if u["banned"] else ""])
    for col, width in zip("ABCDEFGH", (14, 30, 20, 20, 10, 18, 15, 15)):
        ws.column_dimensions[col].width = width
    ws.freeze_panes = "A2"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@router.callback_query(F.data == "admin_export")
async def export_users(callback: CallbackQuery):
    await callback.answer("Tayyorlanmoqda...")
    await activity.flush()
    users = await database.export_users()
    data = await asyncio.to_thread(_users_xlsx, users)
    name = f"foydalanuvchilar_{now_tashkent():%Y-%m-%d}.xlsx"
    await callback.message.answer_document(BufferedInputFile(data, filename=name),
                                           caption=f"📥 {len(users)} ta foydalanuvchi")


# ── 🩺 Bot holati ───────────────────────────────────────────────────────────
@router.callback_query(F.data == "admin_health")
async def show_health(callback: CallbackQuery):
    from handlers.scheduler_tools import scheduler
    await callback.answer()
    ai_requests, ai_users = gemini.usage_today()
    jobs = []
    for job in scheduler.get_jobs():
        when = job.next_run_time.strftime("%d.%m %H:%M") if job.next_run_time else "—"
        jobs.append(f"  • {esc(job.id)} — keyingisi {when}")
    text = (
        "🩺 <b>Bot holati</b>\n\n"
        f"📦 Versiya: {botinfo.VERSION} · @{botinfo.username()}\n"
        f"⏱ Ishlayapti: {botinfo.uptime_text()} (oxirgi qayta ishga tushishdan beri)\n"
        f"🗄 Baza: {esc(db.describe())}\n"
        f"🤖 AI: {'yoqilgan' if gemini.is_enabled() else 'o‘chirilgan'} · bugun {ai_requests} so'rov, {ai_users} kishi "
        f"(har biriga kuniga {gemini.daily_limit()} ta)\n"
        f"⏳ Bazaga yozilishi kutilayotgan faollik: {len(activity._pending_users)} kishi\n"
        f"📡 Xabar tarqatish: {'davom etmoqda' if _broadcast['running'] else 'yo‘q'}\n\n"
        "🗓 <b>Rejalashtirilgan ishlar:</b>\n" + ("\n".join(jobs) or "  —")
    )
    await _edit_or_send(callback, text, _back_kb([InlineKeyboardButton(text="🔄 Yangilash", callback_data="admin_health")]))
