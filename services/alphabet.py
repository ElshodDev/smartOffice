"""
🔤 Bot interfeysi yangi lotin alifbosida (ó, ǵ, ş, ç, ñ).

Kod ichidagi matnlar hozirgi lotinda qoladi (handlerlar ularni solishtiradi), lekin
Telegram'ga ketayotgan har bir xabar, izoh (caption), tugma va ogohlantirish shu yerda
yangi lotinga o'giriladi (`AlphabetRequestMiddleware`). Foydalanuvchi yangi lotindagi
tugmani bosganda keladigan matn esa asl ko'rinishiga qaytariladi (`AlphabetInputMiddleware`).

O'girilMAYDIGAN qismlar:
  • raw(...) ichiga olingan matn — foydalanuvchi yozgan narsa, tarjima/OCR/AI natijasi va h.k.;
  • <code> va <pre> ichidagi matn, HTML teglar va &...; belgilar;
  • havolalar, @username, /buyruqlar, fayl nomlari, qisqartmalar (PNG, HEIC) va inglizcha so'zlar.
"""
from __future__ import annotations

import ast
import html
import logging
import os
import re
from typing import Any

from aiogram import BaseMiddleware
from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, Message, ReplyKeyboardMarkup,
)

from services.transliterator import to_new_latin

ENABLED = os.getenv("BOT_ALPHABET", "new").lower() != "old"

RAW_START, RAW_END = "", ""


def raw(text: Any) -> str:
    """Bu matn yangi lotinga o'girilmaydi (foydalanuvchi matni, natijalar)."""
    return f"{RAW_START}{'' if text is None else text}{RAW_END}"


def esc(text: Any) -> str:
    """html.escape + raw: foydalanuvchi yozgan narsani xabar ichiga xavfsiz qo'yish."""
    return raw(html.escape("" if text is None else str(text)))


def strip_markers(text: str) -> str:
    return text.replace(RAW_START, "").replace(RAW_END, "")


# Inglizcha va texnik so'zlar — "sh/ch/ng" bo'lsa ham o'zgarmaydi
SKIP_WORDS = {
    "chart", "check", "channel", "finish", "landing", "page", "languages", "missing", "ping",
    "refresh", "running", "search", "settings", "share", "short", "scheduler", "apscheduler",
    "english", "string", "thing", "long", "change", "branch", "watch", "match", "push", "flash",
    "smartoffice", "tashkent", "ingliz", "inglizcha", "inglizchaga", "inglizchadan", "ingliztili",
    "google", "github", "neon", "render", "gemini", "chatgpt", "markdown", "html", "fresh",
    "sheet", "sheets", "shift", "show", "hash", "cache", "launch", "touch", "batch", "bash",
    "png", "jpeg", "svg",
}

# Saqlanadigan bo'laklar: teglar, &...; , <code>/<pre> ichi, raw(...) ichi
_PROTECTED = re.compile(
    rf"{RAW_START}.*?{RAW_END}"
    r"|<(code|pre)\b[^>]*>.*?</\1>"
    r"|</?[a-zA-Z][^<>]*>"
    r"|&#?\w+;",
    re.S,
)
# Bitta "so'z" (bo'sh joygacha bo'lgan bo'lak)
_CHUNK = re.compile(r"\S+")
_APOS = "'‘’ʻʼ`"
_WORD = re.compile(rf"[A-Za-z][A-Za-z{_APOS}]*")


def _is_technical_chunk(chunk: str) -> bool:
    if "://" in chunk or chunk.startswith(("@", "/", "#", "www.")) or "_" in chunk:
        return True
    # fayl nomi / domen: "file.png", "t.me", "natija.docx"
    return bool(re.search(r"[A-Za-z0-9]\.[A-Za-z]", chunk))


def _convert_word(match: re.Match) -> str:
    word = match.group(0)
    bare = word.strip(_APOS)
    if bare.lower() in SKIP_WORDS:
        return word
    if bare.isupper() and len(bare) <= 4:          # PNG, HEIC, SH ... qisqartmalar
        return word
    # So'z oxiridagi tutuq — yopuvchi qo'shtirnoq bo'lishi mumkin ('Kino' → 'Kinó' bo'lmasin);
    # faqat g' (tog', bog') o'zbekchada so'z oxirida keladi
    tail = ""
    if len(word) >= 2 and word[-1] in _APOS and word[-2] in "oO":
        word, tail = word[:-1], word[-1]
    return to_new_latin(word) + tail


def _convert_plain(text: str) -> str:
    def chunk(m: re.Match) -> str:
        c = m.group(0)
        return c if _is_technical_chunk(c) else _WORD.sub(_convert_word, c)
    return _CHUNK.sub(chunk, text)


def convert(text: str | None) -> str | None:
    """Bot matnini yangi lotinga o'giradi (himoyalangan qismlar bundan mustasno)."""
    if not text:
        return text
    if not ENABLED:
        return strip_markers(text)
    out, pos = [], 0
    for m in _PROTECTED.finditer(text):
        out.append(_convert_plain(text[pos:m.start()]))
        out.append(m.group(0))
        pos = m.end()
    out.append(_convert_plain(text[pos:]))
    return strip_markers("".join(out))


# ── Tugmalar ────────────────────────────────────────────────────────────────
# Yangi lotindagi tugma matni → kod ichidagi asl matn (foydalanuvchi bosganda qaytarish uchun)
_REVERSE: dict[str, str] = {}


def remember(original: str) -> str:
    converted = convert(original)
    if converted != original:
        _REVERSE[converted] = original
    return converted


def original_text(text: str) -> str:
    return _REVERSE.get(text, text)


def _convert_markup(markup):
    if isinstance(markup, InlineKeyboardMarkup):
        return InlineKeyboardMarkup(inline_keyboard=[
            [b.model_copy(update={"text": convert(b.text)}) for b in row] for row in markup.inline_keyboard
        ])
    if isinstance(markup, ReplyKeyboardMarkup):
        return markup.model_copy(update={"keyboard": [
            [b.model_copy(update={"text": remember(b.text)}) for b in row] for row in markup.keyboard
        ], "input_field_placeholder": convert(markup.input_field_placeholder)})
    return markup


def preload_source_strings(paths: list[str]) -> int:
    """Kod ichidagi barcha qisqa matnlarni oldindan ro'yxatga oladi — bot qayta ishga tushgach ham
    foydalanuvchi telefonidagi eski (yangi lotindagi) tugmalar ishlayveradi."""
    count = 0
    for path in paths:
        try:
            with open(path, encoding="utf-8-sig") as f:
                tree = ast.parse(f.read())
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and 0 < len(node.value) <= 64 \
                    and "\n" not in node.value:
                before = len(_REVERSE)
                remember(node.value)
                count += len(_REVERSE) - before
    return count


# ── Telegram'ga ketayotgan so'rovlar ───────────────────────────────────────
_TEXT_FIELDS = ("text", "caption", "question", "explanation")


class AlphabetRequestMiddleware(BaseRequestMiddleware):
    async def __call__(self, make_request, bot, method):
        try:
            for field in _TEXT_FIELDS:
                value = getattr(method, field, None)
                if isinstance(value, str):
                    setattr(method, field, convert(value))
            markup = getattr(method, "reply_markup", None)
            if markup is not None:
                method.reply_markup = _convert_markup(markup)
            media = getattr(method, "media", None)
            if isinstance(media, list):
                method.media = [m.model_copy(update={"caption": convert(m.caption)}) if getattr(m, "caption", None) else m
                                for m in media]
            elif media is not None and getattr(media, "caption", None):
                method.media = media.model_copy(update={"caption": convert(media.caption)})
            commands = getattr(method, "commands", None)
            if isinstance(commands, list):
                method.commands = [c.model_copy(update={"description": convert(c.description)}) for c in commands]
        except Exception as e:   # o'girishdagi xato xabarni yubormaslikka sabab bo'lmasin
            logging.exception(f"Alifbo o'girishda xato ({type(method).__name__}): {e}")
            for field in _TEXT_FIELDS:
                value = getattr(method, field, None)
                if isinstance(value, str):
                    setattr(method, field, strip_markers(value))
        return await make_request(bot, method)


# ── Foydalanuvchidan kelayotgan tugma bosishlari ─────────────────────────────
class AlphabetInputMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if isinstance(event, Message) and event.text and event.text in _REVERSE:
            event = event.model_copy(update={"text": _REVERSE[event.text]}).as_(data["bot"])
        return await handler(event, data)


# ── Web ilova sahifalari ────────────────────────────────────────────────────
_PAGE_PROTECTED = re.compile(r"<(script|style)\b.*?</\1>|<!--.*?-->", re.S | re.I)
_page_cache: dict[tuple[str, float], str] = {}


def convert_html_page(page: str) -> str:
    """HTML sahifadagi ko'rinadigan matnni yangi lotinga o'giradi (<script>/<style> tegilmaydi)."""
    out, pos = [], 0
    for m in _PAGE_PROTECTED.finditer(page):
        out.append(convert(page[pos:m.start()]) or "")
        out.append(m.group(0))
        pos = m.end()
    out.append(convert(page[pos:]) or "")
    return "".join(out)


def load_page(path: str) -> str:
    mtime = os.path.getmtime(path)
    key = (path, mtime)
    if key not in _page_cache:
        with open(path, encoding="utf-8-sig") as f:
            _page_cache[key] = convert_html_page(f.read())
    return _page_cache[key]
