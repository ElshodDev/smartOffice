import tempfile
import unittest
from pathlib import Path

from services import database


class FormSessionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.database_path = database.DB_PATH
        self.temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_file.close()
        database.DB_PATH = self.temp_file.name
        await database.create_table()

    async def asyncTearDown(self):
        database.DB_PATH = self.database_path
        Path(self.temp_file.name).unlink(missing_ok=True)

    async def test_session_is_bound_to_user_and_consumed_once(self):
        token = await database.create_form_session(7, "form.png")

        self.assertEqual(
            await database.get_form_session(token),
            {"user_id": 7, "filename": "form.png"},
        )
        self.assertIsNone(await database.get_form_session("wrong-token"))
        self.assertTrue(await database.consume_form_session(token, 7, "form.png"))
        self.assertFalse(await database.consume_form_session(token, 7, "form.png"))
        self.assertIsNone(await database.get_form_session(token))
