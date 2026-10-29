"""Tests for registered MCP resources."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from mcp_examples.resources.sample_resources import get_cognito_status


class CognitoStatusResourceTests(unittest.TestCase):
    def test_reports_missing_variable_names_without_values(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            payload = get_cognito_status()

        self.assertFalse(payload["required_settings_present"])
        self.assertEqual(
            payload["missing"],
            [
                "COGNITO_REGION",
                "COGNITO_USER_POOL_ID",
                "COGNITO_CLIENT_ID",
                "COGNITO_DOMAIN",
                "COGNITO_REDIRECT_URI",
            ],
        )

    def test_does_not_return_configured_values(self) -> None:
        values = {
            "COGNITO_REGION": "us-west-2-private",
            "COGNITO_USER_POOL_ID": "us-west-2_PrivatePool",
            "COGNITO_CLIENT_ID": "private-client-id",
            "COGNITO_DOMAIN": "https://private.auth.us-west-2.amazoncognito.com",
            "COGNITO_REDIRECT_URI": "https://private.example/auth/callback",
        }
        with patch.dict("os.environ", values, clear=True):
            payload = get_cognito_status()

        serialized = json.dumps(payload)
        self.assertTrue(payload["required_settings_present"])
        self.assertEqual(payload["missing"], [])
        for value in values.values():
            self.assertNotIn(value, serialized)


if __name__ == "__main__":
    unittest.main()
