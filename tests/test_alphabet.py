import unittest

from services.alphabet import convert, esc, raw, remember, original_text, convert_html_page
from middlewares import throttling


class ConvertTests(unittest.TestCase):
    def test_ui_text(self):
        self.assertEqual(convert("📁 Format o'zgartirish"), "📁 Format ózgartiriş")
        self.assertEqual(convert("Yangi foydalanuvchi qo'shildi, ming, tog'"), "Yañi foydalanuvçi qóşildi, miñ, toǵ")
        self.assertEqual(convert("O‘zbekiston SHAHAR"), "Ózbekiston ŞAHAR")

    def test_protected_parts(self):
        self.assertEqual(convert("<b>Yangi</b> <code>shablon</code>"), "<b>Yañi</b> <code>shablon</code>")
        self.assertEqual(convert("Natija: " + raw("Shahar choy")), "Natija: Shahar choy")
        self.assertEqual(convert("Ism: " + esc("Shoxrux <b>")), "Ism: Shoxrux &lt;b&gt;")
        self.assertEqual(convert("https://t.me/share @Elshod_Developer /done_pdf natija.docx"),
                         "https://t.me/share @Elshod_Developer /done_pdf natija.docx")
        self.assertEqual(convert("PNG, HEIC, Excel/Word, Inglizcha, Smart Office"), "PNG, HEIC, Excel/Word, Inglizcha, Smart Office")
        self.assertEqual(convert("«Kino» 'Kino'"), "«Kino» 'Kino'")

    def test_buttons_round_trip(self):
        shown = remember("📞 Adminga murojaat")
        self.assertEqual(shown, "📞 Adminga murojaat")
        shown = remember("⬅️ Orqaga qaytish")
        self.assertEqual(original_text(shown), "⬅️ Orqaga qaytish")
        self.assertEqual(original_text("oddiy matn"), "oddiy matn")

    def test_html_page_keeps_scripts(self):
        page = "<h1>Yangi</h1><script>const share = 'sh';</script><style>.ch{}</style>"
        self.assertEqual(convert_html_page(page), "<h1>Yañi</h1><script>const share = 'sh';</script><style>.ch{}</style>")


class ThrottleTests(unittest.TestCase):
    def test_album_counts_once(self):
        for _ in range(30):
            self.assertTrue(throttling.allow(1, "album", now=100.0))

    def test_burst_limit(self):
        results = [throttling.allow(2, now=200.0 + i * 0.1) for i in range(12)]
        self.assertEqual(results.count(True), throttling.MAX_EVENTS)
        self.assertTrue(throttling.allow(2, now=200.0 + throttling.WINDOW + 1.5))


if __name__ == "__main__":
    unittest.main()
