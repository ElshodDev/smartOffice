import os
import logging
import google.generativeai as genai
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-3.5-flash')
else:
    model = None

router = Router()

class AIStates(StatesGroup):
    chatting = State()

@router.message(F.text == "🤖 AI Yordamchi (Savol-javob)")
async def start_ai_chat(message: Message, state: FSMContext):
    await state.clear()

    if not model:
        await message.answer(
            "⚠️ <b>AI Yordamchi o'chirilgan!</b>\n\n"
            "Ushbu funksiya ishlashi uchun <code>GEMINI_API_KEY</code> kerak.",
            parse_mode="HTML"
        )
        return

    await message.answer(
        "🤖 <b>Sun'iy Intellekt (Gemini) bilan suhbat</b>\n\n"
        "Mendan bot haqida, hujjatlar bilan ishlash bo'yicha yoki boshqa savollarni so'rashingiz mumkin.\n"
        "<i>Chiqish uchun /cancel yoki boshqa menyu tugmasini bosing.</i>",
        parse_mode="HTML"
    )
    await state.set_state(AIStates.chatting)

@router.message(AIStates.chatting, F.text)
async def process_ai_message(message: Message, state: FSMContext):
    if message.text.startswith('/'):
        return
        
    if not model:
        await message.answer("Iltimos, pastdagi menyudan foydalaning 👇")
        return
        
    msg = await message.answer("✍️ <i>AI o'ylamoqda...</i>", parse_mode="HTML")
    
    bot_context = """
Sen 'Smart Office' Telegram botining rasmiy yordamchisisan.
Sening vazifang - foydalanuvchilarga bot imkoniyatlarini tushuntirish va ofis ishlarida maslahat berish, shuningdek, foydalanuvchilarning turli xil savollariga javob beruvchi do'stona va aqlli sun'iy intellekt bo'lishdir.

Bot imkoniyatlari (bosh menyu bo'limlari):
1. 📁 Hujjatlar bilan ishlash:
   - Excel: qatorlarni qirqish, teng bo'laklarga bo'lish, ustun qiymatlari bo'yicha alohida fayllarga bo'lish, dublikatlarni tozalash, bir nechta faylni birlashtirish, grafik chizish (.xlsx va .xls).
   - PDF: birlashtirish, sahifalarni ajratish, watermark (kirill harflari bilan ham) qo'yish.
   - Word: {{o'zgaruvchi}} li shablonni to'ldirish, Word faylni o'qish va imzo joyiga ism yozish.
   - Obyektivka (ma'lumotnoma): savol-javob orqali PDF yoki Excel formatida tayyorlash.
2. 🔤 Tarjimon va Alifbo: UZ↔EN, UZ↔RU tarjima; Lotin↔Kirill va yangi lotin alifbosiga (ó, ǵ, ş, ç, ñ) o'girish — matn, Word, PDF va .txt fayllar bilan.
3. 📁 Format o'zgartirish: PDF→Word, rasm(lar)→PDF, PDF→rasm (JPG), PDF hajmini kichraytirish, HEIC/WEBP/PNG→JPG.
Botda PDF'ga parol qo'yish va Word'dan PDF'ga o'girish funksiyalari YO'Q — bunday so'rovga botda yo'qligini ayt.

QAT'IY QOIDALAR (GUARDRAILS):
- Foydalanuvchilarning botga aloqador bo'lmagan umumiy savollariga (matematika, tarix, maslahatlar, dasturlash va h.k) ham bemalol javob bera olasan. Javoblaring do'stona, qisqa va foydali bo'lsin.
- Davlat sirlari, shaxsiy ma'lumotlar (PII), yoki noqonuniy harakatlar haqida ma'lumot bermaysan. 
- O'zbek tilida xushmuomala yoz.
"""
    
    try:
        prompt = f"{bot_context}\n\nFoydalanuvchi so'rovi: {message.text}"
        
        response = model.generate_content(prompt)
        answer = response.text
        
        if len(answer) > 4000:
            answer = answer[:4000] + "\n\n...(javob juda uzun)"
            
        # Markdown yulduzchalarini olib tashlaymiz (Telegramda xato bermasligi uchun)
        answer = answer.replace("**", "").replace("*", "")
        await msg.edit_text(answer)
        
    except Exception as e:
        logging.error(f"Gemini API xatosi: {e}")
        await msg.edit_text("❌ Kechirasiz, AIdan javob olishda xatolik yuz berdi. Keyinroq urinib ko'ring.")
