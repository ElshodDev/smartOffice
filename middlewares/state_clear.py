import logging
from aiogram import BaseMiddleware
from aiogram.types import Message

MAIN_BUTTONS = {
    "📊 Excel bilan ishlash",
    "📄 PDF bilan ishlash",
    "📝 Word bilan ishlash",
    "🔄 Format o'zgartirish va Tarjima",
    "📁 Hujjatlar bilan ishlash",
    "🔤 Tarjimon va Alifbo",
    "📁 Format o'zgartirish",
    "🔄 Formatlar va Tarjima",
    "👤 Profil va Sozlamalar",
    "🛠 Boshqa qulayliklar",
    "🤖 AI Yordamchi (Savol-javob)",
    "⏰ Eslatmalar",
    "⚙️ Sozlamalar",
    "📝 Ariza To'ldirish",
    "📋 Ma'lumotnoma (Obyektivka)",
    "📞 Admin / Buyurtma",
    "🔗 Do'stlarga ulashish",
    "🛒 Xizmatlarim",
    "🌐 Web Ilova",
    "/start"
}

class StateClearMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if hasattr(event, "text") and event.text in MAIN_BUTTONS:
            state = data.get("state")
            if state:
                await state.clear()
                
        return await handler(event, data)
