import unittest

from services import onboarding


class OnboardingTests(unittest.TestCase):
    def test_tip_skips_sections_already_used(self):
        self.assertEqual(onboarding.pick_tip("scan", set())[0], "format")
        self.assertEqual(onboarding.pick_tip("scan", {"format"})[0], "ocr")
        self.assertIsNone(onboarding.pick_tip("scan", {"format", "ocr"}))
        self.assertIsNone(onboarding.pick_tip("ai", set()))

    def test_tips_point_to_real_sections(self):
        from handlers.ai_assistant import SECTIONS
        for section, tips in onboarding.TIPS.items():
            for key, text in tips:
                self.assertIn(key, SECTIONS, f"{section} → {key}")
                self.assertNotEqual(key, section)
        for key, _ in onboarding.CHOICES:
            self.assertIn(key, SECTIONS)
        self.assertTrue(all(len(f"onb:{k}") <= 64 for k, _ in onboarding.CHOICES))


if __name__ == "__main__":
    unittest.main()
