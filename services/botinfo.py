"""Bot haqida umumiy ma'lumot: versiya va haqiqiy @username (Telegram'dan olinadi)."""
import os
import time

VERSION = "3.1"
NAME = "smartOffice"
STARTED_AT = time.time()

_username = [os.getenv("BOT_USERNAME", "raqamli_ofis_bot").lstrip("@")]


async def init(bot) -> None:
    """Bot ishga tushganda chaqiriladi: username'ni BOT_USERNAME o'zgaruvchisiga emas, Telegram'ga tayanib oladi."""
    try:
        me = await bot.get_me()
        if me.username:
            _username[0] = me.username
    except Exception:
        pass


def username() -> str:
    return _username[0]


def uptime_text() -> str:
    seconds = int(time.time() - STARTED_AT)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes = seconds // 60
    return (f"{days} kun " if days else "") + f"{hours} soat {minutes} daqiqa"
