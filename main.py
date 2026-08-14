import asyncio
import logging
import sys
import os
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeDefault, MenuButtonCommands
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
    form_filler,
    report_generator,
    promotion,
)
from handlers.scheduler_tools import start_scheduler, stop_scheduler, setup_daily_job
from middlewares.state_clear import StateClearMiddleware
from middlewares.throttling import ThrottlingMiddleware
from middlewares.subscription import SubscriptionMiddleware
from services.database import create_table, get_users_count, get_recent_users, get_user_profile
from config import ADMIN_ID
from services.image_editor import serve_form_image, serve_form_editor, receive_edited_form, set_bot

async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def api_stats(request: web.Request):
    try:
        user_id_str = request.query.get("user_id", "")
        if user_id_str != str(ADMIN_ID):
            return web.json_response({"error": "Unauthorized"}, status=403)
        
        count = await get_users_count()
        recent = await get_recent_users(200)
        return web.json_response({"count": count, "users": recent})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def api_me(request: web.Request):
    """Foydalanuvchining o'z profil ma'lumotlari"""
    try:
        user_id_str = request.query.get("user_id", "")
        if not user_id_str or not user_id_str.isdigit():
            return web.json_response({"error": "user_id required"}, status=400)
        user_id = int(user_id_str)
        profile = await get_user_profile(user_id)
        if not profile:
            return web.json_response({"error": "not found"}, status=404)
        total = await get_users_count()
        return web.json_response({"profile": profile, "total_users": total})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def index(request):
    return web.FileResponse('./webapp/index.html')

async def start_dummy_server(bot):
    app = web.Application()
    app.router.add_get("/ping", handle_ping)
    app.router.add_get("/api/stats", api_stats)
    app.router.add_get("/api/me", api_me)
    app.router.add_get("/", index)
    app.router.add_get("/form-editor", serve_form_editor)
    app.router.add_get("/forms/{filename}", serve_form_image)
    app.router.add_post("/api/form/save", receive_edited_form)
    app.router.add_static('/static', path='./webapp', name='webapp')
    
    port = int(os.environ.get("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"Web server started on port {port}")


async def main():
    if not BOT_TOKEN:
        logging.error("BOT_TOKEN is missing in the environment variables.")
        return

    # Ma'lumotlar bazasini ishga tushirish
    await create_table()

    bot = Bot(token=BOT_TOKEN)
    dp  = Dispatcher()

    # ── Bot buyruqlari va menyu tugmasi ─────────────────────
    # Yangi foydalanuvchilar "/" bosishi bilan ro'yxat chiqadi
    await bot.set_my_commands([
        BotCommand(command="start", description="Botni ishga tushirish / Bosh menyu"),
        BotCommand(command="cancel", description="Joriy amalni bekor qilish"),
    ], scope=BotCommandScopeDefault())
    # Menu tugmasini "Buyruqlar" rejimiga o'tkazamiz
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())

    # ── Middlewarelar ────────────────────────────────
    # 1. Anti-Spam: tez-tez xabar yuborishni cheklash
    dp.message.middleware(ThrottlingMiddleware())
    # 2. Kanalga a'zolikni tekshirish (majburiy obuna)
    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())
    # 3. State Clear: asosiy menyu tugmalarida qotib qolmaslik
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
    dp.include_router(form_filler.router)
    dp.include_router(report_generator.router)
    dp.include_router(promotion.router)
    # ── AI OXIRIDA — boshqa hech narsa bo'lmasa javob beradi ──
    dp.include_router(ai_assistant.router)

    # ── Schedulerni ishga tushirish ─────────────────
    start_scheduler()
    setup_daily_job(bot)

    logging.info("Bot ishga tushmoqda...")
    await bot.delete_webhook(drop_pending_updates=True)

    # ── Web serverga bot reference qo'yish ──
    set_bot(bot)

    try:
        await start_dummy_server(bot)
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
