import asyncio
import os
import tempfile
import time
import unittest
import zipfile

import fitz
from PIL import Image

from services import converter_service as cs
from services.converter_service import ConverterService, ConversionError


def make_text_pdf(path, pages=1):
    doc = fitz.open()
    for i in range(pages):
        doc.new_page().insert_text((72, 72), f"Sahifa {i + 1}: O'zbekiston")
    doc.save(path)
    doc.close()


def make_photo_pdf(path, tmp):
    """Katta (siqilmagan) rasm joylangan PDF — skaner qilingan hujjatga o'xshash."""
    img_path = os.path.join(tmp, "big.png")
    Image.effect_noise((2400, 3200), 60).convert("RGB").save(img_path)
    doc = fitz.open()
    page = doc.new_page()
    page.insert_image(page.rect, filename=img_path)
    doc.save(path)
    doc.close()


class ConverterServiceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def p(self, name):
        return os.path.join(self.tmp, name)

    def test_images_to_pdf_multiple_formats(self):
        Image.new("RGBA", (300, 200), (255, 0, 0, 128)).save(self.p("a.png"))
        Image.new("RGB", (200, 300), "blue").save(self.p("b.jpg"))
        Image.new("RGB", (100, 100), "green").save(self.p("c.webp"))
        ConverterService.images_to_pdf([self.p("a.png"), self.p("b.jpg"), self.p("c.webp")], self.p("out.pdf"))
        with fitz.open(self.p("out.pdf")) as doc:
            self.assertEqual(doc.page_count, 3)
            # Sahifa o'lchami rasmga mos (yo'nalish saqlangan)
            self.assertGreater(doc[0].rect.width, doc[0].rect.height)
            self.assertLess(doc[1].rect.width, doc[1].rect.height)

    def test_images_to_pdf_exif_rotation(self):
        img = Image.new("RGB", (400, 200), "white")
        exif = img.getexif()
        exif[0x0112] = 6  # telefon: 90° burilgan
        img.save(self.p("rot.jpg"), exif=exif)
        ConverterService.images_to_pdf([self.p("rot.jpg")], self.p("out.pdf"))
        with fitz.open(self.p("out.pdf")) as doc:
            self.assertLess(doc[0].rect.width, doc[0].rect.height)

    def test_images_to_pdf_bad_file(self):
        with open(self.p("bad.jpg"), "wb") as f:
            f.write(b"not an image")
        with self.assertRaises(ConversionError):
            ConverterService.images_to_pdf([self.p("bad.jpg")], self.p("out.pdf"))

    @unittest.skipUnless(cs.HEIC_SUPPORTED, "pillow-heif o'rnatilmagan")
    def test_heic_to_jpg(self):
        Image.new("RGB", (120, 80), "orange").save(self.p("iphone.heic"))
        ConverterService.image_to_jpg(self.p("iphone.heic"), self.p("out.jpg"))
        with Image.open(self.p("out.jpg")) as im:
            self.assertEqual((im.format, im.size), ("JPEG", (120, 80)))

    def test_pdf_to_images_single_and_zip(self):
        make_text_pdf(self.p("one.pdf"), 1)
        files = ConverterService.pdf_to_images(self.p("one.pdf"), self.p("o1"), "one")
        self.assertTrue(files[0].endswith(".jpg"))

        make_text_pdf(self.p("three.pdf"), 3)
        files = ConverterService.pdf_to_images(self.p("three.pdf"), self.p("o3"), "three")
        self.assertTrue(files[0].endswith(".zip"))
        with zipfile.ZipFile(files[0]) as zf:
            self.assertEqual(sorted(zf.namelist()), ["three_001.jpg", "three_002.jpg", "three_003.jpg"])

    def test_page_limits(self):
        make_text_pdf(self.p("long.pdf"), cs.MAX_PDF2IMG_PAGES + 1)
        with self.assertRaises(ConversionError) as ctx:
            ConverterService.pdf_to_images(self.p("long.pdf"), self.p("o"), "long")
        self.assertIn("sahifa", str(ctx.exception))

    def test_encrypted_pdf(self):
        make_text_pdf(self.p("plain.pdf"))
        with fitz.open(self.p("plain.pdf")) as doc:
            doc.save(self.p("locked.pdf"), encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="123", owner_pw="123")
        with self.assertRaises(ConversionError) as ctx:
            cs.pdf_page_count(self.p("locked.pdf"))
        self.assertIn("parol", str(ctx.exception))

    def test_compress_photo_pdf(self):
        make_photo_pdf(self.p("scan.pdf"), self.tmp)
        before, after = ConverterService.compress_pdf(self.p("scan.pdf"), self.p("small.pdf"))
        self.assertLess(after, before * 0.5)
        with fitz.open(self.p("small.pdf")) as doc:
            self.assertEqual(doc.page_count, 1)
            self.assertEqual(len(doc[0].get_images()), 1)

    def test_compress_never_grows(self):
        make_text_pdf(self.p("text.pdf"))
        before, after = ConverterService.compress_pdf(self.p("text.pdf"), self.p("out.pdf"))
        self.assertLessEqual(after, before)
        self.assertEqual(os.path.getsize(self.p("out.pdf")), after)

    def test_pdf_has_text(self):
        make_text_pdf(self.p("t.pdf"))
        make_photo_pdf(self.p("s.pdf"), self.tmp)
        self.assertTrue(cs.pdf_has_text(self.p("t.pdf")))
        self.assertFalse(cs.pdf_has_text(self.p("s.pdf")))

    def test_human_size(self):
        self.assertEqual(cs.human_size(500), "500 B")
        self.assertEqual(cs.human_size(2048), "2.0 KB")
        self.assertEqual(cs.human_size(5 * 1024 * 1024), "5.0 MB")


class RunHeavyTests(unittest.IsolatedAsyncioTestCase):
    async def test_event_loop_not_blocked_and_jobs_serialized(self):
        gaps, running, peak = [], [0], [0]

        def job():
            running[0] += 1
            peak[0] = max(peak[0], running[0])
            time.sleep(0.3)
            running[0] -= 1

        async def heartbeat():
            last = time.perf_counter()
            for _ in range(15):
                await asyncio.sleep(0.05)
                now = time.perf_counter()
                gaps.append(now - last)
                last = now

        await asyncio.gather(heartbeat(), cs.run_heavy(job), cs.run_heavy(job))
        self.assertLess(max(gaps), 0.2)   # bot javob berishda davom etdi
        self.assertEqual(peak[0], 1)      # bir vaqtda faqat bitta og'ir ish


if __name__ == "__main__":
    unittest.main()
