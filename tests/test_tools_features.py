import datetime as dt
import os
import tempfile
import unittest

import cv2
import numpy as np
import pandas as pd

from handlers.search_data import _search
from handlers.utility_tools import make_qr_png
from services.timeutil import parse_user_time

NOW = dt.datetime(2026, 11, 15, 18, 0)


class ParseTimeTests(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(parse_user_time("19:30", NOW), dt.datetime(2026, 11, 15, 19, 30))
        self.assertEqual(parse_user_time("9:00", NOW), dt.datetime(2026, 11, 16, 9, 0))      # o'tgan → ertaga
        self.assertEqual(parse_user_time("ertaga 9.00", NOW), dt.datetime(2026, 11, 16, 9, 0))
        self.assertEqual(parse_user_time("20.11.2026 15:30", NOW), dt.datetime(2026, 11, 20, 15, 30))
        self.assertEqual(parse_user_time("01.01 10:00", NOW), dt.datetime(2027, 1, 1, 10, 0))   # keyingi yil
        self.assertEqual(parse_user_time("2026-12-31 23:59", NOW), dt.datetime(2026, 12, 31, 23, 59))

    def test_invalid(self):
        for bad in ("25:00", "31.02.2027 10:00", "qachondir", "", "12:60"):
            self.assertIsNone(parse_user_time(bad, NOW), bad)


class SearchTests(unittest.TestCase):
    def test_phone_numbers_dates_and_special_chars(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "s.xlsx")
            pd.DataFrame([
                {"Ism": "Ali <A> & Co", "Tel": 998901234567, "Sana": pd.Timestamp("2026-11-15"), "Ball": 95.0},
                {"Ism": "Vali (IT)", "Tel": "+998 91 222-33-44", "Sana": None, "Ball": None},
            ]).to_excel(path, index=False)
            out = os.path.join(tmp, "o.xlsx")
            for query, name in (("+998901234567", "Ali <A> & Co"), ("+998 91 222-33-44", "Vali (IT)"),
                                ("(IT)", "Vali (IT)"), ("15.11.2026", "Ali <A> & Co"), ("<A>", "Ali <A> & Co")):
                count, rows = _search(path, query, out)
                self.assertEqual(count, 1, query)
                self.assertEqual(dict(rows[0])["Ism"], name, query)
            count, rows = _search(path, "95", out)
            self.assertEqual(dict(rows[0])["Ball"], "95")       # 95.0 emas
            self.assertEqual(_search(path, "yo'q narsa", out)[0], 0)


class QrTests(unittest.TestCase):
    def test_roundtrip(self):
        text = "https://t.me/raqamli_ofis_bot?start=1"
        image = cv2.imdecode(np.frombuffer(make_qr_png(text), np.uint8), cv2.IMREAD_COLOR)
        self.assertEqual(cv2.QRCodeDetector().detectAndDecode(image)[0], text)


if __name__ == "__main__":
    unittest.main()
