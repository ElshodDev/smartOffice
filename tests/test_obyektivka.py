import io
import os
import tempfile
import unittest

import fitz
from PIL import Image

from services.obyektivka_photo import OUTPUT_PX, crop_box, make_photo
from services.pdf_report import generate_pdf, parse_work_line


class PhotoTests(unittest.TestCase):
    def test_crop_box_centres_face_with_3x4_ratio(self):
        left, top, right, bottom = crop_box(2000, 3000, (900, 1000, 200, 200))
        w, h = right - left, bottom - top
        self.assertAlmostEqual(w / h, 3 / 4, delta=0.01)
        self.assertAlmostEqual((left + right) / 2, 1000, delta=2)        # yuz markazi
        self.assertLess(top, 1000 - 200 * 0.45)                          # boshning tepasida bo'sh joy
        head_share = (200 * 1.6) / h
        self.assertAlmostEqual(head_share, 0.58, delta=0.01)

    def test_crop_box_without_face(self):
        left, top, right, bottom = crop_box(1200, 900, None)
        self.assertAlmostEqual((right - left) / (bottom - top), 3 / 4, delta=0.01)
        self.assertGreaterEqual(left, 0)
        self.assertLessEqual(right, 1200)

    def test_make_photo_output_size_and_dpi(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, dst = os.path.join(tmp, "s.jpg"), os.path.join(tmp, "d.jpg")
            Image.new("RGB", (800, 600), (200, 180, 160)).save(src)
            self.assertFalse(make_photo(src, dst))          # yuz yo'q — markazdan qirqiladi
            with Image.open(dst) as im:
                self.assertEqual(im.size, OUTPUT_PX)
                self.assertEqual(tuple(round(v) for v in im.info["dpi"]), (300, 300))


class WorkLineTests(unittest.TestCase):
    def test_periods(self):
        self.assertEqual(parse_work_line("2012-2014 yy. — «Ziyo» MChJ buxgalteri"), ("2012-2014 yy.", "«Ziyo» MChJ buxgalteri"))
        self.assertEqual(parse_work_line("2020 y. — h.v. — Bosh buxgalter"), ("2020 y. - h.v.", "Bosh buxgalter"))
        self.assertEqual(parse_work_line("2005—2010 yy.: Maktab"), ("2005-2010 yy.", "Maktab"))
        self.assertEqual(parse_work_line("1998 y. - talaba"), ("1998 y.", "talaba"))
        self.assertEqual(parse_work_line("Bosh buxgalter"), ("", "Bosh buxgalter"))


class PdfTests(unittest.TestCase):
    def test_standard_layout(self):
        photo = io.BytesIO()
        Image.new("RGB", OUTPUT_PX, "gray").save(photo, "JPEG")
        data = {
            "full_name": "Karimova Dilnoza", "current_position": "2020 yil 1 sentyabrdan: «Ziyo» MChJ bosh buxgalteri",
            "birth_place": "Toshkent viloyati, Qibray tumani, juda uzun manzil nomi bilan " * 2,
            "work_history": "2012-2014 yy. — «Ziyo» MChJ\n2020 y. — h.v. — Bosh buxgalter",
            "relatives": [{"rel": "Akasi", "name": "Каримов Бобур", "birth": "1993 й.", "work": "Тадбиркор", "address": "Тошкент"}],
        }
        doc = fitz.open(stream=generate_pdf(data, photo.getvalue()), filetype="pdf")
        self.assertEqual(doc.page_count, 2)
        rect = doc[0].get_image_rects(doc[0].get_images(full=True)[0][0])[0]
        self.assertEqual((round(rect.width / 72 * 25.4), round(rect.height / 72 * 25.4)), (30, 40))
        page1, page2 = doc[0].get_text(), doc[1].get_text()
        self.assertIn("2020 yil 1 sentyabrdan:", page1)
        self.assertIn("2012-2014 yy. -", page1)
        self.assertIn("«Ziyo»", page1)
        self.assertIn("Каримов Бобур", page2)      # kirill majburan lotinga o'girilmaydi
        # Uzun "Tug'ilgan joyi" rasm ustiga chiqmaydi
        photo_left = rect.x0
        for block in doc[0].get_text("blocks"):
            if "Qibray" in block[4]:
                self.assertLess(block[2], photo_left)

    def test_without_photo_and_relatives(self):
        doc = fitz.open(stream=generate_pdf({"full_name": "Ali"}), filetype="pdf")
        self.assertEqual(doc.page_count, 1)
        self.assertIn("3×4 rasm", doc[0].get_text())


if __name__ == "__main__":
    unittest.main()
