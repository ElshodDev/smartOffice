"""
Gemini orqali qisqa rasmiy matn yozish (hujjat yaratuvchi uchun). Har qanday muammoda
(kalit yo'q, tarmoq, limit, bo'sh yoki shubhali javob) None qaytaradi — chaqiruvchi tayyor shablonga o'tadi.
"""
import logging
import re

from services import gemini

MAX_RESULT_CHARS = 2500


def clean_ai_text(text: str) -> str | None:
    """Markdown belgilarini olib tashlaydi va javob yaroqli ekanini tekshiradi."""
    if not text:
        return None
    text = text.strip()
    text = re.sub(r"^```\w*\s*|\s*```$", "", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?m)^\s*[#>*-]+\s+", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    # Model to'ldirilmagan joy qoldirgan bo'lsa ([F.I.Sh], ___, <...>) — ishonmaymiz
    if not text or re.search(r"\[[^\]]{2,}\]|_{3,}|<[^>]{2,}>|\{\{", text):
        return None
    return text[:MAX_RESULT_CHARS]


async def generate(prompt: str) -> str | None:
    try:
        return clean_ai_text(await gemini.generate(prompt, max_tokens=1024, temperature=0.4))
    except gemini.AIError as e:
        if e.kind != "disabled":
            logging.warning(f"Hujjat matnini AI yoza olmadi ({e.kind}) — shablon ishlatiladi")
        return None
