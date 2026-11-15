import logging
import os
import re

from pypdf import PdfReader, PdfWriter, Transformation
from reportlab.lib.colors import Color
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from services.transliterator import to_latin

MAX_PAGE_SPEC_LENGTH = 200

# Kirill va o'zbek harflarini qo'llab-quvvatlaydigan shriftlar (Docker'da fonts-dejavu-core)
_FONT_CANDIDATES = [
    "fonts/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
]
_WATERMARK_FONT = None


def _watermark_font() -> str | None:
    """Unicode shriftni bir marta ro'yxatdan o'tkazadi; topilmasa None."""
    global _WATERMARK_FONT
    if _WATERMARK_FONT is None:
        _WATERMARK_FONT = ""
        for path in _FONT_CANDIDATES:
            if os.path.exists(path):
                try:
                    pdfmetrics.registerFont(TTFont("WatermarkFont", path))
                    _WATERMARK_FONT = "WatermarkFont"
                    break
                except Exception as e:
                    logging.warning(f"Shriftni yuklab bo'lmadi {path}: {e}")
        if not _WATERMARK_FONT:
            logging.warning("Unicode shrift topilmadi — watermark lotin harflarida yoziladi.")
    return _WATERMARK_FONT or None


def parse_page_ranges(spec: str, total: int) -> list[int]:
    """
    "1,3,5-7" kabi matndan sahifa raqamlarini oladi (1 dan boshlab, tartiblangan, takrorlarsiz).
    Oraliqlar fayldagi sahifalar soni bilan cheklanadi, shuning uchun "1-100000000"
    kabi kiritish xotirani to'ldirmaydi. Noto'g'ri formatda ValueError.
    """
    if len(spec) > MAX_PAGE_SPEC_LENGTH:
        raise ValueError("juda uzun")
    pages: set[int] = set()
    for part in re.split(r"[,;\s]+", spec.strip()):
        if not part:
            continue
        match = re.fullmatch(r"(\d+)\s*[-–—]\s*(\d+)", part)
        if match:
            start, end = int(match.group(1)), int(match.group(2))
            if start > end:
                start, end = end, start
            start, end = max(start, 1), min(end, total)
            if start <= end:
                pages.update(range(start, end + 1))
        elif part.isdigit():
            page = int(part)
            if 1 <= page <= total:
                pages.add(page)
        else:
            raise ValueError(part)
    return sorted(pages)


class PdfService:
    @staticmethod
    def merge_pdfs(file_paths: list[str], output_path: str) -> bool:
        """Birdan ortiq PDF fayllarni bitta faylga birlashtiradi."""
        try:
            writer = PdfWriter()
            for f in file_paths:
                writer.append(PdfReader(f))
            with open(output_path, "wb") as f_out:
                writer.write(f_out)
            return True
        except Exception as e:
            logging.error(f"PDF merge error: {e}")
            return False

    @staticmethod
    def extract_pages(input_path: str, output_path: str, pages: list[int]) -> int:
        """Ko'rsatilgan sahifalarni (1 dan boshlab) yangi PDF ga ajratadi. Sahifalar sonini qaytaradi."""
        reader = PdfReader(input_path)
        writer = PdfWriter()
        for p in pages:
            if 1 <= p <= len(reader.pages):
                writer.add_page(reader.pages[p - 1])
        if writer.pages:
            with open(output_path, "wb") as f_out:
                writer.write(f_out)
        return len(writer.pages)

    @staticmethod
    def _watermark_layer(path: str, width: float, height: float, text: str) -> None:
        font = _watermark_font()
        if not font:
            text, font = to_latin(text), "Helvetica-Bold"
        size = max(20.0, min(width, height) / max(len(text), 1) * 1.4)
        size = min(size, 90.0)
        c = canvas.Canvas(path, pagesize=(width, height))
        c.setFont(font, size)
        c.setFillColor(Color(0.5, 0.5, 0.5, alpha=0.3))
        c.translate(width / 2, height / 2)
        c.rotate(45)
        c.drawCentredString(0, -size / 3, text)
        c.save()

    @staticmethod
    def add_watermark(input_path: str, output_path: str, wm_text: str, work_dir: str) -> bool:
        """Har bir sahifa markaziga (sahifa o'lchamiga moslab) yarim shaffof matn qo'yadi."""
        try:
            reader = PdfReader(input_path)
            writer = PdfWriter()
            layers: dict[tuple, object] = {}
            for page in reader.pages:
                box = page.mediabox
                size = (round(float(box.width), 1), round(float(box.height), 1))
                if size not in layers:
                    layer_path = os.path.join(work_dir, f"wm_{len(layers)}.pdf")
                    PdfService._watermark_layer(layer_path, size[0], size[1], wm_text)
                    layers[size] = PdfReader(layer_path).pages[0]
                layer = layers[size]
                target = writer.add_page(page)  # avval yozuvchiga biriktiramiz (pypdf tavsiyasi)
                if box.left or box.bottom:  # siljigan sahifalar uchun
                    target.merge_transformed_page(layer, Transformation().translate(float(box.left), float(box.bottom)))
                else:
                    target.merge_page(layer)
            with open(output_path, "wb") as f_out:
                writer.write(f_out)
            return True
        except Exception as e:
            logging.error(f"Watermark error: {e}")
            return False
