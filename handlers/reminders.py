"""⏰ Shaxsiy eslatmalar: qo'shish, ro'yxatini ko'rish, o'chirish. Vaqt — Toshkent vaqti."""
import html
from datetime import datetime

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from services.database import add_reminder, get_user_reminders, delete_reminder
from services.timeutil import now_tashkent, parse_user_time, DB_FORMAT, SHOW_FORMAT

router = Router()

MAX_PENDING = 20
MAX_TEXT = 500
MAX_DAYS_AHEAD = 366


class ReminderStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_time = State()


def get_reminders_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Yangi eslatma qo'shish", callback_data="add_reminder")],
        [InlineKeyboardButton(text="📋 Mening eslatmalarim", callback_data="list_reminders")],
    ])


MENU_TEXT = (
    "⏰ <b>Shaxsiy eslatmalar</b>\n\n"
    "Muhim ishni yozib qo'ying — belgilangan vaqtda (Toshkent vaqti bilan) bot sizga xabar beradi."
)


@router.message(F.text == "⏰ Eslatmalar")
async def show_reminders(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(MENU_TEXT, parse_mode="HTML", reply_markup=get_reminders_menu())


@router.callback_query(F.data == "reminders_menu")
async def show_reminders_cb(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(MENU_TEXT, parse_mode="HTML", reply_markup=get_reminders_menu())


@router.callback_query(F.data == "add_reminder")
async def ask_reminder_text(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if len(await get_user_reminders(callback.from_user.id)) >= MAX_PENDING:
        await callback.message.answer(f"⚠️ Sizda {MAX_PENDING} ta faol eslatma bor. Avval keraksizlarini o'chiring.")
        return
    await callback.message.edit_text("✍️ Eslatma matnini yozing:\n<i>Masalan: Hisobotni direktorga topshirish</i>", parse_mode="HTML")
    await state.set_state(ReminderStates.waiting_for_text)


@router.message(ReminderStates.waiting_for_text, F.text)
async def ask_reminder_time(message: Message, state: FSMContext):
    text = message.text.strip()
    if text.startswith("/"):
        return
    if len(text) > MAX_TEXT:
        await message.answer(f"❌ Matn juda uzun. {MAX_TEXT} belgigacha qisqartiring:")
        return
    await state.update_data(reminder_text=text)
    await message.answer(
        "🕒 Qachon eslatay? (Toshkent vaqti)\n\n"
        "<b>Namunalar:</b>\n"
        "<code>15:30</code> — bugun (o'tib ketgan bo'lsa ertaga)\n"
        "<code>ertaga 9:00</code>\n"
        "<code>20.11.2026 15:30</code>",
        parse_mode="HTML",
    )
    await state.set_state(ReminderStates.waiting_for_time)


@router.message(ReminderStates.waiting_for_time, F.text)
async def save_reminder(message: Message, state: FSMContext):
    now = now_tashkent()
    target = parse_user_time(message.text, now)
    if target is None:
        await message.answer(
            "❌ Vaqtni tushunmadim. Masalan: <code>15:30</code>, <code>ertaga 9:00</code> yoki <code>20.11.2026 15:30</code>",
            parse_mode="HTML",
        )
        return
    if target <= now:
        await message.answer(f"❌ Bu vaqt o'tib ketgan (hozir {now:%d.%m.%Y %H:%M}). Kelajakdagi vaqtni kiriting:")
        return
    if (target - now).days > MAX_DAYS_AHEAD:
        await message.answer("❌ Ko'pi bilan 1 yil oldinga eslatma qo'yish mumkin.")
        return

    data = await state.get_data()
    await add_reminder(message.from_user.id, data.get("reminder_text", ""), target.strftime(DB_FORMAT))
    await state.clear()
    await message.answer(
        f"✅ <b>Eslatma saqlandi!</b>\n\n"
        f"📝 {html.escape(data.get('reminder_text', ''))}\n"
        f"🕒 <b>{target.strftime(SHOW_FORMAT)}</b> da eslataman.",
        parse_mode="HTML",
        reply_markup=get_reminders_menu(),
    )


async def _render_list(message: Message, user_id: int):
    items = await get_user_reminders(user_id)
    if not items:
        await message.edit_text("📋 Sizda faol eslatmalar yo'q.", reply_markup=get_reminders_menu())
        return
    lines, buttons = ["📋 <b>Faol eslatmalaringiz:</b>\n"], []
    for number, (rem_id, text, run_date) in enumerate(items, start=1):
        try:
            when = datetime.strptime(run_date, DB_FORMAT).strftime(SHOW_FORMAT)
        except ValueError:
            when = str(run_date)[:16]
        short = text if len(text) <= 60 else text[:59] + "…"
        lines.append(f"{number}. 🕒 <b>{when}</b> — {html.escape(short)}")
        buttons.append([InlineKeyboardButton(text=f"🗑 {number}-ni o'chirish", callback_data=f"rem_del:{rem_id}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="reminders_menu")])
    await message.edit_text("\n".join(lines), parse_mode="HTML",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query(F.data == "list_reminders")
async def list_reminders(callback: CallbackQuery):
    await callback.answer()
    await _render_list(callback.message, callback.from_user.id)


@router.callback_query(F.data.startswith("rem_del:"))
async def remove_reminder(callback: CallbackQuery):
    try:
        rem_id = int(callback.data.split(":", 1)[1])
    except ValueError:
        await callback.answer()
        return
    deleted = await delete_reminder(rem_id, callback.from_user.id)
    await callback.answer("🗑 O'chirildi" if deleted else "Eslatma topilmadi")
    await _render_list(callback.message, callback.from_user.id)
