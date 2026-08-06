from aiogram import BaseMiddleware, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from config import CHANNEL_ID
from keyboards.inline import get_subscription_menu

async def check_sub(bot: Bot, user_id: int) -> bool:
    if not CHANNEL_ID:
        return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except TelegramBadRequest:
        return False

class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        bot: Bot = data.get("bot")
        
        # Check if the event is a Message or CallbackQuery
        if isinstance(event, Message):
            user_id = event.from_user.id
            text = event.text or ""
            # Allow /start command to pass through
            if text.startswith("/start"):
                return await handler(event, data)
                
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            # Allow the check_subscription button to pass through
            if event.data == "check_subscription":
                return await handler(event, data)
        else:
            return await handler(event, data)

        # Check subscription status
        is_subscribed = await check_sub(bot, user_id)
        if not is_subscribed:
            try:
                chat = await bot.get_chat(CHANNEL_ID)
                channel_url = chat.invite_link or f"https://t.me/{chat.username}" if chat.username else ""
            except Exception:
                channel_url = "https://t.me/your_channel_username"
                
            text_msg = "Botdan foydalanishni davom ettirish uchun iltimos, kanalimizga obuna bo'ling!"
            
            if isinstance(event, Message):
                await event.answer(text_msg, reply_markup=get_subscription_menu(channel_url))
            elif isinstance(event, CallbackQuery):
                await event.message.answer(text_msg, reply_markup=get_subscription_menu(channel_url))
                await event.answer()
                
            # Stop propagation
            return
            
        return await handler(event, data)
