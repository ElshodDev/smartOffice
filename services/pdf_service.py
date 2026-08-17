import os
import logging
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

class PdfService:
    @staticmethod
    def merge_pdfs(file_paths: list[str], output_path: str) -> bool:
        """Birdan ortiq PDF fayllarni bitta faylga birlashtiradi."""
        try:
            writer = PdfWriter()
            for f in file_paths:
                reader = PdfReader(f)
                writer.append(reader)
                
            with open(output_path, "wb") as f_out:
                writer.write(f_out)
            return True
        except Exception as e:
            logging.error(f"PDF merge error: {e}")
            return False

    @staticmethod
    def lock_pdf(input_path: str, output_path: str, password: str) -> bool:
        """PDF faylga parol o'rnatadi."""
        try:
            reader = PdfReader(input_path)
            writer = PdfWriter()
            writer.append_pages_from_reader(reader)
            writer.encrypt(password)
            
            with open(output_path, "wb") as f_out:
                writer.write(f_out)
            return True
        except Exception as e:
            logging.error(f"PDF lock error: {e}")
            return False

    @staticmethod
    def extract_pages(input_path: str, output_path: str, pages_to_extract: set[int], total_pages: int) -> int:
        """PDF fayldan ko'rsatilgan sahifalarni ajratib oladi. Ajratilgan sahifalar sonini qaytaradi."""
        try:
            reader = PdfReader(input_path)
            writer = PdfWriter()
            
            for p in sorted(pages_to_extract):
                if 1 <= p <= total_pages:
                    writer.add_page(reader.pages[p - 1])
                    
            if len(writer.pages) > 0:
                with open(output_path, "wb") as f_out:
                    writer.write(f_out)
            return len(writer.pages)
        except Exception as e:
            logging.error(f"PDF extract error: {e}")
            return 0

    @staticmethod
    def add_watermark(input_path: str, output_path: str, wm_text: str) -> bool:
        """PDF faylga matnli watermark qo'yadi."""
        wm_pdf = "temp/watermark_layer.pdf"
        try:
            # 1. Matnli pdf yaratamiz (watermark qatlami)
            c = canvas.Canvas(wm_pdf, pagesize=A4)
            c.setFont("Helvetica-Bold", 60)
            c.setFillColorRGB(0.5, 0.5, 0.5, alpha=0.3)
            c.translate(300, 400)
            c.rotate(45)
            c.drawCentredString(0, 0, wm_text)
            c.save()
            
            # 2. Birlashtirish
            watermark = PdfReader(wm_pdf).pages[0]
            reader = PdfReader(input_path)
            writer = PdfWriter()
            
            for page in reader.pages:
                page.merge_page(watermark)
                writer.add_page(page)
                
            with open(output_path, "wb") as f_out:
                writer.write(f_out)
            return True
        except Exception as e:
            logging.error(f"Watermark error: {e}")
            return False
        finally:
            if os.path.exists(wm_pdf):
                os.remove(wm_pdf)
