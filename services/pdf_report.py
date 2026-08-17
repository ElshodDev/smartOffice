import io
import os
import tempfile
from fpdf import FPDF

class ObyektivkaPDF(FPDF):
    def header(self):
        pass

    def footer(self):
        self.set_y(-15)
        self.set_font('Times', 'I', 9)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, f'Sahifa {self.page_no()}', align='C')

def _clean_text(text: str) -> str:
    if not isinstance(text, str):
        return text
    
    # Replace curly quotes with straight quotes
    text = text.replace('‘', "'").replace('’', "'").replace('“', '"').replace('”', '"')
    
    # Simple Cyrillic to Latin transliteration for Uzbek
    cyrillic_to_latin = {
        'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'Yo', 'Ж': 'J', 'З': 'Z',
        'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M', 'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R',
        'С': 'S', 'Т': 'T', 'У': 'U', 'Ф': 'F', 'Х': 'X', 'Ц': 'Ts', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Sh',
        'Ъ': "'", 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya',
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo', 'ж': 'j', 'з': 'z',
        'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r',
        'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'x', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sh',
        'ъ': "'", 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
        'Қ': 'Q', 'қ': 'q', 'Ғ': "G'", 'ғ': "g'", 'Ҳ': 'H', 'ҳ': 'h', 'Ў': "O'", 'ў': "o'"
    }
    
    for cyr, lat in cyrillic_to_latin.items():
        text = text.replace(cyr, lat)
        
    try:
        return text.encode('latin-1').decode('latin-1')
    except UnicodeEncodeError:
        return text.encode('latin-1', errors='replace').decode('latin-1')

def generate_pdf(data: dict, photo_bytes: bytes = None) -> bytes:
    # Clean data to avoid UnicodeEncodeError in FPDF
    data = {k: _clean_text(str(v)) if v else v for k, v in data.items()}

    pdf = ObyektivkaPDF(unit='mm', format='A4')
    pdf.add_page()
    pdf.set_margins(20, 20, 20)
    pdf.set_auto_page_break(auto=True, margin=20)
    
    page_w = 210
    margin = 20
    content_w = page_w - 2 * margin
    
    # ── Sarlavha ──
    pdf.set_font('Times', 'B', 14)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 8, "MA'LUMOTNOMA", align='C', ln=True)
    
    full_name = data.get('full_name', '')
    pdf.set_font('Times', 'B', 14)
    pdf.cell(0, 8, full_name.upper(), align='C', ln=True)
    pdf.ln(8)
    
    # ── Asosiy ma'lumotlar (Top 3 qator va Foto) ──
    photo_w = 30
    photo_h = 40
    photo_x = page_w - margin - photo_w
    photo_y = pdf.get_y()
    
    # Rasm joylashuvi
    if photo_bytes:
        try:
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                tmp.write(photo_bytes)
                tmp_path = tmp.name
            pdf.set_draw_color(0, 0, 0)
            pdf.set_line_width(0.2)
            pdf.rect(photo_x, photo_y, photo_w, photo_h)
            pdf.image(tmp_path, x=photo_x, y=photo_y, w=photo_w, h=photo_h)
            os.unlink(tmp_path)
        except Exception:
            _draw_photo_placeholder(pdf, photo_x, photo_y, photo_w, photo_h)
    else:
        _draw_photo_placeholder(pdf, photo_x, photo_y, photo_w, photo_h)
        
    # Columns settings
    col1_x = margin
    col2_x = margin + 70
    
    def draw_cell(x, y, label, val):
        pdf.set_xy(x, y)
        pdf.set_font('Times', 'B', 11)
        pdf.cell(65, 5, label, ln=True)
        pdf.set_xy(x, y + 5)
        pdf.set_font('Times', '', 11)
        pdf.cell(65, 5, str(val), ln=False)

    y_cur = photo_y
    draw_cell(col1_x, y_cur, "Tug'ilgan yili:", data.get('birth_date', ''))
    draw_cell(col2_x, y_cur, "Tug'ilgan joyi:", data.get('birth_place', ''))
    
    y_cur += 14
    draw_cell(col1_x, y_cur, "Millati:", data.get('nationality', ''))
    draw_cell(col2_x, y_cur, "Partiyaviyligi:", data.get('party', "yo'q"))
    
    y_cur += 14
    draw_cell(col1_x, y_cur, "Ma'lumoti:", data.get('education', ''))
    
    # Tamomlagan
    pdf.set_xy(col2_x, y_cur)
    pdf.set_font('Times', 'B', 11)
    pdf.cell(65, 5, "Tamomlagan:", ln=True)
    pdf.set_xy(col2_x, y_cur + 5)
    pdf.set_font('Times', '', 11)
    pdf.multi_cell(photo_x - col2_x - 5, 5, str(data.get('graduated', '')))
    
    pdf.set_y(max(pdf.get_y(), photo_y + photo_h) + 6)
    
    # ── Mutaxassisligi (Inline) ──
    y_cur = pdf.get_y()
    pdf.set_xy(col1_x, y_cur)
    pdf.set_font('Times', 'B', 11)
    pdf.cell(75, 5, "Ma'lumoti bo'yicha mutaxassisligi:", ln=False)
    pdf.set_font('Times', '', 11)
    pdf.multi_cell(content_w - 75, 5, str(data.get('specialty', '')))
    
    pdf.ln(4)
    y_cur = pdf.get_y()
    
    # ── Ilmiy darajasi va unvoni (2 columns) ──
    draw_cell(col1_x, y_cur, "Ilmiy darajasi:", data.get('sci_degree', "yo'q"))
    draw_cell(col2_x, y_cur, "Ilmiy unvoni:", data.get('sci_title', "yo'q"))
    pdf.ln(9)
    
    # ── Tillari va harbiy (2 columns) ──
    y_cur = pdf.get_y() + 5
    draw_cell(col1_x, y_cur, "Qaysi chet tillarini biladi:", data.get('languages', "yo'q"))
    draw_cell(col2_x, y_cur, "Harbiy (maxsus) unvoni:", data.get('military', "yo'q"))
    pdf.ln(9)
    
    # ── Davlat mukofotlari ──
    y_cur = pdf.get_y() + 5
    pdf.set_xy(col1_x, y_cur)
    pdf.set_font('Times', 'B', 11)
    pdf.cell(75, 5, "Davlat mukofotlari bilan taqdirlanganmi:", ln=False)
    pdf.set_font('Times', '', 11)
    pdf.cell(0, 5, " " + str(data.get('awards', "yo'q")), ln=True)
    pdf.ln(4)
    
    # ── Xalq deputatlari ──
    y_cur = pdf.get_y()
    pdf.set_xy(col1_x, y_cur)
    pdf.set_font('Times', 'B', 11)
    dep_text = "Xalq deputatlari, respublika, viloyat, shahar va tuman Kengashi deputatimi yoki boshqa saylanadigan organlarning a'zosimi: "
    pdf.write(5, dep_text)
    pdf.set_font('Times', '', 11)
    pdf.write(5, str(data.get('deputy', "yo'q")))
    pdf.ln(12)
    
    # ── MEHNAT FAOLIYATI ──
    pdf.set_font('Times', 'B', 12)
    pdf.cell(0, 8, "MEHNAT FAOLIYATI", align='C', ln=True)
    pdf.ln(3)
    
    work = data.get('work_history', '')
    if work and work != "yo'q":
        for line in work.split('\n'):
            line = line.strip()
            if not line:
                continue
            parts = line.split('—', 1)
            if len(parts) == 1:
                parts = line.split('-', 1)
                
            pdf.set_x(margin)
            if len(parts) == 2:
                pdf.set_font('Times', '', 11)
                pdf.cell(35, 6, parts[0].strip(), ln=False)
                pdf.cell(10, 6, "-", align='C', ln=False)
                pdf.multi_cell(0, 6, parts[1].strip())
            else:
                pdf.set_font('Times', '', 11)
                pdf.multi_cell(0, 6, line)
    else:
        pdf.set_x(margin)
        pdf.set_font('Times', 'I', 11)
        pdf.cell(0, 6, "yo'q", ln=True)

    # ── YAQIN QARINDOSHLAR (2-sahifa) ──
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
        pdf.set_font('Times', 'B', 12)
        pdf.cell(0, 8, f"{full_name.upper()}", align='C', ln=True)

        pdf.set_font('Times', '', 12)
        pdf.cell(0, 6, "ning yaqin qarindoshlari haqida MA'LUMOT", align='C', ln=True)
        pdf.ln(6)

        col_widths = [30, 45, 45, 50]
        headers = ["Qarindoshligi", "F.I.Sh. va tug'ilgan yili", "Ish joyi va lavozimi", "Yashash manzili"]

        pdf.set_font('Times', 'B', 10)
        x_cur = margin
        y_cur = pdf.get_y()
        for hdr, cw in zip(headers, col_widths):
            pdf.set_xy(x_cur, y_cur)
            pdf.multi_cell(cw, 6, hdr, border=1, align='C')
            x_cur += cw
        pdf.set_y(y_cur + 12)

        pdf.set_font('Times', '', 10)
        for idx, (role, raw) in enumerate(relatives):
            if not raw or raw == "yo'q":
                continue

            lines = [l.strip() for l in raw.split('\n') if l.strip()]
            chunks = [lines[i:i+3] for i in range(0, len(lines), 3)]
            
            for chunk_idx, chunk in enumerate(chunks):
                name_val = chunk[0] if len(chunk) > 0 else ''
                work_val = chunk[1] if len(chunk) > 1 else ''
                addr_val = chunk[2] if len(chunk) > 2 else ''

                row_y = pdf.get_y()
                x_cur = margin
                display_role = role if chunk_idx == 0 else ''
                cells = [display_role, name_val, work_val, addr_val]
                
                max_lines = 1
                for val, cw in zip(cells, col_widths):
                    str_w = pdf.get_string_width(str(val))
                    lines_needed = max(1, int(str_w / (cw - 2)) + 1)
                    if lines_needed > max_lines:
                        max_lines = lines_needed
                
                row_height = max_lines * 6
                if row_height < 8:
                    row_height = 8
                
                if row_y + row_height > 280:
                    pdf.add_page()
                    row_y = pdf.get_y()
                
                for val, cw in zip(cells, col_widths):
                    pdf.set_xy(x_cur, row_y)
                    pdf.rect(x_cur, row_y, cw, row_height)
                    text_h = len(str(val).split('\n')) * 6
                    pdf.set_xy(x_cur, row_y + (row_height - text_h) / 2)
                    pdf.multi_cell(cw, 6, str(val), border=0, align='C')
                    x_cur += cw
                    
                pdf.set_y(row_y + row_height)

    buf = io.BytesIO()
    buf.write(pdf.output())
    buf.seek(0)
    return buf.read()


def _draw_photo_placeholder(pdf: FPDF, x, y, w, h):
    pdf.set_draw_color(160, 160, 160)
    pdf.set_line_width(0.3)
    pdf.rect(x, y, w, h)
    pdf.set_font('Times', '', 9)
    pdf.set_text_color(160, 160, 160)
    pdf.set_xy(x, y + h / 2 - 3)
    pdf.cell(w, 6, 'Rasm (3x4)', align='C')
    pdf.set_text_color(0, 0, 0)

