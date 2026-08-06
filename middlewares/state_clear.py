import logging
from aiogram import BaseMiddleware
from aiogram.types import Message

MAIN_BUTTONS = {
    # Yangi 8 ta asosiy menyu tugmalari
    "📊 Excel Asboblari",
    "📄 PDF Asboblari",
    "📝 Word & Matn",
    "🔄 Tarjimon & Konvertor",
    "🧰 Qulay Vositalar",
    "🤖 AI Yordamchi",
    "⏰ Eslatmalar",
    "⚙️ Sozlamalar",
    "✍️ Ariza & Imzo",
    "📱 Mini Ilova",
    "📞 Admin / Buyurtma"
}

class StateClearMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        # Agar foydalanuvchi asosiy menyudagi tugmalardan birini bossa
        if hasattr(event, "text") and event.text in MAIN_BUTTONS:
            state = data.get("state")
            if state:
                # Barcha eski FSM jarayonlarini tozalaymiz
                await state.clear()
                
        # Jarayonni asil handlerlarga o'tkazamiz
        return await handler(event, data)
