import asyncio
import logging
import sys
import os
from aiohttp import web

from aiogram import Bot, Dispatcher
from config import BOT_TOKEN
from handlers import (
    start,
    admin,
    # ── Hub handlerlari (asosiy menyu) ──
    excel_hub,
    word_hub,
    converter_hub,
    tools_hub,
    # ── Funksional handlerlari ──
    excel_tools,
    excel_utils,
    smart_splitter,
    category_splitter,
    converter,
    format_converter,
    word_tools,
    ocr_tools,
    utility_tools,
    search_data,
    pdf_tools,
    reminders,
    ai_assistant,
    settings,
    scheduler_tools,
)
from handlers.scheduler_tools import start_scheduler, stop_scheduler, setup_daily_job
from middlewares.state_clear import StateClearMiddleware
from middlewares.throttling import ThrottlingMiddleware
from services.database import create_table

async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def index(request):
    return web.FileResponse('./webapp/index.html')

async def start_dummy_server():
    app = web.Application()
    app.router.add_get("/ping", handle_ping)
    app.router.add_get("/", index)
    app.router.add_static('/', path='./webapp', name='webapp')
    
    port = int(os.environ.get("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"Dummy web server started on port {port}")


async def main():
    if not BOT_TOKEN:
        logging.error("BOT_TOKEN is missing in the environment variables.")
        return

    # Ma'lumotlar bazasini ishga tushirish
    await create_table()

    bot = Bot(token=BOT_TOKEN)
    dp  = Dispatcher()

    # ── Middlewarelar ────────────────────────────────
    # 1. Anti-Spam: tez-tez xabar yuborishni cheklash
    dp.message.middleware(ThrottlingMiddleware())
    # 2. State Clear: asosiy menyu tugmalarida qotib qolmaslik
    dp.message.middleware(StateClearMiddleware())

    # ── Ro'yxatdan o'tkazish (Routers) ──────────────
    dp.include_router(start.router)
    dp.include_router(admin.router)
    # ── Hub routerlari (asosiy menyu kategoriyalari) ──
    dp.include_router(excel_hub.router)
    dp.include_router(word_hub.router)
    dp.include_router(converter_hub.router)
    dp.include_router(tools_hub.router)
    # ── Funksional routerlar (hub ichidan chaqiriladi) ──
    dp.include_router(excel_tools.router)
    dp.include_router(excel_utils.router)
    dp.include_router(smart_splitter.router)
    dp.include_router(category_splitter.router)
    dp.include_router(converter.router)
    dp.include_router(format_converter.router)
    dp.include_router(word_tools.router)
    dp.include_router(ocr_tools.router)
    dp.include_router(utility_tools.router)
    dp.include_router(search_data.router)
    dp.include_router(pdf_tools.router)
    dp.include_router(reminders.router)
    dp.include_router(settings.router)
    dp.include_router(scheduler_tools.router)
    # ── AI OXIRIDA — boshqa hech narsa bo'lmasa javob beradi ──
    dp.include_router(ai_assistant.router)

    # ── Schedulerni ishga tushirish ─────────────────
    start_scheduler()
    setup_daily_job(bot)

    logging.info("Bot ishga tushmoqda...")
    await bot.delete_webhook(drop_pending_updates=True)

    try:
        await start_dummy_server()
        await dp.start_polling(bot)
    finally:
        stop_scheduler()
        logging.info("Bot to'xtatildi!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
