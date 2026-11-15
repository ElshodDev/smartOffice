import asyncio
import logging
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
from services.database import create_table
from services.image_editor import ImageEditorService
from src.shared.security.http import require_admin, require_webapp_user
from src.shared.logging import configure_logging
from src.shared.settings import get_settings
from src.modules.identity.application.queries import IdentityQueryService
from src.modules.identity.infrastructure.sqlite import SqliteIdentityReadAdapter

app_settings = get_settings()
identity_queries = IdentityQueryService(SqliteIdentityReadAdapter())

async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def api_stats(request: web.Request):
    try:
        require_admin(request, app_settings)
        statistics = await identity_queries.get_admin_statistics()
        return web.json_response(statistics)
    except web.HTTPException:
        raise
    except Exception:
        logging.exception("Failed to load admin statistics")
        return web.json_response({"error": "Internal server error"}, status=500)

async def api_user_profile(request: web.Request):
    """Har bir foydalanuvchining o'z profilini ko'rishi uchun endpoint."""
    try:
        authenticated_user_id = require_webapp_user(request, app_settings)
        profile = await identity_queries.get_own_profile(authenticated_user_id)
        if not profile:
            return web.json_response({"error": "User not found"}, status=404)
        return web.json_response(profile)
    except web.HTTPException:
        raise
    except Exception:
        logging.exception("Failed to load user profile")
        return web.json_response({"error": "Internal server error"}, status=500)


async def index(request):
    return web.FileResponse('./webapp/index.html')

async def start_dummy_server(bot):
    image_editor = ImageEditorService(bot, app_settings)
    app = web.Application(client_max_size=10 * 1024 * 1024)
    app.router.add_get("/ping", handle_ping)
    app.router.add_get("/api/stats", api_stats)
    app.router.add_get("/api/user-profile", api_user_profile)
    app.router.add_get("/", index)
    app.router.add_get("/form-editor", image_editor.serve_form_editor)
    app.router.add_get("/forms/{filename}", image_editor.serve_form_image)
    app.router.add_post("/api/form/save", image_editor.receive_edited_form)
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
    from handlers import documents_hub, profile_hub
    dp.include_router(documents_hub.router)
    dp.include_router(profile_hub.router)
    
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
    dp.include_router(search_data.router)
    dp.include_router(pdf_tools.router)
    dp.include_router(utility_tools.router)
    dp.include_router(reminders.router)
    dp.include_router(promotion.router)
    dp.include_router(settings.router)
    dp.include_router(scheduler_tools.router)
    dp.include_router(form_filler.router)
    dp.include_router(report_generator.router)
    from handlers import doc_generator
    dp.include_router(doc_generator.router)
    from handlers import feedback
    dp.include_router(feedback.router)
    # ── AI OXIRIDA — boshqa hech narsa bo'lmasa javob beradi ──
    dp.include_router(ai_assistant.router)

    # ── Schedulerni ishga tushirish ─────────────────
    start_scheduler()
    setup_daily_job(bot)

    logging.info("Bot ishga tushmoqda...")
    await bot.delete_webhook(drop_pending_updates=True)

    try:
        await start_dummy_server(bot)
        await dp.start_polling(bot)
    finally:
        stop_scheduler()
        logging.info("Bot to'xtatildi!")


if __name__ == "__main__":
    configure_logging()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
