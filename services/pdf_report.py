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
        self.cell(0, 8, 'Shaxsiy Ma\'lumotlar Hisoboti', align='C')

        self.ln(20)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(148, 163, 184)
        now = datetime.now().strftime('%d.%m.%Y %H:%M')
        self.cell(0, 10, f'smartOffice Bot | Yaratildi: {now} | Sahifa {self.page_no()} | Ishlab chiquvchi: @Elshod_Developer', align='C')


FIELD_LABELS = {
    'full_name': 'Ism',
    'surname': 'Familiya',
    'passport': 'Pasport raqami',
    'birth_date': 'Tug\'ilgan sana',
    'address': 'Manzil',
    'phone': 'Telefon',
}


def generate_pdf(data: dict) -> bytes:
    """Foydalanuvchi ma'lumotlaridan chiroyli PDF hisobot yaratadi."""
    pdf = ReportPDF()
    pdf.add_page()

    # ── Title ──
    pdf.set_font('Helvetica', 'B', 16)
    pdf.set_text_color(30, 41, 59)
    pdf.ln(5)
    pdf.cell(0, 12, 'Shaxsiy Ma\'lumotlar', align='C')
    pdf.ln(14)

    # ── Divider ──
    pdf.set_draw_color(59, 130, 246)
    pdf.set_line_width(0.8)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(8)

    # ── Data rows ──
    row_num = 0
    for key, label in FIELD_LABELS.items():
        value = data.get(key)
        if not value or value == '-':
            continue

        # Alternating row colors
        if row_num % 2 == 0:
            pdf.set_fill_color(241, 245, 249)
        else:
            pdf.set_fill_color(255, 255, 255)

        pdf.set_x(20)
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(55, 12, label + ':', fill=True)

        pdf.set_font('Helvetica', '', 11)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(115, 12, str(value), fill=True, ln=True)

        row_num += 1

    # ── Bottom divider ──
    pdf.ln(8)
    pdf.set_draw_color(59, 130, 246)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(10)

    # ── Note ──
    pdf.set_font('Helvetica', 'I', 9)
    pdf.set_text_color(148, 163, 184)
    pdf.cell(0, 8, 'Ushbu hisobot smartOffice Telegram boti orqali avtomatik yaratilgan.', align='C')

    # Return as bytes
    buf = io.BytesIO()
    pdf_bytes = pdf.output()
    buf.write(pdf_bytes)
    buf.seek(0)
    return buf.read()
