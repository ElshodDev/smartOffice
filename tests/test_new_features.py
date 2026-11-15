import datetime as dt
import math
import os
import tempfile
import unittest
import zipfile

import cv2
import numpy as np
import pandas as pd
from docx import Document

from services.ai_text import clean_ai_text
from services.doc_generator import DOC_TYPES, body_paragraphs, build_docx
from services.doc_scanner import find_page, scan_image
from services.mass_fill import format_cell, generate_documents, make_sample_excel, match_columns


def doc_text(path):
    d = Document(path)
    return "\n".join([p.text for p in d.paragraphs] + [c.text for t in d.tables for r in t.rows for c in r.cells])


class DocGeneratorTests(unittest.TestCase):
    def test_every_type_builds_with_examples(self):
        with tempfile.TemporaryDirectory() as tmp:
            for key, doc in DOC_TYPES.items():
                values = {f.key: f.example for f in doc.fields}
                path = os.path.join(tmp, f"{key}.docx")
                build_docx(doc, values, body_paragraphs(doc, values, None), path, today=dt.date(2026, 11, 15))
                text = doc_text(path)
                self.assertIn(doc.heading, text, key)
                self.assertIn("15.11.2026", text, key)
                self.assertNotIn("{{", text, key)

    def test_optional_fields_can_be_empty(self):
        doc = DOC_TYPES["tushuntirish"]
        values = {f.key: ("" if f.optional else f.example) for f in doc.fields}
        body = body_paragraphs(doc, values, None)
        self.assertTrue(all(p.strip() for p in body))
        self.assertTrue(body[-1].endswith("."))

    def test_cyrillic(self):
        doc = DOC_TYPES["ariza_boshash"]
        values = {f.key: f.example for f in doc.fields}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "c.docx")
            build_docx(doc, values, body_paragraphs(doc, values, None), path, cyrillic=True)
            self.assertIn("АРИЗА", doc_text(path))

    def test_ai_text_cleaning(self):
        self.assertEqual(clean_ai_text("**Hurmatli** rahbar,\n\n\n\nso'rayman."), "Hurmatli rahbar,\n\nso'rayman.")
        for bad in ("Men [F.I.Sh] ...", "Sana: ____", "", "{{ism}}"):
            self.assertIsNone(clean_ai_text(bad))


class ScannerTests(unittest.TestCase):
    def _photo(self, path):
        page = np.full((1400, 1000, 3), 255, np.uint8)
        for i in range(20):
            cv2.putText(page, f"Line {i} hujjat matni", (60, 120 + i * 60), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (20, 20, 20), 2)
        bg = np.full((2000, 1600, 3), (60, 80, 110), np.uint8)
        src = np.float32([[0, 0], [1000, 0], [1000, 1400], [0, 1400]])
        dst = np.float32([[300, 250], [1350, 330], [1290, 1800], [220, 1700]])
        m = cv2.getPerspectiveTransform(src, dst)
        warped = cv2.warpPerspective(page, m, (1600, 2000))
        mask = cv2.warpPerspective(np.full((1400, 1000), 255, np.uint8), m, (1600, 2000))
        cv2.imwrite(path, np.where(mask[:, :, None] > 0, warped, bg))
        return dst

    def test_detects_page_and_flattens(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "photo.jpg")
            expected = self._photo(src)
            corners = find_page(cv2.imread(src))
            self.assertIsNotNone(corners)
            self.assertLess(np.abs(corners - expected).max(), 15)
            out = os.path.join(tmp, "scan.png")
            self.assertTrue(scan_image(src, out, "bw"))
            result = cv2.imread(out, cv2.IMREAD_GRAYSCALE)
            h, w = result.shape
            self.assertAlmostEqual(h / w, 1.4, delta=0.1)
            self.assertGreater((result > 200).mean(), 0.8)   # oq fon
            self.assertGreater((result < 60).mean(), 0.01)   # matn saqlangan

    def test_no_page_found_uses_whole_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "flat.jpg")
            cv2.imwrite(src, np.full((600, 400, 3), 230, np.uint8))
            self.assertFalse(scan_image(src, os.path.join(tmp, "out.jpg"), "color"))


class MassFillTests(unittest.TestCase):
    def test_format_cell(self):
        self.assertEqual(format_cell(95.0), "95")
        self.assertEqual(format_cell(9.5), "9.5")
        self.assertEqual(format_cell(math.nan), "")
        self.assertEqual(format_cell(pd.NaT), "")
        self.assertEqual(format_cell(pd.Timestamp("2026-11-15")), "15.11.2026")
        self.assertEqual(format_cell(" Ali "), "Ali")

    def test_match_columns(self):
        matched, missing = match_columns(["F.I.Sh", "o'qituvchi", "sana"], ["f.i.sh", "O‘qituvchi", "Izoh"])
        self.assertEqual(matched, ["F.I.Sh", "o'qituvchi"])
        self.assertEqual(missing, ["sana"])

    def test_generate_documents(self):
        with tempfile.TemporaryDirectory() as tmp:
            tpl = os.path.join(tmp, "t.docx")
            d = Document()
            d.add_paragraph("Hurmatli {{ism}}, sana {{sana}}")
            d.save(tpl)
            sample = os.path.join(tmp, "s.xlsx")
            make_sample_excel(["ism", "sana"], sample)
            self.assertEqual(list(pd.read_excel(sample).columns), ["ism", "sana"])
            xl = os.path.join(tmp, "r.xlsx")
            pd.DataFrame({"Ism": ["Ali", "Vali"], "Sana": [pd.Timestamp("2026-01-02"), None]}).to_excel(xl, index=False)
            zip_path, count = generate_documents(tpl, xl, tmp, "t", 0)
            self.assertEqual(count, 2)
            with zipfile.ZipFile(zip_path) as z:
                self.assertEqual(sorted(z.namelist()), ["001_Ali.docx", "002_Vali.docx"])
                text = Document(z.open("001_Ali.docx")).paragraphs[0].text
                self.assertEqual(text, "Hurmatli Ali, sana 02.01.2026")


if __name__ == "__main__":
    unittest.main()
