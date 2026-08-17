import logging
from pdf2docx import Converter
from PIL import Image

class ConverterService:
    @staticmethod
    def pdf_to_word(pdf_path: str, docx_path: str) -> bool:
        """PDF faylni Word (docx) ga o'giradi."""
        try:
            cv = Converter(pdf_path)
            cv.convert(docx_path)
            cv.close()
            return True
        except Exception as e:
            logging.error(f"PDF to Word xatolik: {e}")
            return False

    @staticmethod
    def img_to_pdf(img_path: str, pdf_path: str) -> bool:
        """Rasmni (JPG, PNG) PDF formatiga o'tkazadi."""
        try:
            image = Image.open(img_path)
            if image.mode != 'RGB':
                image = image.convert('RGB')
            image.save(pdf_path, "PDF", resolution=100.0)
            return True
        except Exception as e:
            logging.error(f"Image to PDF xatolik: {e}")
            return False
