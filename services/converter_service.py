"""
Fayl formatlarini o'zgartirish xizmati.

Barcha funksiyalar sinxron (CPU og'ir). Ularni bot ichidan to'g'ridan-to'g'ri emas,
`run_heavy()` orqali chaqiring: u ishni alohida oqimda bajaradi (bot qotmaydi) va
bir vaqtda faqat bitta og'ir ish bajarilishini ta'minlaydi (512 MB xotira tugamaydi).
"""
import asyncio
import io
import logging
import os
import zipfile

import fitz  # PyMuPDF
from pdf2docx import Converter
from PIL import Image, ImageOps

try:  # iPhone HEIC/HEIF rasmlari uchun
    from pillow_heif import register_heif_opener

    register_heif_opener()
    HEIC_SUPPORTED = True
except ImportError:  # paket o'rnatilmagan bo'lsa, qolgan formatlar ishlayveradi
    HEIC_SUPPORTED = False

# ── Cheklovlar ──────────────────────────────────────────────────────────────
MAX_FILE_SIZE = 20 * 1024 * 1024   # Telegram bot API yuklab olish chegarasi
MAX_PDF2WORD_PAGES = 40
MAX_PDF2IMG_PAGES = 20
MAX_COMPRESS_PAGES = 150
MAX_IMAGES_PER_PDF = 30

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".webp", ".heic", ".heif", ".tif", ".tiff")

# ── Navbat: bir vaqtda bitta og'ir konvertatsiya ─────────────────────────────
_heavy_lock = asyncio.Semaphore(1)


def is_busy() -> bool:
    """Hozir boshqa og'ir ish bajarilyaptimi (foydalanuvchiga "navbatda" deyish uchun)."""
    return _heavy_lock.locked()


async def run_heavy(func, *args, **kwargs):
    async with _heavy_lock:
        return await asyncio.to_thread(func, *args, **kwargs)


class ConversionError(Exception):
    """Foydalanuvchiga ko'rsatiladigan tushunarli xato."""


def pdf_page_count(pdf_path: str) -> int:
    try:
        with fitz.open(pdf_path) as doc:
            if doc.needs_pass:
                raise ConversionError("🔒 PDF parol bilan himoyalangan. Avval parolni olib tashlang.")
            return doc.page_count
    except ConversionError:
        raise
    except Exception as e:
        raise ConversionError("❌ PDF faylni ochib bo'lmadi. Fayl buzilgan bo'lishi mumkin.") from e


def pdf_has_text(pdf_path: str, sample_pages: int = 5) -> bool:
    with fitz.open(pdf_path) as doc:
        for page in doc.pages(0, min(sample_pages, doc.page_count)):
            if page.get_text().strip():
                return True
    return False


def _check_pages(pdf_path: str, limit: int) -> int:
    pages = pdf_page_count(pdf_path)
    if pages == 0:
        raise ConversionError("❌ PDF faylda sahifa yo'q.")
    if pages > limit:
        raise ConversionError(
            f"❌ PDF juda katta: {pages} sahifa. Bu amal uchun ko'pi bilan {limit} sahifa.\n"
            "Avval PDF bo'limidagi «Sahifalarni ajratish» orqali kichikroq qismlarga bo'ling."
        )
    return pages


class ConverterService:
    # ── PDF → Word ──────────────────────────────────────────────────────────
    @staticmethod
    def pdf_to_word(pdf_path: str, docx_path: str, max_pages: int = MAX_PDF2WORD_PAGES) -> bool:
        """PDF faylni Word (docx) ga o'giradi. Muvaffaqiyatsiz bo'lsa False."""
        try:
            _check_pages(pdf_path, max_pages)
            cv = Converter(pdf_path)
            try:
                cv.convert(docx_path)
            finally:
                cv.close()
            return True
        except ConversionError:
            raise
        except Exception as e:
            logging.error(f"PDF to Word xatolik: {e}")
            return False

    # ── Rasm(lar) → PDF ─────────────────────────────────────────────────────
    @staticmethod
    def _open_image_rgb(img_path: str) -> Image.Image:
        image = Image.open(img_path)
        image = ImageOps.exif_transpose(image)  # telefonda burilgan suratlarni to'g'rilash
        if image.mode in ("RGBA", "LA", "P"):
            image = image.convert("RGBA")
            background = Image.new("RGB", image.size, "white")
            background.paste(image, mask=image.split()[-1])
            return background
        return image.convert("RGB")

    @staticmethod
    def images_to_pdf(img_paths: list[str], pdf_path: str) -> None:
        """Bir yoki bir nechta rasmni bitta PDF ga (har rasm alohida sahifa) birlashtiradi."""
        if not img_paths:
            raise ConversionError("❌ Rasm yuborilmadi.")
        pages = []
        try:
            for path in img_paths:
                try:
                    pages.append(ConverterService._open_image_rgb(path))
                except Exception as e:
                    raise ConversionError(
                        f"❌ «{os.path.basename(path).split('_', 2)[-1]}» rasmini ochib bo'lmadi."
                    ) from e
            pages[0].save(pdf_path, "PDF", resolution=150.0, save_all=True, append_images=pages[1:])
        finally:
            for page in pages:
                page.close()

    @staticmethod
    def img_to_pdf(img_path: str, pdf_path: str) -> bool:
        """Eski interfeys: bitta rasm → PDF."""
        try:
            ConverterService.images_to_pdf([img_path], pdf_path)
            return True
        except Exception as e:
            logging.error(f"Image to PDF xatolik: {e}")
            return False

    # ── PDF → rasmlar ───────────────────────────────────────────────────────
    @staticmethod
    def pdf_to_images(pdf_path: str, out_dir: str, base_name: str, dpi: int = 150) -> list[str]:
        """Har bir sahifani JPG qiladi. Bitta sahifa bo'lsa — .jpg, ko'p bo'lsa — .zip qaytaradi."""
        _check_pages(pdf_path, MAX_PDF2IMG_PAGES)
        os.makedirs(out_dir, exist_ok=True)
        zoom = dpi / 72
        files = []
        with fitz.open(pdf_path) as doc:
            for i, page in enumerate(doc, start=1):
                pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
                out = os.path.join(out_dir, f"{base_name}_{i:03d}.jpg")
                pix.save(out, jpg_quality=85)
                files.append(out)
        if len(files) == 1:
            return files
        zip_path = os.path.join(out_dir, f"{base_name}_rasmlar.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in files:
                zf.write(path, arcname=os.path.basename(path))
        return [zip_path]

    # ── PDF siqish ──────────────────────────────────────────────────────────
    @staticmethod
    def compress_pdf(pdf_path: str, out_path: str, max_side: int = 1600, quality: int = 70) -> tuple[int, int]:
        """
        PDF hajmini kamaytiradi: katta rasmlarni kichraytirib JPEG qiladi va
        ortiqcha obyektlarni tozalaydi. (asl_hajm, yangi_hajm) qaytaradi.
        """
        _check_pages(pdf_path, MAX_COMPRESS_PAGES)
        before = os.path.getsize(pdf_path)
        with fitz.open(pdf_path) as doc:
            done = set()
            for page in doc:
                for img in page.get_images(full=True):
                    xref, smask = img[0], img[1]
                    if xref in done or smask:  # shaffof rasmlarga tegmaymiz
                        continue
                    done.add(xref)
                    try:
                        info = doc.extract_image(xref)
                        if not info or len(info["image"]) < 50 * 1024:  # kichik rasmlar arzimaydi
                            continue
                        with Image.open(io.BytesIO(info["image"])) as im:
                            im = im.convert("RGB")
                            im.thumbnail((max_side, max_side))
                            buf = io.BytesIO()
                            im.save(buf, "JPEG", quality=quality, optimize=True)
                        if buf.tell() < len(info["image"]):
                            page.replace_image(xref, stream=buf.getvalue())
                    except Exception as e:  # bitta rasm xato bo'lsa, qolganlari davom etadi
                        logging.warning(f"PDF siqish: rasm {xref} o'tkazib yuborildi: {e}")
            doc.save(out_path, garbage=4, deflate=True, clean=True)
        after = os.path.getsize(out_path)
        if after >= before:  # foyda bo'lmasa, asl faylni qaytaramiz
            with open(pdf_path, "rb") as src, open(out_path, "wb") as dst:
                dst.write(src.read())
            after = before
        return before, after

    # ── Rasm formatini o'zgartirish ─────────────────────────────────────────
    @staticmethod
    def image_to_jpg(img_path: str, out_path: str) -> None:
        """HEIC, WEBP, PNG, BMP, TIFF → JPG."""
        try:
            image = ConverterService._open_image_rgb(img_path)
        except Exception as e:
            raise ConversionError("❌ Rasmni ochib bo'lmadi. Fayl buzilgan yoki format noma'lum.") from e
        try:
            image.save(out_path, "JPEG", quality=92, optimize=True)
        finally:
            image.close()


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB"):
        if n < 1024 or unit == "MB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
