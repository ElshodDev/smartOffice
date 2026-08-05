import logging
from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from config import ADMIN_ID

router = Router()

class FeedbackStates(StatesGroup):
    waiting_for_feedback = State()

@router.message(F.text == "📞 Adminga murojaat")
async def start_feedback(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Adminga yozmoqchi bo'lgan murojaatingizni yuboring.\n\n"
        "📝 Iltimos, savolingiz yoki taklifingizni batafsil yozing:"
    )
    await state.set_state(FeedbackStates.waiting_for_feedback)

@router.message(FeedbackStates.waiting_for_feedback, F.text)
async def process_feedback(message: Message, state: FSMContext, bot: Bot):
    if not ADMIN_ID:
        await message.answer("Kechirasiz, hozirda admin bilan bog'lanish imkoni yo'q.")
        await state.clear()
        return

    user = message.from_user
    user_info = (
        f"👤 <b>Foydalanuvchi:</b> {user.full_name}\n"
        f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
        f"📱 <b>Username:</b> @{user.username or 'Yoq'}\n\n"
        f"📩 <b>Murojaat:</b>\n{message.text}"
    )

    try:
        admin_id = int(ADMIN_ID)
        
        # Adminga xabarni yuborish, reply_parameters orqali user_id ni meta sifatida yozib qo'yamiz
        # Admin ushbu xabarga "Reply" qilganda, bot uni foydalanuvchiga yo'naltiradi
        sent = await bot.send_message(
            chat_id=admin_id,
            text=user_info + f"\n\n<i>💬 Javob berish uchun ushbu xabarga <b>Reply</b> qiling.</i>",
            parse_mode="HTML"
        )

        # FSM da foydalanuvchi ID va admin ga yuborilgan xabar IDni saqlaymiz
        # (admin Reply qilganda bu orqali topamiz)
        await state.update_data(
            admin_message_id=sent.message_id,
            user_id=user.id
        )

        await message.answer(
            "✅ Murojaatingiz adminga yuborildi!\n\n"
            "Admin eng yaqin vaqtda javob qaytaradi. Asosiy menyuga qaytishingiz mumkin."
        )
    except Exception as e:
        logging.error(f"Adminga xabar yuborishda xato: {e}")
        await message.answer("Xatolik yuz berdi. Keyinroq urinib ko'ring.")
    finally:
        await state.clear()

# ─────────────────────────────────────────────
# Admin Reply qilganda foydalanuvchiga javob jo'natish
# ─────────────────────────────────────────────
@router.message(F.reply_to_message & F.chat.func(lambda chat: str(chat.id) == str(ADMIN_ID).lstrip("@")) )
async def admin_reply_to_user(message: Message, bot: Bot):
    """
    Admin o'z chatida bot xabariga Reply qilganda,
    bot o'sha foydalanuvchini topib javob uzatadi.
    Bu mantiq adminning shaxsiy chatida bot bilan ishlaydi.
    """
    replied_text = message.reply_to_message.text or ""

    # Xabardan user ID ni parse qilamiz (yuqorida yozilgan user_info formatiga mos)
    user_id = None
    for line in replied_text.splitlines():
        if "🆔" in line and "ID:" in line:
            try:
                # "<b>ID:</b> <code>123456789</code>" yoki "🆔 ID: 123456789"
                parts = line.split(":")
                raw_id = parts[-1].strip().replace("<code>", "").replace("</code>", "").strip()
                user_id = int(raw_id)
            except (ValueError, IndexError):
                pass

    if not user_id:
        await message.reply("⚠️ Foydalanuvchi ID topilmadi. Foydalanuvchi xabarini to'g'ri Reply qiling.")
        return

    try:
        await bot.send_message(
            chat_id=user_id,
            text=f"📬 <b>Admin javobi:</b>\n\n{message.text}",
            parse_mode="HTML"
        )
        await message.react([{"type": "emoji", "emoji": "✅"}])
    except Exception as e:
        logging.error(f"Foydalanuvchiga javob yuborishda xato: {e}")
        await message.reply(f"❌ Javob yuborib bo'lmadi. Foydalanuvchi bilan aloqa uzilgan bo'lishi mumkin.\nXato: {e}")
