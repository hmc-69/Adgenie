import asyncio
import unittest
from unittest.mock import patch

from fastapi import FastAPI

from app.core.config import settings, validate_security_configuration
from app.core.security import create_access_token, decode_access_token
from app.main import lifespan


class StartupConfigurationTests(unittest.TestCase):
    def test_jwt_secret_requires_explicit_strong_value(self):
        for secret in (
            None,
            "short",
            "a" * 48,
            "replace-with-a-generated-random-secret-of-at-least-32-characters",
            "adgenie_jwt_super_secret_key_2026_marketing_intel_secure_key",
        ):
            with self.subTest(secret_is_set=secret is not None), patch.object(settings, "JWT_SECRET_KEY", secret):
                with self.assertRaisesRegex(RuntimeError, "JWT_SECRET_KEY"):
                    validate_security_configuration()

    def test_valid_jwt_secret_is_accepted(self):
        with patch.object(settings, "JWT_SECRET_KEY", "test-only-secret-83f4a92de6c712b0f5a1c8d3"):
            validate_security_configuration()
            token = create_access_token(17)
            self.assertEqual(decode_access_token(token)["sub"], "17")

    def test_database_initialization_runs_before_application_serves(self):
        async def exercise():
            with patch("app.main.validate_security_configuration") as security, patch(
                "app.main.Base.metadata.create_all"
            ) as create_all, patch("app.main.ensure_creative_image_columns") as ensure:
                async with lifespan(FastAPI()):
                    security.assert_called_once_with()
                    create_all.assert_called_once()
                    ensure.assert_called_once_with()

        asyncio.run(exercise())

    def test_database_initialization_failure_propagates_and_stops_startup(self):
        async def exercise():
            with patch("app.main.validate_security_configuration"), patch(
                "app.main.Base.metadata.create_all", side_effect=RuntimeError("database unavailable")
            ), patch("app.main.ensure_creative_image_columns") as ensure:
                with self.assertRaisesRegex(RuntimeError, "database unavailable"):
                    async with lifespan(FastAPI()):
                        self.fail("Lifespan yielded despite database failure")
                ensure.assert_not_called()

        asyncio.run(exercise())


if __name__ == "__main__":
    unittest.main()
