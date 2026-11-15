"""
Gemini orqali qisqa rasmiy matn yozish. Har qanday muammoda (kalit yo'q, tarmoq, vaqt tugadi,
bo'sh yoki shubhali javob) None qaytaradi — chaqiruvchi tayyor shablonga o'tadi.
"""
import asyncio
import logging
import os
import re

GEMINI_MODEL = "gemini-3.5-flash"
TIMEOUT_SECONDS = 25
MAX_RESULT_CHARS = 2500

_model = None
_model_loaded = False


def _get_model():
    global _model, _model_loaded
    if not _model_loaded:
        _model_loaded = True
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                _model = genai.GenerativeModel(GEMINI_MODEL)
            except Exception as e:
                logging.warning(f"Gemini modelini yuklab bo'lmadi: {e}")
    return _model


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
    model = _get_model()
    if model is None:
        return None
    try:
        response = await asyncio.wait_for(asyncio.to_thread(model.generate_content, prompt), TIMEOUT_SECONDS)
        return clean_ai_text(getattr(response, "text", "") or "")
    except Exception as e:  # tarmoq, vaqt tugashi, xavfsizlik filtri va h.k.
        logging.warning(f"Gemini javob bermadi: {e}")
        return None
