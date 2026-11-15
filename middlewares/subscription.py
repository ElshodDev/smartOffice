import logging
from aiogram import BaseMiddleware, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from cachetools import TTLCache

from config import CHANNEL_ID
from keyboards.inline import get_subscription_menu

logger = logging.getLogger(__name__)

# Obuna bo'lganlar 10 daqiqa eslab qolinadi — har bir xabarda Telegram'dan qayta so'ralmaydi
_subscribed: TTLCache = TTLCache(maxsize=50_000, ttl=600)
_channel_url: list[str] = []


async def check_sub(bot: Bot, user_id: int, use_cache: bool = True) -> bool:
    """Foydalanuvchi kanalga obuna bo'lganmi yoki yo'qligini tekshiradi."""
    if not CHANNEL_ID:
        return True
    if use_cache and user_id in _subscribed:
        return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        ok = member.status in ("member", "administrator", "creator")
    except Exception as e:
        # Agar kanal topilmasa yoki xato bo'lsa — o'tkazib yubormaymiz
        logger.warning(f"Subscription check failed for user={user_id}: {e}")
        return False
    if ok:
        _subscribed[user_id] = True
    return ok


async def channel_url(bot: Bot) -> str:
    """Kanal havolasi (bir marta aniqlanadi). Topilmasa — bo'sh satr (tugma ko'rsatilmaydi)."""
    if _channel_url:
        return _channel_url[0]
    url = ""
    try:
        chat = await bot.get_chat(CHANNEL_ID)
        if chat.username:
            url = f"https://t.me/{chat.username}"
        elif chat.invite_link:
            url = chat.invite_link
    except Exception as e:
        logger.warning(f"Could not get chat info: {e}")
    if not url and str(CHANNEL_ID).startswith("@"):
        url = f"https://t.me/{str(CHANNEL_ID).lstrip('@')}"
    if url:
        _channel_url.append(url)
    return url


async def _send_sub_required(event, channel_url: str):
    """Foydalanuvchiga obuna talab xabarini yuboradi."""
    text_msg = (
        "⛔️ Botdan foydalanish uchun avval kanalimizga obuna bo'ling!\n\n"
        "Obuna bo'lgach, <b>✅ Obunani tekshirish</b> tugmasini bosing."
    )
    kb = get_subscription_menu(channel_url)
    if isinstance(event, Message):
        await event.answer(text_msg, reply_markup=kb, parse_mode="HTML")
    elif isinstance(event, CallbackQuery):
        await event.message.answer(text_msg, reply_markup=kb, parse_mode="HTML")
        await event.answer("Iltimos, avval kanalga obuna bo'ling!", show_alert=True)


class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        # CHANNEL_ID sozlanmagan bo'lsa — hamma o'tib ketadi
        if not CHANNEL_ID:
            return await handler(event, data)

        bot: Bot = data.get("bot")

        # event turini va user_id ni aniqlaymiz
        if isinstance(event, Message):
            user_id = event.from_user.id
            text = event.text or ""
            # /start va /cancel buyruqlarini o'tkazib yuboramiz
            if text.startswith("/start") or text.startswith("/cancel"):
                return await handler(event, data)

        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            # "Obunani tekshirish" tugmasini o'tkazib yuboramiz
            if event.data == "check_subscription":
                return await handler(event, data)
        else:
            # Boshqa event turlari (EditedMessage va h.k.) o'tkazib yuboriladi
            return await handler(event, data)

        # Obuna tekshiruvi
        is_subscribed = await check_sub(bot, user_id)

        if not is_subscribed:
            await _send_sub_required(event, await channel_url(bot))
            # Handler ga o'tmaymiz (bloklaymiz)
            return

        # Obuna bo'lgan — davom etamiz
        return await handler(event, data)
