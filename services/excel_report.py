import io
from openpyxl import Workbook
from openpyxl.styles import (
    PatternFill, Font, Alignment, Border, Side
)
from openpyxl.utils import get_column_letter
from datetime import datetime


FIELD_LABELS = {
    'full_name':    'F.I.Sh.',
    'current_position': 'Hozirgi ish joyi va lavozimi',
    'birth_date':   "Tug'ilgan yili",
    'birth_place':  "Tug'ilgan joyi",
    'nationality':  'Millati',
    'party':        'Partiyaviyligi',
    'education':    "Ma'lumoti",
    'graduated':    'Tamomlagan',
    'specialty':    "Ma'lumoti bo'yicha mutaxassisligi",
    'sci_degree':   'Ilmiy darajasi',
    'sci_title':    'Ilmiy unvoni',
    'languages':    'Chet tillarini biladi',
    'military':     'Harbiy (maxsus) unvoni',
    'awards':       'Davlat mukofotlari',
    'deputy':       "Deputatmi?",
    'work_history': 'Mehnat faoliyati',
}

# Colors
HEADER_BG   = '1E293B'   # Dark navy
HEADER_FG   = 'FFFFFF'
TITLE_BG    = '3B82F6'   # Blue
TITLE_FG    = 'FFFFFF'
ROW_ALT     = 'F1F5F9'   # Light gray
ROW_NORMAL  = 'FFFFFF'
LABEL_FG    = '475569'
VALUE_FG    = '0F172A'
BORDER_CLR  = 'CBD5E1'


def _thin_border():
    side = Side(style='thin', color=BORDER_CLR)
    return Border(left=side, right=side, top=side, bottom=side)


def generate_excel(data: dict) -> bytes:
    """Foydalanuvchi ma'lumotlaridan chiroyli Excel hisobot yaratadi."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Ma'lumotnoma"

    # ── Column widths ──
    ws.column_dimensions['A'].width = 35
    ws.column_dimensions['B'].width = 50

    # ── Row 1: Main Title ──
    ws.merge_cells('A1:B1')
    title_cell = ws['A1']
    title_cell.value = 'smartOffice — MA\'LUMOTNOMA (OBYEKTIVKA)'
    title_cell.font = Font(name='Calibri', bold=True, size=14, color=TITLE_FG)
    title_cell.fill = PatternFill('solid', fgColor=TITLE_BG)
    title_cell.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 30

    # ── Row 2: Date ──
    ws.merge_cells('A2:B2')
    date_cell = ws['A2']
    date_cell.value = f"Yaratildi: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    date_cell.font = Font(name='Calibri', italic=True, size=10, color='94A3B8')
    date_cell.fill = PatternFill('solid', fgColor=HEADER_BG)
    date_cell.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[2].height = 18

    # ── Row 3: Column headers ──
    headers = ['Maydon', 'Qiymat']
    for col, h in enumerate(headers, start=1):
        cell = ws.cell(row=3, column=col, value=h)
        cell.font = Font(name='Calibri', bold=True, size=11, color=HEADER_FG)
        cell.fill = PatternFill('solid', fgColor=HEADER_BG)
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = _thin_border()
    ws.row_dimensions[3].height = 22

    # ── Data rows ──
    current_row = 4
    for idx, (key, label) in enumerate(FIELD_LABELS.items()):
        value = data.get(key)
        if not value or value == '-':
            continue

        bg = ROW_ALT if idx % 2 == 0 else ROW_NORMAL

        # Label cell
        label_cell = ws.cell(row=current_row, column=1, value=label)
        label_cell.font = Font(name='Calibri', bold=True, size=11, color=LABEL_FG)
        label_cell.fill = PatternFill('solid', fgColor=bg)
        label_cell.alignment = Alignment(horizontal='left', vertical='center', indent=1)
        label_cell.border = _thin_border()

        # Value cell
        value_cell = ws.cell(row=current_row, column=2, value=str(value))
        value_cell.font = Font(name='Calibri', size=11, color=VALUE_FG)
        value_cell.fill = PatternFill('solid', fgColor=bg)
        value_cell.alignment = Alignment(horizontal='left', vertical='center', indent=1, wrap_text=True)
        value_cell.border = _thin_border()

        text_lines = sum(max(1, -(-len(part) // 48)) for part in str(value).split("\n"))
        ws.row_dimensions[current_row].height = max(20, 15 * text_lines + 4)
        current_row += 1

    # ── Footer ──
    ws.merge_cells(f'A{current_row}:B{current_row}')
    footer = ws[f'A{current_row}']
    footer.value = 'Ushbu hisobot smartOffice Telegram boti orqali avtomatik yaratilgan.'
    footer.font = Font(name='Calibri', italic=True, size=9, color='94A3B8')
    footer.fill = PatternFill('solid', fgColor=HEADER_BG)
    footer.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[current_row].height = 18

    # ── 2-varaq: yaqin qarindoshlar (5 ustun) ──
    relatives = data.get('relatives') or []
    if relatives:
        rs = wb.create_sheet("Qarindoshlar")
        headers = ["Qarindoshligi", "Familiyasi, ismi va otasining ismi", "Tug'ilgan yili va joyi",
                   "Ish joyi va lavozimi", "Turar joyi"]
        widths = [18, 34, 30, 34, 30]
        for col, (title, width) in enumerate(zip(headers, widths), start=1):
            cell = rs.cell(row=1, column=col, value=title)
            cell.font = Font(name='Calibri', bold=True, size=11, color=HEADER_FG)
            cell.fill = PatternFill('solid', fgColor=HEADER_BG)
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
            cell.border = _thin_border()
            rs.column_dimensions[get_column_letter(col)].width = width
        rs.row_dimensions[1].height = 32
        for r_idx, rel in enumerate(relatives, start=2):
            values = [rel.get('rel', ''), rel.get('name', ''), rel.get('birth', ''), rel.get('work', ''), rel.get('address', '')]
            for col, value in enumerate(values, start=1):
                cell = rs.cell(row=r_idx, column=col, value=value)
                cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
                cell.border = _thin_border()
        rs.freeze_panes = "A2"

    # ── Save to bytes ──
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()
