"""
📋 Obyektivka (ma'lumotnoma) — standart shakldagi PDF.

1-sahifa: MA'LUMOTNOMA, F.I.Sh., hozirgi lavozim, 3×4 sm rasm (o'ng yuqori burchakda),
          ikki ustunli ma'lumotlar, MEHNAT FAOLIYATI.
2-sahifa: «... ning yaqin qarindoshlari haqida MA'LUMOT» — 5 ustunli jadval.
Matnlar har doim katak ichida o'raladi (ustma-ust tushmaydi).
"""
import io
import os
import re
import tempfile

from fpdf import FPDF

PAGE_W = 210
MARGIN_L, MARGIN_R, MARGIN_T = 20, 15, 15
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R
PHOTO_W, PHOTO_H = 30, 40          # 3×4 sm
LINE_H = 5.2
COL1_W = 80                        # 1-ustun kengligi
COL2_X = MARGIN_L + 86             # 2-ustun boshlanishi (har doim bir xil)

_FONT_DIRS = ["fonts", "/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/dejavu"]


def _find_font(name: str) -> str | None:
    for d in _FONT_DIRS:
        path = os.path.join(d, name)
        if os.path.exists(path):
            return path
    return None


def _clean_latin1(text: str) -> str:
    """Unicode shrift topilmasa (zaxira): Times uchun latin-1 ga moslash."""
    from services.transliterator import to_latin
    text = to_latin(text)
    for a, b in (("‘", "'"), ("’", "'"), ("ʻ", "'"), ("ʼ", "'"), ("`", "'"), ("«", '"'), ("»", '"'),
                 ("“", '"'), ("”", '"'), ("–", "-"), ("—", "-")):
        text = text.replace(a, b)
    return text.encode("latin-1", errors="replace").decode("latin-1")


class ObyektivkaPDF(FPDF):
    def __init__(self):
        super().__init__(unit="mm", format="A4")
        regular, bold = _find_font("DejaVuSerif.ttf"), _find_font("DejaVuSerif-Bold.ttf")
        if regular and bold:
            self.add_font("Body", "", regular)
            self.add_font("Body", "B", bold)
            self.family_name, self.unicode = "Body", True
        else:
            self.family_name, self.unicode = "Times", False
        self.set_margins(MARGIN_L, MARGIN_T, MARGIN_R)
        self.set_auto_page_break(auto=True, margin=15)

    def t(self, text) -> str:
        text = "" if text is None else str(text)
        return text if self.unicode else _clean_latin1(text)

    def font(self, bold=False, size=11):
        self.set_font(self.family_name, "B" if bold else "", size)

    def lines(self, width: float, text: str) -> int:
        return max(1, len(self.multi_cell(width, LINE_H, self.t(text), align="L", dry_run=True, output="LINES")))


def _value(data: dict, key: str) -> str:
    value = str(data.get(key) or "").strip()
    return value or "yo'q"


WORK_LINE = re.compile(
    r"^\s*(\d{4}\s*(?:y+\.?)?(?:\s*[-–—]\s*(?:\d{4}\s*(?:y+\.?)?|h\.?\s*v\.?|hozirgi\s+vaqtgacha|hozirgacha))?\s*(?:y+\.?)?)"
    r"\s*[-–—:]+\s*(.+)$", re.IGNORECASE)


def parse_work_line(line: str) -> tuple[str, str]:
    """'2012-2014 yy. — «Ziyo» MChJ' → ('2012-2014 yy.', '«Ziyo» MChJ'). Davr topilmasa ('', qator)."""
    match = WORK_LINE.match(line)
    if not match:
        return "", line.strip()
    period = match.group(1).strip()
    # "2012-2014 yy." — yillar orasida probelsiz; "2020 y. - h.v." — probel bilan
    period = re.sub(r"(\d{4})\s*[-–—]\s*(\d{4})", r"\1-\2", period)
    period = re.sub(r"\s*[-–—]\s*(?=h|hoz)", " - ", period, flags=re.IGNORECASE)
    return period, match.group(2).strip()


def _labeled(pdf: ObyektivkaPDF, x: float, y: float, w: float, label: str, value: str) -> float:
    """Sarlavha (qalin) + qiymat ostida; balandlikni qaytaradi."""
    pdf.set_xy(x, y)
    pdf.font(True)
    pdf.multi_cell(w, LINE_H, pdf.t(label), align="L", new_x="LEFT", new_y="NEXT")
    pdf.font(False)
    pdf.multi_cell(w, LINE_H, pdf.t(value), align="L", new_x="LEFT", new_y="NEXT")
    return pdf.get_y() - y


def _pair_height(pdf, w, label, value):
    pdf.font(True)
    h = pdf.lines(w, label)
    pdf.font(False)
    return (h + pdf.lines(w, value)) * LINE_H


def _inline(pdf: ObyektivkaPDF, w: float, label: str, value: str):
    """Qalin sarlavha va oddiy qiymat bitta oqimda (uzun bo'lsa o'raladi)."""
    pdf.set_x(MARGIN_L)
    pdf.font(True)
    pdf.write(LINE_H, pdf.t(label) + " ")
    pdf.font(False)
    pdf.write(LINE_H, pdf.t(value))
    pdf.ln(LINE_H + 2.5)


def generate_pdf(data: dict, photo_bytes: bytes | None = None) -> bytes:
    pdf = ObyektivkaPDF()
    pdf.add_page()

    # ── Sarlavha ──
    pdf.font(True, 13)
    pdf.cell(0, 7, pdf.t("MA'LUMOTNOMA"), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.font(True, 13)
    pdf.multi_cell(0, 7, pdf.t(_value(data, "full_name")), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    top = pdf.get_y()
    photo_x = PAGE_W - MARGIN_R - PHOTO_W
    left_w = CONTENT_W - PHOTO_W - 6          # rasm yonidagi kenglik

    # ── 3×4 rasm ──
    pdf.set_draw_color(0, 0, 0)
    pdf.set_line_width(0.2)
    if photo_bytes:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(photo_bytes)
            tmp_path = tmp.name
        try:
            pdf.image(tmp_path, x=photo_x, y=top, w=PHOTO_W, h=PHOTO_H)
        finally:
            os.unlink(tmp_path)
    pdf.rect(photo_x, top, PHOTO_W, PHOTO_H)
    if not photo_bytes:
        pdf.font(False, 8)
        pdf.set_text_color(150, 150, 150)
        pdf.set_xy(photo_x, top + PHOTO_H / 2 - 2)
        pdf.cell(PHOTO_W, 4, pdf.t("3×4 rasm" if pdf.unicode else "3x4 rasm"), align="C")
        pdf.set_text_color(0, 0, 0)

    # ── Hozirgi lavozim ──
    pdf.set_xy(MARGIN_L, top)
    current = str(data.get("current_position") or "").strip()
    if current and current.lower() not in ("yo'q", "yoq", "-"):
        date_part, sep, rest = current.partition(":")
        if sep and len(date_part) <= 40:
            pdf.font(True)
            pdf.multi_cell(left_w, LINE_H, pdf.t(date_part + ":"), align="L", new_x="LMARGIN", new_y="NEXT")
            pdf.font(False)
            pdf.multi_cell(left_w, LINE_H, pdf.t(rest.strip()), align="L", new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.font(False)
            pdf.multi_cell(left_w, LINE_H, pdf.t(current), align="L", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    # ── Ikki ustunli ma'lumotlar (rasm yonida, so'ng to'liq kenglikda) ──
    pairs = [
        ("Tug'ilgan yili:", _value(data, "birth_date"), "Tug'ilgan joyi:", _value(data, "birth_place")),
        ("Millati:", _value(data, "nationality"), "Partiyaviyligi:", _value(data, "party")),
        ("Ma'lumoti:", _value(data, "education"), "Tamomlagan:", _value(data, "graduated")),
    ]
    for l1, v1, l2, v2 in pairs:
        y = pdf.get_y()
        w2 = (photo_x - 4 - COL2_X) if y < top + PHOTO_H else (MARGIN_L + CONTENT_W - COL2_X)
        h = max(_pair_height(pdf, COL1_W, l1, v1), _pair_height(pdf, w2, l2, v2))
        _labeled(pdf, MARGIN_L, y, COL1_W, l1, v1)
        _labeled(pdf, COL2_X, y, w2, l2, v2)
        pdf.set_y(y + h + 2.5)
    pdf.set_y(max(pdf.get_y(), top + PHOTO_H + 3))

    _inline(pdf, CONTENT_W, "Ma'lumoti bo'yicha mutaxassisligi:", _value(data, "specialty"))
    for l1, k1, l2, k2 in (("Ilmiy darajasi:", "sci_degree", "Ilmiy unvoni:", "sci_title"),
                           ("Qaysi chet tillarini biladi:", "languages", "Harbiy (maxsus) unvoni:", "military")):
        y = pdf.get_y()
        w2 = MARGIN_L + CONTENT_W - COL2_X
        h = max(_pair_height(pdf, COL1_W, l1, _value(data, k1)), _pair_height(pdf, w2, l2, _value(data, k2)))
        _labeled(pdf, MARGIN_L, y, COL1_W, l1, _value(data, k1))
        _labeled(pdf, COL2_X, y, w2, l2, _value(data, k2))
        pdf.set_y(y + h + 2.5)
    _inline(pdf, CONTENT_W, "Davlat mukofotlari bilan taqdirlanganmi (qanaqa):", _value(data, "awards"))
    _inline(pdf, CONTENT_W, "Xalq deputatlari, respublika, viloyat, shahar va tuman Kengashi deputatimi yoki "
                            "boshqa saylanadigan organlarning a'zosimi (to'liq ko'rsatilishi lozim):",
            _value(data, "deputy"))

    # ── Mehnat faoliyati ──
    pdf.ln(2)
    pdf.font(True, 12)
    pdf.cell(0, 7, pdf.t("MEHNAT FAOLIYATI"), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    work = str(data.get("work_history") or "").strip()
    lines = [ln for ln in work.splitlines() if ln.strip()] if work.lower() not in ("", "yo'q", "yoq") else []
    period_w = 38
    if not lines:
        pdf.font(False)
        pdf.cell(0, LINE_H, pdf.t("yo'q"), new_x="LMARGIN", new_y="NEXT")
    for line in lines:
        period, text = parse_work_line(line)
        pdf.font(False)
        h = pdf.lines(CONTENT_W - period_w - 4, text) * LINE_H
        if pdf.get_y() + h > 280:
            pdf.add_page()
        y = pdf.get_y()
        pdf.set_xy(MARGIN_L, y)
        pdf.multi_cell(period_w, LINE_H, pdf.t(f"{period} -" if period else ""), align="L")
        pdf.set_xy(MARGIN_L + period_w + 4, y)
        pdf.multi_cell(CONTENT_W - period_w - 4, LINE_H, pdf.t(text), align="L")
        pdf.set_y(y + h + 1.5)

    # ── 2-sahifa: yaqin qarindoshlar ──
    relatives = data.get("relatives") or []
    if relatives:
        pdf.add_page()
        name = _value(data, "full_name")
        pdf.font(True, 12)
        pdf.multi_cell(0, 6.5, pdf.t(f"{name.upper()}NING YAQIN QARINDOSHLARI HAQIDA"), align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.multi_cell(0, 6.5, pdf.t("MA'LUMOT"), align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)
        widths = [27, 39, 35, 37, CONTENT_W - 138]
        headers = ["Qarindoshligi", "Familiyasi, ismi va otasining ismi", "Tug'ilgan yili va joyi",
                   "Ish joyi va lavozimi", "Turar joyi"]

        def row(cells, bold=False):
            pdf.font(bold, 8.5 if bold else 9.5)
            heights = [pdf.lines(w - 2, c) for w, c in zip(widths, cells)]
            h = max(heights) * LINE_H + 2
            if pdf.get_y() + h > 282:
                pdf.add_page()
                if not bold:
                    row(headers, bold=True)
                    pdf.font(False, 9.5)
            y, x = pdf.get_y(), MARGIN_L
            for w, cell, lines_count in zip(widths, cells, heights):
                pdf.rect(x, y, w, h)
                pdf.set_xy(x + 1, y + (h - lines_count * LINE_H) / 2)
                pdf.multi_cell(w - 2, LINE_H, pdf.t(cell), align="C")
                x += w
            pdf.set_y(y + h)

        row(headers, bold=True)
        for r in relatives:
            row([r.get("rel", ""), r.get("name", ""), r.get("birth", ""), r.get("work", ""), r.get("address", "")])

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()
