import asyncio
import logging
import os
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault, MenuButtonCommands
from config import BOT_TOKEN
from handlers import (
    start,
    admin,
    # ── Hub handlerlari (asosiy menyu) ──
    excel_hub,
    word_hub,
    converter_hub,
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
from src.shared.logging import configure_logging
from src.shared.settings import get_settings

app_settings = get_settings()

async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def index(request):
    from services.alphabet import load_page
    return web.Response(text=load_page("./webapp/index.html"), content_type="text/html",
                        headers={"Cache-Control": "no-cache"})

async def start_dummy_server(bot):
    image_editor = ImageEditorService(bot, app_settings)
    app = web.Application(client_max_size=10 * 1024 * 1024)
    app.router.add_get("/ping", handle_ping)
    from services import webapp_api
    webapp_api.setup_routes(app)
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


def setup_dispatcher(dp: Dispatcher, bot: Bot) -> None:
    """Middlewarelar va routerlar (testlar ham shu funksiyadan foydalanadi)."""
    import glob
    from handlers import documents_hub, profile_hub, doc_generator, feedback
    from middlewares.activity import ActivityMiddleware, attach_section_tracking
    from services.alphabet import AlphabetInputMiddleware, AlphabetRequestMiddleware, preload_source_strings

    # ── Yangi lotin alifbosi: chiqayotgan xabarlar o'giriladi, bosilgan tugmalar asliga qaytariladi ──
    bot.session.middleware(AlphabetRequestMiddleware())
    preload_source_strings(glob.glob("handlers/*.py") + glob.glob("keyboards/*.py"))
    dp.message.outer_middleware(AlphabetInputMiddleware())
    # ── Faollik: har bir foydalanuvchi bazada saqlanadi; admin cheklaganlar to'xtatiladi ──
    dp.message.outer_middleware(ActivityMiddleware())
    dp.callback_query.outer_middleware(ActivityMiddleware())

    # 1. Anti-Spam: tez-tez xabar yuborishni cheklash (albomlar bitta xabar hisoblanadi)
    dp.message.middleware(ThrottlingMiddleware())
    # 2. Kanalga a'zolikni tekshirish (majburiy obuna)
    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())
    # 3. State Clear: asosiy menyu tugmalarida qotib qolmaslik
    dp.message.middleware(StateClearMiddleware())

    modules = [
        start, admin,
        # ── Hub routerlari (asosiy menyu kategoriyalari) ──
        documents_hub, profile_hub, excel_hub, word_hub, converter_hub,
        # ── Funksional routerlar (hub ichidan chaqiriladi) ──
        excel_tools, excel_utils, smart_splitter, category_splitter, converter, format_converter,
        word_tools, ocr_tools, search_data, pdf_tools, utility_tools, reminders, promotion, settings,
        scheduler_tools, form_filler, report_generator, doc_generator, feedback,
        # ── AI OXIRIDA — boshqa hech narsa bo'lmasa javob beradi ──
        ai_assistant,
    ]
    for module in modules:
        attach_section_tracking(module)     # profil va admin statistikasi uchun bo'limlar hisobi
        dp.include_router(module.router)


async def main():
    if not BOT_TOKEN:
        logging.error("BOT_TOKEN is missing in the environment variables.")
        return

    from config import ADMIN_ID
    from services import activity, botinfo

    # Ma'lumotlar bazasini ishga tushirish
    await create_table()
    await activity.load_banned()

    bot = Bot(token=BOT_TOKEN)
    dp  = Dispatcher()
    setup_dispatcher(dp, bot)
    await botinfo.init(bot)

    # ── Bot buyruqlari va menyu tugmasi ─────────────────────
    # Yangi foydalanuvchilar "/" bosishi bilan ro'yxat chiqadi
    commands = [
        BotCommand(command="start", description="Botni ishga tushirish / Bosh menyu"),
        BotCommand(command="cancel", description="Joriy amalni bekor qilish"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
    if ADMIN_ID:
        try:
            await bot.set_my_commands(commands + [
                BotCommand(command="admin", description="Admin panel"),
                BotCommand(command="stats", description="Statistika"),
                BotCommand(command="user", description="Foydalanuvchini topish: /user ID yoki ism"),
            ], scope=BotCommandScopeChat(chat_id=int(ADMIN_ID)))
        except Exception as e:
            logging.warning(f"Admin buyruqlarini o'rnatib bo'lmadi: {e}")
    # Menu tugmasini "Buyruqlar" rejimiga o'tkazamiz
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())

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
        await activity.flush()
        from services import db
        await db.close()
        logging.info("Bot to'xtatildi!")


if __name__ == "__main__":
    configure_logging()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
