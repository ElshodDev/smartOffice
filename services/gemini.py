"""
Gemini bilan ishlash uchun umumiy xizmat (google-genai SDK).

- Asinxron: javob kutilayotganda bot boshqa foydalanuvchilarga javob berishda davom etadi.
- Model nomi GEMINI_MODEL muhit o'zgaruvchisidan olinadi — Google modelni almashtirsa,
  kodni emas, Render'dagi sozlamani o'zgartirish kifoya.
- Kunlik limit har bir foydalanuvchi uchun alohida (bepul tarifdagi umumiy kvotani bitta
  odam tugatib qo'ymasligi uchun).
"""
import datetime as dt
import logging
import os
from dataclasses import dataclass

DEFAULT_MODEL = "gemini-3.5-flash"
TIMEOUT_MS = 60_000


class AIError(Exception):
    """kind: 'disabled' | 'quota' | 'blocked' | 'unavailable' | 'error'"""

    def __init__(self, kind: str, detail: str = ""):
        super().__init__(f"{kind}: {detail}")
        self.kind = kind


USER_MESSAGES = {
    "disabled": "⚠️ AI yordamchi hozircha o'chirilgan (administrator Gemini kalitini sozlamagan).",
    "quota": "⏳ Bugun AI'ga so'rovlar soni umumiy limitga yetdi. Birozdan keyin yoki ertaga qayta urinib ko'ring.",
    "blocked": "⚠️ Bu so'rovga AI javob bera olmaydi (xavfsizlik filtri). Savolni boshqacha ifodalab ko'ring.",
    "unavailable": "⏳ AI xizmati hozir band yoki javob bermayapti. Bir daqiqadan keyin qayta urinib ko'ring.",
    "error": "❌ AI'dan javob olishda xatolik yuz berdi. Keyinroq urinib ko'ring.",
}

_client = None


def model_name() -> str:
    return os.getenv("GEMINI_MODEL", "").strip() or DEFAULT_MODEL


def is_enabled() -> bool:
    return bool(os.getenv("GEMINI_API_KEY"))


def _get_client():
    global _client
    if _client is None:
        from google import genai
        from google.genai import types
        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"),
                               http_options=types.HttpOptions(timeout=TIMEOUT_MS))
    return _client


async def _call(contents, system_instruction: str | None, max_tokens: int, temperature: float) -> str:
    """Haqiqiy API chaqiruvi (testlarda almashtiriladi)."""
    from google.genai import types
    response = await _get_client().aio.models.generate_content(
        model=model_name(),
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            max_output_tokens=max_tokens,
            temperature=temperature,
        ),
    )
    text = (response.text or "").strip()
    if not text:
        raise AIError("blocked", "bo'sh javob")
    return text


async def generate(contents, system_instruction: str | None = None,
                   max_tokens: int = 2048, temperature: float = 0.6) -> str:
    """Matn qaytaradi yoki AIError ko'taradi."""
    if not is_enabled():
        raise AIError("disabled")
    try:
        return await _call(contents, system_instruction, max_tokens, temperature)
    except AIError:
        raise
    except Exception as e:
        code = getattr(e, "code", None)
        message = str(e)
        logging.warning(f"Gemini xatosi ({model_name()}): {code} {message[:300]}")
        if code == 429 or "RESOURCE_EXHAUSTED" in message:
            raise AIError("quota", message) from e
        if code in (500, 502, 503, 504) or isinstance(e, TimeoutError) or "timed out" in message.lower():
            raise AIError("unavailable", message) from e
        if code == 404:
            logging.error(f"Gemini modeli topilmadi: '{model_name()}'. Render'da GEMINI_MODEL ni tekshiring.")
        raise AIError("error", message) from e


# ── Har bir foydalanuvchi uchun kunlik limit ────────────────────────────────
@dataclass
class _Usage:
    day: dt.date
    count: int = 0


_usage: dict[int, _Usage] = {}


def daily_limit() -> int:
    try:
        return max(1, int(os.getenv("AI_DAILY_LIMIT", "30")))
    except ValueError:
        return 30


def _today() -> dt.date:
    from services.timeutil import now_tashkent
    return now_tashkent().date()


def remaining(user_id: int, unlimited: bool = False) -> int:
    if unlimited:
        return 10**6
    usage = _usage.get(user_id)
    used = usage.count if usage and usage.day == _today() else 0
    return max(0, daily_limit() - used)


def consume(user_id: int, unlimited: bool = False) -> bool:
    """Limitdan 1 ta so'rov oladi. Limit tugagan bo'lsa False."""
    if unlimited:
        return True
    today = _today()
    usage = _usage.get(user_id)
    if not usage or usage.day != today:
        usage = _usage[user_id] = _Usage(today)
    if usage.count >= daily_limit():
        return False
    usage.count += 1
    return True


def refund(user_id: int) -> None:
    """AI xatosi bo'lsa — so'rov hisobga olinmaydi."""
    usage = _usage.get(user_id)
    if usage and usage.count > 0:
        usage.count -= 1


def usage_today() -> tuple[int, int]:
    """Bugun: (AI so'rovlari soni, foydalanuvchilar soni). Admin so'rovlari hisobga olinmaydi."""
    today = _today()
    counts = [u.count for u in _usage.values() if u.day == today and u.count]
    return sum(counts), len(counts)
