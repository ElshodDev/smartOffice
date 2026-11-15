import tempfile
import unittest
from pathlib import Path

from docx import Document

from services.transliterator import to_new_latin, transliterate_docx


class NewLatinTests(unittest.TestCase):
    def test_letters(self):
        self.assertEqual(to_new_latin("o'g'il"), "óǵil")
        self.assertEqual(to_new_latin("shahar choy"), "şahar çoy")
        self.assertEqual(to_new_latin("ming tong"), "miñ toñ")
        # n + g qo'shimcha chegarasida — ikki alohida tovush, ñ bo'lmaydi
        self.assertEqual(to_new_latin("Adminga menga cheklangan yuklangach"), "Adminga menga çeklangan yuklangaç")
        self.assertEqual(to_new_latin("Keyingi bugungi Ingliz"), "Keyingi bugungi Ingliz")
        self.assertEqual(to_new_latin("yangi dengiz sizning faylingiz so'nggi"), "yañi deñiz sizniñ fayliñiz sóñgi")

    def test_capitals(self):
        self.assertEqual(to_new_latin("O'zbekiston"), "Ózbekiston")
        self.assertEqual(to_new_latin("G'alaba Shahar Chorsu"), "Ǵalaba Şahar Çorsu")
        self.assertEqual(to_new_latin("TOSHKENT SHAHRI"), "TOŞKENT ŞAHRI")

    def test_apostrophe_variants(self):
        for mark in ("'", "‘", "’", "ʻ", "ʼ", "`"):
            self.assertEqual(to_new_latin(f"o{mark}g{mark}"), "óǵ")

    def test_tutuq_belgisi_untouched(self):
        # a', e' kabi tutuq belgilari o'zgarmaydi
        self.assertEqual(to_new_latin("ma'no ta'lim"), "ma'no ta'lim")
        # s'h — tutuq bilan ajratilgan, "ş" ga aylanmaydi
        self.assertEqual(to_new_latin("Is'hoq"), "Is'hoq")


class DocxTests(unittest.TestCase):
    def test_docx_keeps_formatting(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, dst = Path(tmp, "a.docx"), Path(tmp, "b.docx")
            doc = Document()
            paragraph = doc.add_paragraph()
            bold = paragraph.add_run("O'zbekiston ")
            bold.bold = True
            paragraph.add_run("shahar")
            table = doc.add_table(rows=1, cols=1)
            table.cell(0, 0).text = "choy"
            doc.sections[0].header.paragraphs[0].text = "g'alaba"
            doc.save(src)

            transliterate_docx(str(src), str(dst), to_new_latin)

            result = Document(dst)
            runs = result.paragraphs[0].runs
            self.assertEqual(runs[0].text, "Ózbekiston ")
            self.assertTrue(runs[0].bold)
            self.assertEqual(runs[1].text, "şahar")
            self.assertEqual(result.tables[0].cell(0, 0).text, "çoy")
            self.assertEqual(result.sections[0].header.paragraphs[0].text, "ǵalaba")


if __name__ == "__main__":
    unittest.main()
