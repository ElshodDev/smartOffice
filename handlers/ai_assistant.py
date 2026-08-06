import os
import logging
import google.generativeai as genai
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
from services.subscription import is_premium

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    # Eng yangi va tezkor Gemini modeli (hozirgi versiyalarga mos)
    model = genai.GenerativeModel('gemini-flash-latest')
else:
    model = None

router = Router()

class AIStates(StatesGroup):
    chatting = State()

@router.message(F.text == "🤖 AI Yordamchi")
async def start_ai_chat(message: Message, state: FSMContext):
    await state.clear()

    # Premium tekshiruv
    premium = await is_premium(message.from_user.id)
    if not premium:
        await message.answer(
            "🤖 <b>AI Yordamchi — Premium xizmat</b>\n\n"
            "Bu funksiya faqat <b>Premium</b> foydalanuvchilar uchun mavjud.\n\n"
            "💳 Premium olish uchun asosiy menyudagi <b>\"💳 Premium\"</b> tugmasini bosing.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="💳 Premium olish", callback_data="go_premium")
            ]])
        )
        return

    if not model:
        await message.answer(
            "⚠️ <b>AI Yordamchi o'chirilgan!</b>\n\n"
            "Ushbu funksiya ishlashi uchun <code>GEMINI_API_KEY</code> kiritilishi kerak.\n"
            "Key oling: https://aistudio.google.com/",
            parse_mode="HTML"
        )
        return

    await message.answer(
        "🤖 <b>Sun'iy Intellekt (Gemini) bilan suhbat</b>\n\n"
        "Menga istalgan savolingizni bering yoki matn yozing.\n"
        "<i>Chiqish uchun /cancel yoki boshqa menyu tugmasini bosing.</i>",
        parse_mode="HTML"
    )
    await state.set_state(AIStates.chatting)

@router.message(AIStates.chatting, F.text)
async def process_ai_message(message: Message, state: FSMContext):
    # Komandalarni va menyu tugmalarini ushlamasligi uchun tekshiramiz
    if message.text.startswith('/'):
        return
        
    if not model:
        # Agar AI yoqilmagan bo'lsa, oddiy xabar qaytaramiz
        await message.answer("Iltimos, pastdagi menyudan foydalaning 👇")
        return
        
    msg = await message.answer("✍️ <i>AI o'ylamoqda...</i>", parse_mode="HTML")
    
    try:
        prompt = f"Sen 'Smart Office' Telegram botining rasmiy yordamchisisan. Qisqa, aniq va foydali javob ber. O'zbek tilida yoz. Foydalanuvchi so'rovi: {message.text}"
        
        response = model.generate_content(prompt)
        answer = response.text
        
        if len(answer) > 4000:
            answer = answer[:4000] + "\n\n...(javob juda uzun)"
            
        await msg.edit_text(answer, parse_mode="Markdown")
        
    except Exception as e:
        logging.error(f"Gemini API xatosi: {e}")
        await msg.edit_text("❌ Kechirasiz, AIdan javob olishda xatolik yuz berdi. Keyinroq urinib ko'ring.")
