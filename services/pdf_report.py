import io
from fpdf import FPDF
from datetime import datetime


class ReportPDF(FPDF):
    def header(self):
        # Header background
        self.set_fill_color(30, 41, 59)
        self.rect(0, 0, 210, 35, 'F')

        # Logo text
        self.set_font('Helvetica', 'B', 20)
        self.set_text_color(59, 130, 246)
        self.set_y(8)
        self.cell(0, 10, 'smartOffice', align='C')

        # Subtitle
        self.set_font('Helvetica', '', 10)
        self.set_text_color(148, 163, 184)
        self.set_y(20)
        self.cell(0, 8, 'MA\'LUMOTNOMA (OBYEKTIVKA)', align='C')

        self.ln(20)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(148, 163, 184)
        now = datetime.now().strftime('%d.%m.%Y %H:%M')
        self.cell(0, 10, f'smartOffice Bot  |  Yaratildi: {now}  |  Sahifa {self.page_no()}', align='C')


FIELD_LABELS = {
    'full_name': 'F.I.Sh.',
    'birth_info': 'Tug\'ilgan yili va joyi',
    'education': 'Ma\'lumoti, mutaxassisligi',
    'experience': 'Ish joyi, lavozimi',
}


def generate_pdf(data: dict, photo_bytes: bytes = None) -> bytes:
    """Foydalanuvchi ma'lumotlaridan chiroyli Obyektivka PDF yaratadi."""
    pdf = ReportPDF()
    pdf.add_page()

    # ── Title ──
    pdf.set_font('Helvetica', 'B', 16)
    pdf.set_text_color(30, 41, 59)
    pdf.ln(5)
    pdf.cell(0, 12, 'MA\'LUMOTNOMA', align='C')
    pdf.ln(14)

    # ── Divider ──
    pdf.set_draw_color(59, 130, 246)
    pdf.set_line_width(0.8)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(8)

    # ── Fotosurat (3x4) o'ng burchakda ──
    photo_col_x = 155   # X holati (o'ng)
    photo_col_y = 50    # Y holati (sarlavhadan pastroq)
    photo_w = 35        # 3x4 proporsiyada (mm)
    photo_h = 47

    if photo_bytes:
        try:
            import tempfile, os
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                tmp.write(photo_bytes)
                tmp_path = tmp.name
            # Rasm chegarasi (ramka)
            pdf.set_draw_color(100, 116, 139)
            pdf.set_line_width(0.5)
            pdf.rect(photo_col_x - 1, photo_col_y - 1, photo_w + 2, photo_h + 2)
            pdf.image(tmp_path, x=photo_col_x, y=photo_col_y, w=photo_w, h=photo_h)
            os.unlink(tmp_path)
        except Exception:
            # Rasm qo'shilmasa ham davom etamiz
            pass
    else:
        # Fotosiz bo'lsa — bo'sh ramka
        pdf.set_draw_color(148, 163, 184)
        pdf.set_line_width(0.5)
        pdf.rect(photo_col_x - 1, photo_col_y - 1, photo_w + 2, photo_h + 2)
        pdf.set_font('Helvetica', '', 7)
        pdf.set_text_color(148, 163, 184)
        pdf.set_xy(photo_col_x, photo_col_y + photo_h / 2 - 3)
        pdf.cell(photo_w, 6, '3x4 RASM', align='C')

    # ── Data rows (chap tomonda, rasm bilan yon-yon) ──
    row_num = 0
    data_area_w_label = 50
    data_area_w_value = 80   # Rasm uchun joy qoldirgan holda
    for key, label in FIELD_LABELS.items():
        value = data.get(key)
        if not value or value == '-':
            continue

        if row_num % 2 == 0:
            pdf.set_fill_color(241, 245, 249)
        else:
            pdf.set_fill_color(255, 255, 255)

        pdf.set_x(20)
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(data_area_w_label, 14, label + ':', fill=True)

        pdf.set_font('Helvetica', '', 11)
        pdf.set_text_color(15, 23, 42)
        # Multi_cell uchun x qayta o'rnatamiz
        pdf.multi_cell(data_area_w_value, 14, str(value), fill=True)

        row_num += 1

    # ── Bottom divider ──
    pdf.ln(6)
    pdf.set_draw_color(59, 130, 246)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(10)

    # ── Note ──
    pdf.set_font('Helvetica', 'I', 9)
    pdf.set_text_color(148, 163, 184)
    pdf.cell(0, 8, 'Ushbu ma\'lumotnoma smartOffice Telegram boti orqali avtomatik yaratilgan.', align='C')

    # Return as bytes
    buf = io.BytesIO()
    pdf_bytes = pdf.output()
    buf.write(pdf_bytes)
    buf.seek(0)
    return buf.read()

