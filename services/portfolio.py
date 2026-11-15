"""
💻 Muallifning loyihalari (portfolio) va buyurtma turlari.

Yangi loyiha qo'shish yoki tavsifni o'zgartirish uchun faqat PROJECTS ro'yxatini tahrirlang.
Havolalar bot serveri orqali ochiladi (/p/KALIT) — admin statistikasida qaysi loyiha nechta
odam tomonidan ochilgani ko'rinadi.
"""
from config import RENDER_URL

# (kalit, belgi, nomi, sayt, tavsif)
PROJECTS: list[tuple[str, str, str, str, str]] = [
    ("fluentuz", "🗣", "FluentUz", "https://fluentuz.app/", "Ingliz tilini o'rganish platformasi"),
    ("mulkchi", "🏠", "Mulkchi", "https://mulkchi.vercel.app/", "Ko'chmas mulk e'lonlari platformasi"),
    ("elshod", "👨‍💻", "elshod.me", "https://elshod.me/", "Muallifning shaxsiy sayti: barcha loyihalar va aloqa"),
]
PROJECT_URLS = {key: url for key, _, _, url, _ in PROJECTS}

# Buyurtma turlari: (kalit, tugma matni)
ORDER_TYPES: list[tuple[str, str]] = [
    ("bot", "🤖 Telegram bot"),
    ("site", "🌐 Veb-sayt"),
    ("app", "📱 Mobil ilova / Web ilova"),
    ("auto", "⚙️ Ish jarayonini avtomatlashtirish"),
    ("other", "💡 Boshqa"),
]
ORDER_TITLES = dict(ORDER_TYPES)


def tracked_url(key: str, user_id: int | None = None) -> str:
    """Loyiha havolasi bot serveri orqali: kim ochganini hisoblaydi, keyin saytga yo'naltiradi."""
    base = f"{RENDER_URL.rstrip('/')}/p/{key}"
    return f"{base}?u={user_id}" if user_id else base
