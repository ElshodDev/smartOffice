import html
import logging
from aiogram import Router, Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from config import ADMIN_ID
from services.database import get_due_reminders, mark_reminder_done
from services.timeutil import now_tashkent, DB_FORMAT
from services.alphabet import esc as uesc, raw

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
    """Har kuni soat 09:00 da adminga kechagi kun statistikasini yuboradi."""
    if not ADMIN_ID:
        return
    try:
        from datetime import timedelta
        from services import activity, database
        await activity.flush()
        now = now_tashkent()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday = today - timedelta(days=1)
        week = today - timedelta(days=7)
        fmt = DB_FORMAT
        total = (await database.admin_stats(today.strftime(fmt), week.strftime(fmt), week.strftime(fmt)))["total"]
        y = await database.admin_stats(yesterday.strftime(fmt), week.strftime(fmt), week.strftime(fmt))
        # "kecha" = kecha 00:00 dan hozirgacha; bugun ertalabgacha bo'lgan qism juda kichik
        sections = await database.top_sections(since=yesterday.strftime(fmt), limit=3)
        top = "\n".join(f"  {i}. {activity.SECTION_TITLES.get(sec, sec)} — {users} kishi"
                         for i, (sec, users, _) in enumerate(sections, 1)) or "  —"
        await bot.send_message(
            chat_id=int(ADMIN_ID),
            text=(
                f"☀️ <b>Kunlik hisobot</b> · {yesterday:%d.%m.%Y}\n\n"
                f"👥 Jami foydalanuvchilar: <b>{total}</b>\n"
                f"🆕 Kecha qo'shildi: <b>{y['new_day']}</b>\n"
                f"🔥 Kecha faol bo'ldi: <b>{y['active_day']}</b>\n"
                f"📅 7 kunda faol: <b>{y['active_week']}</b>\n\n"
                f"🏆 Kechagi eng mashhur bo'limlar:\n{top}\n\n"
                f"<i>Batafsil: /admin → 📊 Statistika</i>"
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logging.error(f"Scheduler error (daily report): {e}")


async def flush_activity():
    from services import activity
    await activity.flush()


# ──────────────────────────────────────────────
# FOYDALANUVCHILAR UCHUN BIR MARTALIK ESLATMALAR
# ──────────────────────────────────────────────
async def check_reminders(bot: Bot):
    """Har daqiqada bazadan vaqti kelgan eslatmalarni tekshiradi."""
    try:
        reminders = await get_due_reminders(now_tashkent().strftime(DB_FORMAT))
        for rem_id, u_id, text in reminders:
            try:
                await bot.send_message(
                    chat_id=u_id,
                    text=f"⏰ <b>ESLATMA!</b>\n\n{uesc(text)}",
                    parse_mode="HTML"
                )
                await mark_reminder_done(rem_id)
            except (TelegramForbiddenError, TelegramBadRequest) as e:
                # Foydalanuvchi botni bloklagan / chat yo'q — qayta urinish foydasiz, har daqiqa logni to'ldirmasin
                logging.warning(f"Eslatma {rem_id} yuborilmadi va yopildi (user: {u_id}): {e}")
                await mark_reminder_done(rem_id)
            except Exception as e:  # tarmoq xatosi — keyingi daqiqada qayta urinadi
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

    # 3. Foydalanuvchi faolligini bazaga yozish (faqat yangi narsa bo'lsa — baza bo'sh vaqtda uxlaydi)
    scheduler.add_job(flush_activity, "interval", seconds=60, id="flush_activity", replace_existing=True)
