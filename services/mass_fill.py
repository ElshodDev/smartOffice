"""
📋 Ommaviy shablon to'ldirish: bitta Word shablon + Excel ro'yxat → har bir qator uchun hujjat (ZIP).
"""
import datetime as dt
import math
import os
import zipfile

import pandas as pd
from docx import Document
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from services.docx_template import fill_document, normalize_key
from services.excel_common import read_table, unique_name
from services.tempfiles import safe_filename

MAX_ROWS = 300


def make_sample_excel(placeholders: list[str], path: str) -> None:
    """Shablon o'zgaruvchilari sarlavha bo'lgan bo'sh jadval — foydalanuvchi to'ldirib qaytaradi."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Ro'yxat"
    for col, name in enumerate(placeholders, start=1):
        cell = ws.cell(row=1, column=col, value=name)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="2F5597")
        ws.column_dimensions[cell.column_letter].width = max(14, min(40, len(name) + 6))
    ws.freeze_panes = "A2"
    wb.save(path)


def match_columns(placeholders: list[str], columns) -> tuple[list[str], list[str]]:
    """(mos kelgan o'zgaruvchilar, jadvalda yo'q o'zgaruvchilar)."""
    keys = {normalize_key(c) for c in columns}
    matched = [p for p in placeholders if normalize_key(p) in keys]
    missing = [p for p in placeholders if normalize_key(p) not in keys]
    return matched, missing


def format_cell(value) -> str:
    """Excel qiymatini hujjatga yoziladigan matnga aylantiradi."""
    if value is None or (isinstance(value, float) and math.isnan(value)) or value is pd.NaT:
        return ""
    if isinstance(value, (pd.Timestamp, dt.datetime)):
        return value.strftime("%d.%m.%Y") if (value.hour, value.minute) == (0, 0) else value.strftime("%d.%m.%Y %H:%M")
    if isinstance(value, dt.date):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def generate_documents(template_path: str, excel_path: str, job_dir: str, stem: str,
                       name_column: int | None) -> tuple[str, int]:
    df = read_table(excel_path).dropna(how="all")
    columns = list(df.columns)
    zip_path = os.path.join(job_dir, f"{stem}_hujjatlar.zip")
    used: set[str] = set()
    count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for number, (_, row) in enumerate(df.iterrows(), start=1):
            values = {str(c): format_cell(row[c]) for c in columns}
            document = Document(template_path)
            fill_document(document, values)
            label = format_cell(row[columns[name_column]]) if name_column is not None else ""
            name = f"{number:03d}_{safe_filename(label, '', 50)}" if label else f"{stem}_{number:03d}"
            out = os.path.join(job_dir, "doc_tmp.docx")
            document.save(out)
            zf.write(out, arcname=unique_name(f"{name}.docx", used))
            count += 1
    if count:
        os.remove(os.path.join(job_dir, "doc_tmp.docx"))
    return zip_path, count
