"""
Toshkent vaqti bilan ishlash. Render serveri UTC'da ishlaydi, foydalanuvchilar esa Toshkent
vaqtini yozadi — shuning uchun hamma joyda aniq vaqt mintaqasi ishlatiladi.
"""
import datetime as dt
import re
from zoneinfo import ZoneInfo

TASHKENT = ZoneInfo("Asia/Tashkent")
DB_FORMAT = "%Y-%m-%d %H:%M:%S"
SHOW_FORMAT = "%d.%m.%Y %H:%M"


def now_tashkent() -> dt.datetime:
    """Toshkent vaqti (vaqt mintaqasisiz, bazaga yozish uchun)."""
    return dt.datetime.now(TASHKENT).replace(tzinfo=None, microsecond=0)


def parse_user_time(text: str, now: dt.datetime | None = None) -> dt.datetime | None:
    """
    Foydalanuvchi yozgan vaqtni tushunadi:
      15:30 / 15.30            — bugun (o'tib ketgan bo'lsa ertaga)
      ertaga 9:00              — ertaga
      20.11.2026 15:30         — sana bilan (O'zbekistonda odatiy ko'rinish)
      20.11 15:30              — joriy yil (o'tgan bo'lsa keyingi yil)
      2026-11-20 15:30         — ISO ko'rinish
    Tushunilmasa None.
    """
    now = now or now_tashkent()
    text = " ".join(text.strip().lower().split())

    def hm(h, m):
        h, m = int(h), int(m)
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError
        return h, m

    try:
        if match := re.fullmatch(r"(ertaga|bugun|indinga)\s+(\d{1,2})[:.](\d{2})", text):
            h, m = hm(match.group(2), match.group(3))
            days = {"bugun": 0, "ertaga": 1, "indinga": 2}[match.group(1)]
            return (now + dt.timedelta(days=days)).replace(hour=h, minute=m, second=0)
        if match := re.fullmatch(r"(\d{1,2})[:.](\d{2})", text):
            h, m = hm(match.group(1), match.group(2))
            target = now.replace(hour=h, minute=m, second=0)
            return target if target > now else target + dt.timedelta(days=1)
        if match := re.fullmatch(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})\s+(\d{1,2})[:.](\d{2})", text):
            h, m = hm(match.group(4), match.group(5))
            return dt.datetime(int(match.group(3)), int(match.group(2)), int(match.group(1)), h, m)
        if match := re.fullmatch(r"(\d{1,2})[./](\d{1,2})\s+(\d{1,2})[:.](\d{2})", text):
            h, m = hm(match.group(3), match.group(4))
            target = dt.datetime(now.year, int(match.group(2)), int(match.group(1)), h, m)
            return target if target > now else target.replace(year=now.year + 1)
        if match := re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{2})", text):
            h, m = hm(match.group(4), match.group(5))
            return dt.datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)), h, m)
    except ValueError:  # 31.02, 25:00 kabi mavjud bo'lmagan sana/vaqt
        return None
    return None
