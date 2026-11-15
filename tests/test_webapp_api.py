import unittest

from services.webapp_api import level_info, _iso


class WebAppApiTests(unittest.TestCase):
    def test_levels(self):
        self.assertEqual(level_info(0)["to_next"], 5)
        info = level_info(7)
        self.assertEqual((info["to_next"], info["progress"]), (13, 13))
        self.assertIn("Faol", info["label"])
        top = level_info(150)
        self.assertEqual((top["next_label"], top["progress"]), (None, 100))

    def test_iso_dates_for_all_browsers(self):
        self.assertEqual(_iso("2026-11-15 10:20:30"), "2026-11-15T10:20:30+05:00")
        self.assertEqual(_iso("2026-11-15 10:20:30.123456"), "2026-11-15T10:20:30+05:00")
        self.assertEqual(_iso(""), "")


if __name__ == "__main__":
    unittest.main()
