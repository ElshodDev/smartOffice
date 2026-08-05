import logging
from datetime import datetime
from aiogram import Router, Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from config import ADMIN_ID
from services.database import get_due_reminders, mark_reminder_done

router = Router()
scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")

# ──────────────────────────────────────────────
# SCHEDULER ISHGA TUSHIRISH / TO'XTATISH
# ──────────────────────────────────────────────
def start_scheduler():
    if not scheduler.running:
        scheduler.start()
        logging.info("✅ APScheduler ishga tushdi (Asia/Tashkent).")

def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logging.info("APScheduler to'xtatildi.")

# ──────────────────────────────────────────────
# KUNLIK AVTOMATIK XABAR (admin uchun namuna)
# ──────────────────────────────────────────────
async def daily_report(bot: Bot):
    """Har kuni soat 09:00 da adminga avtomatik xabar yuboradi."""
    if not ADMIN_ID:
        return
    try:
        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        await bot.send_message(
            chat_id=int(ADMIN_ID),
            text=(
                f"☀️ <b>Kunlik eslatma</b>\n"
                f"Sana: <code>{now}</code>\n\n"
                f"<i>smartOffice bot faol va ishlamoqda.</i>\n"
                f"Yaxshi ish kuni tilaymiz! 🚀"
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Scheduler error (daily report): {e}")

# ──────────────────────────────────────────────
# FOYDALANUVCHILAR UCHUN BIR MARTALIK ESLATMALAR
# ──────────────────────────────────────────────
async def check_reminders(bot: Bot):
    """Har daqiqada bazadan vaqti kelgan eslatmalarni tekshiradi."""
    try:
        reminders = await get_due_reminders()
        for rem_id, u_id, text in reminders:
            try:
                await bot.send_message(
                    chat_id=u_id, 
                    text=f"⏰ <b>ESLATMA!</b>\n\n{text}", 
                    parse_mode="HTML"
                )
                await mark_reminder_done(rem_id)
            except Exception as e:
                logging.error(f"Eslatma yuborishda xato (user: {u_id}): {e}")
    except Exception as e:
        logging.error(f"Check reminders xatosi: {e}")

def setup_daily_job(bot: Bot):
    """Barcha rejalashtirilgan vazifalarni schedulerga qo'shish."""
    # 1. Kunlik hisobot (Ertalab 09:00)
    scheduler.add_job(
        daily_report,
        trigger=CronTrigger(hour=9, minute=0),
        kwargs={"bot": bot},
        id="daily_report",
        replace_existing=True
    )
    logging.info("Kunlik xabar jadvali sozlandi: har kuni 09:00 (Toshkent).")
    
    # 2. Shaxsiy eslatmalarni tekshirish (Har daqiqada)
    scheduler.add_job(
        check_reminders,
        'cron',
        minute='*',
        kwargs={"bot": bot},
        id="check_reminders",
        replace_existing=True
    )
    logging.info("Shaxsiy eslatmalarni tekshirish jadvali sozlandi: har daqiqada.")
