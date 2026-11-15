import os
import tempfile
import time
import unittest
import zipfile

import fitz
import pandas as pd
from docx import Document

from services import tempfiles
from services.docx_template import fill_template, template_placeholders
from services.excel_common import column_by_index, column_keyboard, unique_name
from services.pdf_service import PdfService, parse_page_ranges


class PageRangeTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(parse_page_ranges("1,3,5-7", 10), [1, 3, 5, 6, 7])
        self.assertEqual(parse_page_ranges("1-3, 8", 10), [1, 2, 3, 8])
        self.assertEqual(parse_page_ranges("7-5", 10), [5, 6, 7])

    def test_clamped_to_document(self):
        self.assertEqual(parse_page_ranges("1-100000000", 3), [1, 2, 3])
        self.assertEqual(parse_page_ranges("0, 4, 99", 3), [])

    def test_invalid(self):
        for bad in ("abc", "1-2-3", "x" * 300):
            with self.assertRaises(ValueError):
                parse_page_ranges(bad, 10)


class DocxTemplateTests(unittest.TestCase):
    def test_split_runs_apostrophes_tables_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, dst = os.path.join(tmp, "t.docx"), os.path.join(tmp, "o.docx")
            doc = Document()
            p = doc.add_paragraph("Hurmatli ")
            bold = p.add_run("{{")
            bold.bold = True
            p.add_run("ism")
            p.add_run("}}, {{o'qituvchi}}!")
            doc.add_table(rows=1, cols=1).cell(0, 0).text = "Sana: {{ Sana }} {{qolgan}}"
            doc.sections[0].header.paragraphs[0].text = "{{ism}}"
            doc.save(src)

            self.assertEqual(template_placeholders(src), ["ism", "o'qituvchi", "Sana", "qolgan"])
            fill_template(src, dst, {"ISM": "Ali", "o‘qituvchi": "Vali", "sana": "01.01.2026"})

            out = Document(dst)
            self.assertEqual(out.paragraphs[0].text, "Hurmatli Ali, Vali!")
            self.assertTrue(out.paragraphs[0].runs[1].bold)  # formatlash saqlandi
            self.assertEqual(out.tables[0].cell(0, 0).text, "Sana: 01.01.2026 {{qolgan}}")
            self.assertEqual(out.sections[0].header.paragraphs[0].text, "Ali")


class WatermarkTests(unittest.TestCase):
    def test_cyrillic_and_page_sizes(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "in.pdf")
            doc = fitz.open()
            doc.new_page(width=595, height=842)   # A4
            doc.new_page(width=842, height=595)   # albom
            doc.save(src)
            doc.close()
            out = os.path.join(tmp, "out.pdf")
            self.assertTrue(PdfService.add_watermark(src, out, "НАМУНА oʻgʻil", tmp))
            with fitz.open(out) as res:
                self.assertEqual(res.page_count, 2)
                for page in res:
                    self.assertIn("НАМУНА", page.get_text())
                    # matn sahifa markazida
                    rect = page.search_for("НАМУНА")[0]
                    centre = (rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2
                    self.assertAlmostEqual(centre[0], page.rect.width / 2, delta=page.rect.width * 0.25)
                    self.assertAlmostEqual(centre[1], page.rect.height / 2, delta=page.rect.height * 0.25)


class ExcelCommonTests(unittest.TestCase):
    def test_keyboard_uses_indexes(self):
        columns = ["Ташкилотнинг тўлиқ расмий номи ва манзили", 2024, "Unnamed: 2"]
        kb = column_keyboard(columns, "catcol")
        datas = [row[0].callback_data for row in kb.inline_keyboard]
        self.assertEqual(datas, ["catcol:0", "catcol:1", "catcol:2"])
        self.assertTrue(all(len(d.encode()) <= 64 for d in datas))
        self.assertEqual(column_by_index(columns, "catcol:1"), 2024)
        self.assertIsNone(column_by_index(columns, "catcol:9"))

    def test_unique_name(self):
        used = set()
        self.assertEqual(unique_name("a.xlsx", used), "a.xlsx")
        self.assertEqual(unique_name("A.xlsx", used), "A (2).xlsx")

    def test_category_split_keeps_empty_rows(self):
        from handlers.category_splitter import _split_by_column
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "x.xlsx")
            pd.DataFrame({"Viloyat": ["Toshkent", None, "Toshkent", "a/b", "a-b"], "N": [1, 2, 3, 4, 5]}).to_excel(src, index=False)
            zip_path, column, groups, empty, total = _split_by_column(src, tmp, "x", 0)
            with zipfile.ZipFile(zip_path) as z:
                names = z.namelist()
                rows = sum(len(pd.read_excel(z.open(n))) for n in names)
            self.assertEqual(rows, 5)
            self.assertEqual(empty, 1)
            self.assertEqual(len(names), len(set(n.lower() for n in names)))  # nomlar to'qnashmaydi


class TempfilesTests(unittest.TestCase):
    def test_unique_dirs_and_stale_cleanup(self):
        old_root = tempfiles.TEMP_ROOT
        with tempfile.TemporaryDirectory() as tmp:
            tempfiles.TEMP_ROOT = tmp
            try:
                a, b = tempfiles.new_job_dir("pdfmerge"), tempfiles.new_job_dir("pdfmerge")
                self.assertNotEqual(a, b)
                keep = os.path.join(tmp, "forms")
                os.makedirs(keep)
                old = time.time() - 3 * 3600
                for path in (a, keep):
                    os.utime(path, (old, old))
                self.assertEqual(tempfiles.cleanup_stale_jobs(), 1)
                self.assertFalse(os.path.exists(a))
                self.assertTrue(os.path.exists(b))
                self.assertTrue(os.path.exists(keep))   # boshqa papkalarga tegilmaydi
            finally:
                tempfiles.TEMP_ROOT = old_root

    def test_safe_filename(self):
        self.assertEqual(tempfiles.safe_filename('a/b:c*?"<>|'), "a-b-c")
        self.assertEqual(tempfiles.safe_filename("..."), "fayl")


if __name__ == "__main__":
    unittest.main()
