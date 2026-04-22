import json
import os
import unittest
from unittest.mock import patch

from suite.redaction import REDACTION_TOKEN, redact_text, redact_value
from suite.report import format_report


class RedactionTests(unittest.TestCase):
    def test_redacts_exact_secret_values_from_nested_structures(self):
        secret = "dku-secret-12345"
        payload = {
            "summary": f"Using {secret}",
            "stdout": f'{{"user_api_key":"{secret}","project_key":"COBUILD"}}',
            "stderr": f"token={secret}",
            "tool_trace": [
                {
                    "name": "custom-tool",
                    "input": {
                        "token": secret,
                        "project_key": "COBUILD",
                    },
                }
            ],
        }

        redacted = redact_value(payload, secret_values=[secret])

        self.assertNotIn(secret, json.dumps(redacted))
        self.assertIn(REDACTION_TOKEN, json.dumps(redacted))
        self.assertEqual(redacted["tool_trace"][0]["input"]["project_key"], "COBUILD")

    def test_redacts_common_auth_patterns_without_known_secret_values(self):
        text = "\n".join(
            [
                "Authorization: Bearer abc123token",
                '{"user_api_key":"xyz789"}',
                "api_key=shh-secret",
                "https://user:password@example.com/path",
            ]
        )

        redacted = redact_text(text, secret_values=[])

        self.assertNotIn("abc123token", redacted)
        self.assertNotIn("xyz789", redacted)
        self.assertNotIn("shh-secret", redacted)
        self.assertNotIn("password@", redacted)
        self.assertIn(REDACTION_TOKEN, redacted)

    def test_format_report_redacts_verbose_agent_output(self):
        secret = "dku-secret-12345"
        agent_result = {
            "status": "completed",
            "summary": f"Used {secret}",
            "stdout": f"Authorization: Bearer {secret}",
            "stderr": f'{{"user_api_key":"{secret}"}}',
            "tool_trace": [
                {
                    "name": "custom-tool",
                    "input": {
                        "token": secret,
                        "project_key": "COBUILD",
                    },
                }
            ],
        }
        validation_result = {"passed": True, "checks": []}

        with patch.dict(os.environ, {"DATAIKU_API_KEY": secret}, clear=False):
            report = format_report(
                "dates",
                "COBUILD_DATES",
                agent_result,
                validation_result,
                project_name="[Agent Test] dates | claude-vanilla | 2026-04-22 12:07",
                profile_name="claude-vanilla",
                agent_command="claude",
                verbose=True,
            )

        self.assertNotIn(secret, report)
        self.assertIn(REDACTION_TOKEN, report)
        self.assertIn("COBUILD", report)
        self.assertIn("Profile: claude-vanilla", report)
        self.assertIn("Coding Agent: claude", report)
        self.assertIn("Execution: completed", report)


if __name__ == "__main__":
    unittest.main()
