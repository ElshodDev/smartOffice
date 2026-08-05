from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
import datetime
from services.database import add_reminder

router = Router()

class ReminderStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_time = State()

def get_reminders_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Yangi eslatma qo'shish", callback_data="add_reminder")],
    ])

@router.message(F.text == "⏰ Eslatmalar")
async def show_reminders(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "⏰ <b>Shaxsiy Eslatmalar</b>\n\nBu yerda siz muhim vazifalarni yozib qo'yishingiz mumkin. Vaqti kelganda bot sizga xabar beradi.",
        parse_mode="HTML",
        reply_markup=get_reminders_menu()
    )

@router.callback_query(F.data == "add_reminder")
async def ask_reminder_text(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text("Yozib qoldirmoqchi bo'lgan eslatmangiz (matni) ni kiriting:")
    await state.set_state(ReminderStates.waiting_for_text)

@router.message(ReminderStates.waiting_for_text, F.text)
async def ask_reminder_time(message: Message, state: FSMContext):
    await state.update_data(reminder_text=message.text)
    await message.answer(
        "Qachon eslatishim kerak?\n\n"
        "Vaqtni shu formatda kiriting: <b>YYYY-MM-DD HH:MM</b>\n"
        "Masalan: <b>2024-12-31 15:30</b> yoki bugun uchun faqat <b>HH:MM</b>",
        parse_mode="HTML"
    )
    await state.set_state(ReminderStates.waiting_for_time)

@router.message(ReminderStates.waiting_for_time, F.text)
async def save_reminder(message: Message, state: FSMContext):
    time_str = message.text.strip()
    now = datetime.datetime.now()
    
    # Faqat soat yozilsa bugungi kunga qabul qilamiz
    if len(time_str) == 5 and ":" in time_str:
        try:
            h, m = map(int, time_str.split(":"))
            target_time = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if target_time < now:
                # Agar vaqt o'tib ketgan bo'lsa (masalan ertalabki vaqtni kechqurun yozsa) ertaga o'tkazamiz
                target_time += datetime.timedelta(days=1)
            time_str = target_time.strftime("%Y-%m-%d %H:%M:%S")
        except:
            return await message.answer("❌ Vaqt noto'g'ri kiritildi. HH:MM formatida yozing (masalan, 15:30).")
    else:
        try:
            # YYYY-MM-DD HH:MM
            dt = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M")
            time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            return await message.answer("❌ Vaqt noto'g'ri kiritildi. YYYY-MM-DD HH:MM formatida yozing (masalan, 2024-12-31 15:30).")

    data = await state.get_data()
    text = data.get("reminder_text")
    
    await add_reminder(message.from_user.id, text, time_str)
    await message.answer(f"✅ <b>Eslatma saqlandi!</b>\n\nSizga bu haqida <b>{time_str}</b> da xabar beraman.", parse_mode="HTML")
    await state.clear()
