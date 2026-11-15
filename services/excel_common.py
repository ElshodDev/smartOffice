"""
Excel bo'limi uchun umumiy yordamchilar.

- read_table: .xlsx va eski .xls fayllarni o'qiydi.
- column_keyboard: ustun tanlash tugmalari. callback_data'da ustun NOMI emas, TARTIB RAQAMI
  yuboriladi — aks holda raqamli sarlavhalar (2024) va uzun kirill nomlar (64 baytdan ortiq)
  ishlamay qolardi.
"""
import html
import os

import pandas as pd
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from services.converter_service import MAX_FILE_SIZE, human_size

EXCEL_EXTENSIONS = (".xlsx", ".xls")
MAX_COLUMN_BUTTONS = 40
MAX_BUTTON_TEXT = 40


def is_excel(file_name: str | None) -> bool:
    return (file_name or "").lower().endswith(EXCEL_EXTENSIONS)


def size_error(file_size: int | None) -> str | None:
    if file_size and file_size > MAX_FILE_SIZE:
        return f"❌ Fayl juda katta ({human_size(file_size)}). Limit — 20 MB."
    return None


def read_table(path: str) -> pd.DataFrame:
    """Birinchi varaqni o'qiydi. .xls uchun xlrd, .xlsx uchun openpyxl ishlatiladi."""
    engine = "xlrd" if path.lower().endswith(".xls") else None
    return pd.read_excel(path, engine=engine)


def column_label(column) -> str:
    text = str(column)
    if text.startswith("Unnamed:"):
        return f"(nomsiz ustun {text.split(':')[-1].strip()})"
    return text if len(text) <= MAX_BUTTON_TEXT else text[: MAX_BUTTON_TEXT - 1] + "…"


def column_keyboard(columns, prefix: str, extra_first: list | None = None) -> InlineKeyboardMarkup:
    """Har bir ustun uchun tugma: callback_data = f"{prefix}:{tartib_raqami}"."""
    rows = [list(extra_first)] if extra_first else []
    for index, column in enumerate(list(columns)[:MAX_COLUMN_BUTTONS]):
        rows.append([InlineKeyboardButton(text=column_label(column), callback_data=f"{prefix}:{index}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def column_by_index(columns, data: str):
    """callback_data'dan ustunni qaytaradi; topilmasa None."""
    try:
        index = int(data.rsplit(":", 1)[1])
    except (ValueError, IndexError):
        return None
    columns = list(columns)
    return columns[index] if 0 <= index < len(columns) else None


def too_many_columns_note(columns) -> str:
    extra = len(columns) - MAX_COLUMN_BUTTONS
    return f"\n<i>Faqat birinchi {MAX_COLUMN_BUTTONS} ta ustun ko'rsatildi ({extra} tasi yashirin).</i>" if extra > 0 else ""


def esc(value) -> str:
    return html.escape(str(value))


def unique_name(name: str, used: set[str]) -> str:
    """ZIP ichida bir xil nomli fayllar bir-birini bosib ketmasligi uchun."""
    base, ext = os.path.splitext(name)
    candidate, n = name, 2
    while candidate.lower() in used:
        candidate = f"{base} ({n}){ext}"
        n += 1
    used.add(candidate.lower())
    return candidate
