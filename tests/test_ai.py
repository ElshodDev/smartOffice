import os
import unittest
from unittest import mock

from services import gemini
from services.ai_format import extract_sections, split_for_telegram, strip_html, to_telegram


class FormatTests(unittest.TestCase):
    def test_markdown_to_html(self):
        html_text = to_telegram("## Sarlavha\n\n**qalin** va *kursiv*, `=SUM(A1)`\n* band\n2*3*4 = 24, a < b & c")[0]
        self.assertIn("<b>Sarlavha</b>", html_text)
        self.assertIn("<b>qalin</b>", html_text)
        self.assertIn("<i>kursiv</i>", html_text)
        self.assertIn("<code>=SUM(A1)</code>", html_text)
        self.assertIn("• band", html_text)
        self.assertIn("2*3*4 = 24", html_text)          # ko'paytirish buzilmaydi
        self.assertIn("a &lt; b &amp; c", html_text)    # maxsus belgilar xavfsiz

    def test_code_block(self):
        self.assertEqual(to_telegram("```python\nprint('<x>')\n```")[0], "<pre>print('&lt;x&gt;')</pre>")

    def test_long_answer_split_keeps_tags_balanced(self):
        text = "\n\n".join(f"**Band {i}** " + "matn " * 150 for i in range(15))
        parts = to_telegram(text)
        self.assertGreater(len(parts), 1)
        for part in parts:
            self.assertLessEqual(len(part), 4000)
            self.assertEqual(part.count("<b>"), part.count("</b>"))

    def test_very_long_single_line(self):
        parts = split_for_telegram(["x" * 9000])
        self.assertTrue(all(len(p) <= 4000 for p in parts))
        self.assertEqual(sum(len(p) for p in parts), 9000)

    def test_sections(self):
        text, keys = extract_sections("Javob [[bo'lim:scan]] [[bo‘lim:PDF]] [[bo'lim:yoq]] [[bo'lim:scan]]", {"scan", "pdf"})
        self.assertEqual(keys, ["scan", "pdf"])
        self.assertEqual(text, "Javob")

    def test_strip_html(self):
        self.assertEqual(strip_html("<b>a</b> &lt;b&gt;"), "a <b>")


class LimitTests(unittest.TestCase):
    def setUp(self):
        gemini._usage.clear()

    def test_daily_limit_and_refund(self):
        with mock.patch.dict(os.environ, {"AI_DAILY_LIMIT": "2"}):
            self.assertTrue(gemini.consume(1))
            self.assertTrue(gemini.consume(1))
            self.assertFalse(gemini.consume(1))
            self.assertEqual(gemini.remaining(1), 0)
            gemini.refund(1)
            self.assertEqual(gemini.remaining(1), 1)
            self.assertTrue(gemini.consume(2))          # boshqa foydalanuvchi alohida
            self.assertTrue(gemini.consume(1, unlimited=True))

    def test_model_name_from_env(self):
        with mock.patch.dict(os.environ, {"GEMINI_MODEL": "gemini-x"}):
            self.assertEqual(gemini.model_name(), "gemini-x")
        with mock.patch.dict(os.environ, {"GEMINI_MODEL": ""}):
            self.assertEqual(gemini.model_name(), gemini.DEFAULT_MODEL)


class ErrorMappingTests(unittest.IsolatedAsyncioTestCase):
    async def _kind(self, exc):
        async def failing(*args, **kwargs):
            raise exc
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "k"}), mock.patch.object(gemini, "_call", failing):
            with self.assertRaises(gemini.AIError) as ctx:
                await gemini.generate("x")
        return ctx.exception.kind

    async def test_mapping(self):
        from google.genai import errors
        self.assertEqual(await self._kind(errors.APIError(429, {"error": {"message": "RESOURCE_EXHAUSTED"}})), "quota")
        self.assertEqual(await self._kind(errors.APIError(503, {"error": {"message": "overloaded"}})), "unavailable")
        self.assertEqual(await self._kind(errors.APIError(400, {"error": {"message": "bad"}})), "error")
        self.assertEqual(await self._kind(TimeoutError()), "unavailable")

    async def test_disabled_without_key(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            with self.assertRaises(gemini.AIError) as ctx:
                await gemini.generate("x")
        self.assertEqual(ctx.exception.kind, "disabled")



class KeywordSectionTests(unittest.TestCase):
    def test_keywords(self):
        from handlers.ai_assistant import keyword_sections
        self.assertEqual(keyword_sections("pdf yubormoqchiman"), ["pdf", "format"])
        self.assertEqual(keyword_sections("Telefon suratini PDF qilmoqchiman"), ["scan"])
        self.assertEqual(keyword_sections("Ishdan bo'shash arizasini qanday yozaman?"), ["docgen"])
        self.assertEqual(keyword_sections("Excel jadvaldan ism qidirish"), ["search", "excel"])
        self.assertEqual(keyword_sections("Bugun ob-havo qanday?"), [])


if __name__ == "__main__":
    unittest.main()
