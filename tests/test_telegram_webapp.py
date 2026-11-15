import hashlib
import hmac
import json
import time
import unittest
from urllib.parse import urlencode

from src.shared.security.telegram_webapp import (
    WebAppAuthenticationError,
    validate_init_data,
)


class TelegramWebAppValidationTests(unittest.TestCase):
    def _signed_data(self, bot_token: str, user_id: int = 42) -> str:
        fields = {
            "auth_date": str(int(time.time())),
            "query_id": "query-1",
            "user": json.dumps({"id": user_id, "first_name": "Test"}),
        }
        data_check_string = "\n".join(
            f"{key}={value}" for key, value in sorted(fields.items())
        )
        secret_key = hmac.new(
            b"WebAppData", bot_token.encode(), hashlib.sha256
        ).digest()
        fields["hash"] = hmac.new(
            secret_key, data_check_string.encode(), hashlib.sha256
        ).hexdigest()
        return urlencode(fields)

    def test_valid_init_data_returns_user(self):
        user = validate_init_data(self._signed_data("secret"), "secret")
        self.assertEqual(user.id, 42)

    def test_tampered_init_data_is_rejected(self):
        init_data = self._signed_data("secret") + "&foo=bar"
        with self.assertRaises(WebAppAuthenticationError):
            validate_init_data(init_data, "secret")

    def test_expired_init_data_is_rejected(self):
        init_data = self._signed_data("secret")
        with self.assertRaises(WebAppAuthenticationError):
            validate_init_data(init_data, "secret", now=int(time.time()) + 86_401)


if __name__ == "__main__":
    unittest.main()
