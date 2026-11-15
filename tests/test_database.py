"""
Baza funksiyalari testlari. SQLite'da har doim ishlaydi; PostgreSQL'da — TEST_DATABASE_URL berilsa
(masalan: postgresql://user:pass@127.0.0.1/testdb). Diqqat: PostgreSQL testi jadvallarni tozalaydi.
"""
import os
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest import mock

from services import database, db


class _DatabaseContract:
    """Ikkala baza uchun umumiy tekshiruvlar."""

    async def test_users(self):
        self.assertTrue(await database.add_user(111, "Ali", None))
        self.assertFalse(await database.add_user(111, "Ali qayta", None))   # takror qo'shilmaydi
        self.assertTrue(await database.add_user(5_000_000_000, "Katta ID", 111))  # BIGINT
        self.assertEqual(await database.get_users_count(), 2)
        self.assertEqual(sorted(await database.get_all_users()), [111, 5_000_000_000])
        profile = await database.get_user_profile(5_000_000_000)
        self.assertEqual((profile["name"], profile["referrer_id"]), ("Katta ID", 111))
        self.assertEqual([u["id"] for u in await database.get_recent_users(10)], [5_000_000_000, 111])
        self.assertEqual(await database.increment_usage(111), 1)
        self.assertIsNone(await database.get_user_profile(999))

    async def test_reminders_and_cache(self):
        await database.add_reminder(7, "Ertangi", "2026-11-16 09:00:00")
        await database.add_reminder(7, "Bugungi", "2026-11-15 18:00:00")
        await database.add_reminder(8, "Boshqa odam", "2026-11-15 18:00:00")
        self.assertEqual([r[1] for r in await database.get_user_reminders(7)], ["Bugungi", "Ertangi"])

        # Vaqti kelmagan — bazaga umuman murojaat qilinmaydi
        await database.get_due_reminders("2026-11-15 17:00:00")    # keshni to'ldiradi
        backend = database._db()
        with mock.patch.object(type(backend), "fetchall", side_effect=AssertionError("bazaga so'rov!")), \
             mock.patch.object(type(backend), "fetchone", side_effect=AssertionError("bazaga so'rov!")):
            self.assertEqual(await database.get_due_reminders("2026-11-15 17:59:00"), [])

        due = await database.get_due_reminders("2026-11-15 18:00:00")
        self.assertEqual(sorted(r[2] for r in due), ["Boshqa odam", "Bugungi"])
        for rem_id, _, _ in due:
            await database.mark_reminder_done(rem_id)
        self.assertEqual(await database.get_due_reminders("2026-11-15 23:00:00"), [])
        self.assertEqual([r[2] for r in await database.get_due_reminders("2026-11-16 09:00:00")], ["Ertangi"])

        rem_id = (await database.get_user_reminders(7))[0][0]
        self.assertFalse(await database.delete_reminder(rem_id, 8))   # birovniki
        self.assertTrue(await database.delete_reminder(rem_id, 7))
        self.assertEqual(await database.get_user_reminders(7), [])

    async def test_form_sessions(self):
        token = await database.create_form_session(7, "form.jpg")
        self.assertEqual(await database.get_form_session(token), {"user_id": 7, "filename": "form.jpg"})
        self.assertFalse(await database.consume_form_session(token, 8, "form.jpg"))
        self.assertTrue(await database.consume_form_session(token, 7, "form.jpg"))
        self.assertFalse(await database.consume_form_session(token, 7, "form.jpg"))
        expired = await database.create_form_session(7, "old.jpg", ttl=timedelta(seconds=-1))
        self.assertIsNone(await database.get_form_session(expired))
        self.assertEqual(sorted(await database.cleanup_expired_form_sessions()), ["form.jpg", "old.jpg"])

    async def test_activity_and_admin_stats(self):
        await database.add_user(1, "Ali", None)
        await database.add_user(2, "Vali", 1)
        await database.touch_users([(2, "Vali", "2026-11-15 10:00:00"), (3, "Yangi odam", "2026-11-15 11:00:00")])
        self.assertEqual(await database.get_users_count(), 3)            # /start bosmagan ham qo'shildi
        await database.add_section_uses([(2, "pdf", 2, "2026-11-15 10:00:00"), (3, "pdf", 1, "2026-11-15 11:00:00"),
                                         (2, "ocr", 1, "2026-11-15 10:00:00")])
        await database.add_section_uses([(2, "pdf", 1, "2026-11-15 12:00:00")])
        self.assertEqual(await database.get_user_sections(2), {"pdf": 3, "ocr": 1})
        self.assertEqual((await database.get_user_profile(2))["usage_count"], 4)
        self.assertEqual(await database.count_referrals(1), 1)
        self.assertEqual(await database.top_sections(), [("pdf", 2, 4), ("ocr", 1, 1)])
        self.assertEqual(await database.top_referrers(), [(1, "Ali", 1)])
        stats = await database.admin_stats("2026-11-15 00:00:00", "2026-11-09 00:00:00", "2026-10-17 00:00:00")
        self.assertEqual((stats["total"], stats["active_day"], stats["referred"]), (3, 2, 1))

        await database.mark_bot_blocked([3])
        self.assertTrue(await database.set_banned(2, True))
        self.assertFalse(await database.set_banned(999, True))
        self.assertEqual(await database.get_banned_ids(), {2})
        self.assertEqual(await database.get_broadcast_targets(), [1])
        await database.touch_users([(3, "Yangi odam", "2026-11-16 09:00:00")])   # qaytib keldi
        self.assertEqual(sorted(await database.get_broadcast_targets()), [1, 3])
        self.assertEqual([u["id"] for u in await database.find_users("vali")], [2])
        self.assertEqual((await database.find_users("3"))[0]["name"], "Yangi odam")
        self.assertEqual(len(await database.export_users()), 3)

    async def test_webapp_queries(self):
        await database.add_user(1, "Ali", None)
        await database.touch_users([(1, "Ali", "2026-11-14 09:00:00"), (2, "Vali", "2026-11-15 10:00:00")])
        await database.touch_users([(1, "Ali", "2026-11-15 12:00:00")])
        series = await database.daily_series("2026-11-14")
        self.assertEqual(series["2026-11-14"]["active"], 1)
        self.assertEqual(series["2026-11-15"]["active"], 2)
        self.assertEqual(sum(p["new"] for p in series.values()), 2)
        # Ali ilgari qo'shilgan va bugun yana kirdi (qo'shilgan sanasi — bugun; shuning uchun 0 yoki 1)
        self.assertIn(await database.returning_users("2026-11-15 00:00:00"), (0, 1))
        total, users = await database.list_users(sort="active")
        self.assertEqual((total, [u["id"] for u in users]), (2, [1, 2]))
        total, users = await database.list_users(query="val")
        self.assertEqual((total, users[0]["name"]), (1, "Vali"))
        total, users = await database.list_users(query="2")
        self.assertEqual([u["id"] for u in users], [2])
        total, users = await database.list_users(limit=1, offset=1, sort="joined")
        self.assertEqual((total, len(users)), (2, 1))

    async def test_onboarding_queries(self):
        self.assertTrue(await database.set_flag(1, "onb:scan"))
        self.assertFalse(await database.set_flag(1, "onb:scan"))          # bir marta
        await database.set_flag(2, "onb:scan")
        await database.set_flag(2, "tip:format")
        self.assertTrue(await database.has_flag(2, "tip:format"))
        self.assertEqual(await database.count_flags(2, "tip:"), 1)
        self.assertEqual(await database.flag_stats("onb:", "2000-01-01"), [("scan", 2)])

        # 3 ta yangi foydalanuvchi: biri darhol ishlatdi va ertasi qaytdi, biri 2 kundan keyin, biri umuman
        await database.touch_users([(10, "A", "2026-11-10 09:00:00"), (11, "B", "2026-11-10 09:00:00"),
                                    (12, "C", "2026-11-10 09:00:00")])
        await database.add_section_uses([(10, "scan", 1, "2026-11-10 09:05:00")])
        await database.touch_users([(10, "A", "2026-11-11 08:00:00")])
        await database.add_section_uses([(11, "pdf", 1, "2026-11-12 10:00:00")])
        await database.touch_users([(11, "B", "2026-11-12 10:00:00")])
        o = await database.onboarding_stats("2026-11-09 00:00:00", "2026-11-15 12:00:00")
        self.assertEqual(o, {"joined": 3, "activated": 1, "eligible": 3, "returned": 2})

        nudge = await database.users_to_nudge("2026-11-01 00:00:00", "2026-11-12 09:00:00")
        self.assertEqual([u for u, _ in nudge], [10, 12])               # B 12-noyabrda kirgan
        await database.set_flag(12, "nudge")
        await database.mark_bot_blocked([10])
        self.assertEqual(await database.users_to_nudge("2026-11-01 00:00:00", "2026-11-12 09:00:00"), [])

    async def test_migrations_are_idempotent(self):
        await database.create_table()
        await database.create_table()
        self.assertEqual(await database.get_users_count(), 0)


class SqliteDatabaseTests(_DatabaseContract, unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._env = mock.patch.dict(os.environ, {"DATABASE_URL": ""})
        self._env.start()
        self.old_path = database.DB_PATH
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        handle.close()
        self.path = handle.name
        database.DB_PATH = self.path
        await database.create_table()

    async def asyncTearDown(self):
        database.DB_PATH = self.old_path
        Path(self.path).unlink(missing_ok=True)
        self._env.stop()


@unittest.skipUnless(os.getenv("TEST_DATABASE_URL"), "TEST_DATABASE_URL berilmagan")
class PostgresDatabaseTests(_DatabaseContract, unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._env = mock.patch.dict(os.environ, {"DATABASE_URL": os.environ["TEST_DATABASE_URL"]})
        self._env.start()
        db._pg_backend = None
        backend = database._db()
        for table in ("users", "reminders", "form_sessions", "user_sections", "daily_activity", "user_flags", "schema_migrations"):
            await backend.execute(f"DROP TABLE IF EXISTS {table}")
        await database.create_table()

    async def asyncTearDown(self):
        await db.close()
        db._pg_backend = None
        self._env.stop()


class UrlTests(unittest.TestCase):
    def test_neon_url_cleaned(self):
        url = ("postgresql://u:p@ep-x-pooler.eu-central-1.aws.neon.tech/neondb"
               "?sslmode=require&channel_binding=require")
        self.assertEqual(db.clean_pg_url(url), "postgresql://u:p@ep-x-pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require")
        self.assertTrue(db.clean_pg_url("postgres://u:p@h/d").startswith("postgresql://"))

    def test_placeholders(self):
        self.assertEqual(db._to_pg("SELECT ? , ? WHERE a = ?"), "SELECT $1 , $2 WHERE a = $3")

    def test_backend_choice(self):
        with mock.patch.dict(os.environ, {"DATABASE_URL": ""}):
            self.assertEqual(db.get_backend("x.db").dialect, "sqlite")
        with mock.patch.dict(os.environ, {"DATABASE_URL": "postgresql://u:p@h/d"}):
            self.assertEqual(db.get_backend("x.db").dialect, "postgres")
        db._pg_backend = None


if __name__ == "__main__":
    unittest.main()
