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
        for table in ("users", "reminders", "form_sessions", "schema_migrations"):
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
