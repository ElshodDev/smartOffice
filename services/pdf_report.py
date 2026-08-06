import io
import os
import tempfile
from fpdf import FPDF
from datetime import datetime


class ObyektivkaPDF(FPDF):
    def header(self):
        pass  # Sarlavha PDF ichida qo'lda chiziladi

    def footer(self):
        self.set_y(-12)
        self.set_font('Helvetica', 'I', 7)
        self.set_text_color(160, 160, 160)
        now = datetime.now().strftime('%d.%m.%Y')
        self.cell(0, 8, f'smartOffice Bot orqali yaratildi  |  {now}  |  Sahifa {self.page_no()}', align='C')


def _draw_field(pdf: FPDF, label: str, value: str, x: float, y: float, w_label: float, w_value: float, h: float = 7):
    """Label + value juftini chizadi."""
    pdf.set_xy(x, y)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(w_label, h, label + ":", ln=False)
    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(w_value, h, str(value), ln=False)


def generate_pdf(data: dict, photo_bytes: bytes = None) -> bytes:
    """Standart O'zbek Obyektivkasi formatida PDF yaratadi."""
    pdf = ObyektivkaPDF()
    pdf.add_page()
    pdf.set_margins(15, 15, 15)

    page_w = 210
    margin = 15
    content_w = page_w - 2 * margin   # 180 mm

    # ── Sarlavha ──────────────────────────────────────────────
    pdf.set_font('Helvetica', 'B', 14)
    pdf.set_text_color(20, 20, 20)
    pdf.set_y(14)
    pdf.cell(0, 8, "MA'LUMOTNOMA", align='C', ln=True)

    # F.I.Sh. (to'liq ism sarlavha ostida)
    full_name = data.get('full_name', '')
    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_y(24)
    pdf.cell(0, 7, full_name, align='C', ln=True)

    # Ajratuvchi chiziq
    y_after_name = pdf.get_y() + 2
    pdf.set_draw_color(180, 180, 180)
    pdf.set_line_width(0.3)
    pdf.line(margin, y_after_name, page_w - margin, y_after_name)

    # ── Fotosurat (o'ng yuqori burchak) ──────────────────────
    photo_x = page_w - margin - 33
    photo_y = 14
    photo_w = 33
    photo_h = 42

    if photo_bytes:
        try:
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                tmp.write(photo_bytes)
                tmp_path = tmp.name
            pdf.set_draw_color(120, 120, 120)
            pdf.set_line_width(0.4)
            pdf.rect(photo_x - 0.5, photo_y - 0.5, photo_w + 1, photo_h + 1)
            pdf.image(tmp_path, x=photo_x, y=photo_y, w=photo_w, h=photo_h)
            os.unlink(tmp_path)
        except Exception:
            _draw_photo_placeholder(pdf, photo_x, photo_y, photo_w, photo_h)
    else:
        _draw_photo_placeholder(pdf, photo_x, photo_y, photo_w, photo_h)

    # ── Asosiy ma'lumotlar ─────────────────────────────────────
    # 2 ustunli maydon: chap va o'ng
    # Foto uchun chap qism torroq bo'ladi
    start_y = y_after_name + 5
    left_x = margin
    col_w = (photo_x - margin - 6) / 2   # Foto oldidagi bo'shliqda 2 ustun
    label_w = 28
    val_w = col_w - label_w
    row_h = 12
    row_gap = 1

    # --- Qator 1: Tug'ilgan yili | Tug'ilgan joyi ---
    y = start_y
    _draw_two_col_row(
        pdf,
        left_x, y, col_w, row_h,
        "Tug'ilgan yili:", data.get('birth_date', ''),
        "Tug'ilgan joyi:", data.get('birth_place', ''),
    )
    y += row_h + row_gap

    # --- Qator 2: Millati | Partiyaviyligi ---
    _draw_two_col_row(
        pdf,
        left_x, y, col_w, row_h,
        "Millati:", data.get('nationality', ''),
        "Partiyaviyligi:", data.get('party', "yo'q"),
    )
    y += row_h + row_gap

    # --- Qator 3: Ma'lumoti | Tamomlagan ---
    _draw_two_col_row(
        pdf,
        left_x, y, col_w, row_h,
        "Ma'lumoti:", data.get('education', ''),
        "Tamomlagan:", data.get('graduated', ''),
    )
    y = max(y + row_h + row_gap, photo_y + photo_h + 5)

    # Ajratuvchi chiziq
    pdf.set_draw_color(180, 180, 180)
    pdf.line(margin, y - 2, page_w - margin, y - 2)

    # --- To'liq kenglikdagi maydonlar ---
    full_fields = [
        ("Ma'lumoti bo'yicha mutaxassisligi:", data.get('specialty', '')),
        ("Ilmiy darajasi:", data.get('sci_degree', "yo'q")),
        ("Ilmiy unvoni:", data.get('sci_title', "yo'q")),
        ("Qaysi chet tillarini biladi:", data.get('languages', "yo'q")),
        ("Harbiy (maxsus) unvoni:", data.get('military', "yo'q")),
        ("Davlat mukofotlari bilan taqdirlangan (qanaqasi):", data.get('awards', "yo'q")),
        ("Xalq deputatimi yoki boshqa saylanadigan organlar a'zosimi (to'liq ko'rsatilishi lozim):", data.get('deputy', "yo'q")),
    ]

    for label, value in full_fields:
        pdf.set_xy(margin, y)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(60, 60, 60)
        pdf.cell(content_w, 6, label, ln=True)

        pdf.set_x(margin)
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(20, 20, 20)
        # Multi-cell agar matn uzun bo'lsa
        before_y = pdf.get_y()
        pdf.multi_cell(content_w, 5.5, str(value))
        y = pdf.get_y() + 2

    # ── MEHNAT FAOLIYATI ──────────────────────────────────────
    y = pdf.get_y() + 3
    pdf.set_draw_color(180, 180, 180)
    pdf.line(margin, y, page_w - margin, y)
    y += 4

    pdf.set_xy(margin, y)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(0, 7, "MEHNAT FAOLIYATI", align='C', ln=True)
    y = pdf.get_y() + 1

    work = data.get('work_history', '')
    if work and work != "yo'q":
        for line in work.split('\n'):
            line = line.strip()
            if not line:
                continue
            # "—" bo'yicha ajratish: yillar | joy
            parts = line.split('—', 1)
            pdf.set_xy(margin, pdf.get_y())
            if len(parts) == 2:
                pdf.set_font('Helvetica', 'B', 9)
                pdf.set_text_color(40, 40, 40)
                pdf.cell(38, 5.5, parts[0].strip(), ln=False)
                pdf.set_font('Helvetica', '', 9)
                pdf.set_text_color(20, 20, 20)
                pdf.multi_cell(content_w - 38, 5.5, parts[1].strip())
            else:
                pdf.set_font('Helvetica', '', 9)
                pdf.multi_cell(content_w, 5.5, line)
    else:
        pdf.set_xy(margin, pdf.get_y())
        pdf.set_font('Helvetica', 'I', 9)
        pdf.set_text_color(130, 130, 130)
        pdf.cell(0, 5.5, "yo'q", ln=True)

    # ── YAQIN QARINDOSHLAR (2-sahifa) ─────────────────────────
    relatives = [
        ("Otasi",               data.get('rel_father',   '')),
        ("Onasi",               data.get('rel_mother',   '')),
        ("Turmush o'rtog'i",    data.get('rel_spouse',   '')),
        ("Farzandlari",         data.get('rel_children', '')),
        ("Aka-uka/Opa-singillar", data.get('rel_siblings','')),
    ]
    has_relatives = any(v and v != "yo'q" for _, v in relatives)

    if has_relatives:
        pdf.add_page()

        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(20, 20, 20)
        pdf.set_y(14)
        pdf.cell(0, 8, f"{full_name.upper()}", align='C', ln=True)

        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(60, 60, 60)
        pdf.cell(0, 6, "ning yaqin qarindoshlari haqida MA'LUMOT", align='C', ln=True)

        pdf.ln(3)
        pdf.set_draw_color(180, 180, 180)
        pdf.line(margin, pdf.get_y(), page_w - margin, pdf.get_y())
        pdf.ln(5)

        # Jadval sarlavhasi
        col_widths = [32, 42, 42, 40]   # Jami = 156 ~ content_w
        headers = ["Qarindoshligi", "F.I.Sh.", "Ish joyi va lavozimi", "Yashash manzili"]

        hdr_y = pdf.get_y()
        x_cur = margin
        for i, (hdr, cw) in enumerate(zip(headers, col_widths)):
            pdf.set_xy(x_cur, hdr_y)
            pdf.set_fill_color(30, 41, 59)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font('Helvetica', 'B', 8)
            pdf.cell(cw, 8, hdr, border=1, fill=True, align='C')
            x_cur += cw
        pdf.ln(8)

        # Jadval satrlari
        for idx, (role, raw) in enumerate(relatives):
            if not raw or raw == "yo'q":
                continue

            # raw ma'lumotni qatorlarga ajratish
            lines = [l.strip() for l in raw.split('\n') if l.strip()]
            name_val = lines[0] if len(lines) > 0 else ''
            work_val = lines[1] if len(lines) > 1 else ''
            addr_val = lines[2] if len(lines) > 2 else ''

            fill = (idx % 2 == 0)
            fill_color = (241, 245, 249) if fill else (255, 255, 255)
            pdf.set_fill_color(*fill_color)
            pdf.set_text_color(20, 20, 20)
            pdf.set_font('Helvetica', '', 8)

            row_y = pdf.get_y()
            x_cur = margin
            cells = [role, name_val, work_val, addr_val]
            for val, cw in zip(cells, col_widths):
                pdf.set_xy(x_cur, row_y)
                pdf.multi_cell(cw, 6, str(val), border=1, fill=fill)
                x_cur += cw
            # Keyingi qator uchun Y ni hisoblash
            max_h = max(
                pdf.get_string_width(str(v)) / cw * 6 + 6
                for v, cw in zip(cells, col_widths)
            )
            pdf.set_y(row_y + 6)

    # Return as bytes
    buf = io.BytesIO()
    buf.write(pdf.output())
    buf.seek(0)
    return buf.read()



def _draw_photo_placeholder(pdf: FPDF, x, y, w, h):
    """Bo'sh foto ramkasi."""
    pdf.set_draw_color(160, 160, 160)
    pdf.set_line_width(0.4)
    pdf.rect(x, y, w, h)
    pdf.set_font('Helvetica', '', 7)
    pdf.set_text_color(160, 160, 160)
    pdf.set_xy(x, y + h / 2 - 3)
    pdf.cell(w, 6, '3x4', align='C')


def _draw_two_col_row(
    pdf: FPDF,
    x: float, y: float, col_w: float, row_h: float,
    label1: str, val1: str,
    label2: str, val2: str,
):
    """Bir qatorda 2 ta label+value chizadi."""
    gap = 5   # ustunlar orasidagi bo'shliq
    lbl_w = 30

    # --- Chap ustun ---
    pdf.set_xy(x, y)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(lbl_w, row_h / 2, label1, ln=True)
    pdf.set_xy(x, y + row_h / 2)
    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(col_w - gap, row_h / 2, str(val1), ln=False)

    # --- O'ng ustun ---
    x2 = x + col_w + gap
    pdf.set_xy(x2, y)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(lbl_w, row_h / 2, label2, ln=True)
    pdf.set_xy(x2, y + row_h / 2)
    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(col_w - gap, row_h / 2, str(val2), ln=False)

    pdf.set_y(y + row_h)
