from aiogram import BaseMiddleware
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from typing import Callable, Dict, Any, Awaitable
from services.database import increment_usage

AD_INTERVAL = 15

class AdsMiddleware(BaseMiddleware):
    """
    Foydalanuvchining botdan foydalanishini sanaydi va har AD_INTERVAL
    marta xabar yozganida bitta reklama (banner) chiqaradi.
    """
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        
        # Asosiy xabarni o'tkazib yuboramiz (handler ishlashi uchun)
        result = await handler(event, data)

        # Agar bu chat xabari bo'lsa va bot yoki command bo'lmasa
        if isinstance(event, Message) and event.text and not event.text.startswith('/'):
            user_id = event.from_user.id
            usage = await increment_usage(user_id)

            if usage > 0 and usage % AD_INTERVAL == 0:
                ad_text = (
                    "💡 <b>Kichik Eslatma</b>\n\n"
                    "Ushbu bot sizga foyda keltiryaptimi? O'z biznesingiz yoki loyihangiz "
                    "uchun shunday aqlli botlar yaratishni xohlasangiz, dasturchiga murojaat qiling!\n\n"
                    "👇 <i>Menyudan '🛒 Xizmatlarim' tugmasi orqali to'liq ma'lumot olishingiz mumkin.</i>"
                )
                await event.answer(
                    ad_text, 
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="📞 Dasturchi bilan aloqa", url="https://t.me/Elshod_Developer")
                    ]])
                )

        return result
