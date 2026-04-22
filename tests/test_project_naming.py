import unittest
from datetime import datetime, timedelta, timezone

from evals import _build_project_key, _build_project_name


class ProjectNamingTests(unittest.TestCase):
    def test_build_project_key_uses_agent_test_prefix_case_and_timestamp(self):
        now = datetime(2026, 4, 22, 14, 31, tzinfo=timezone(timedelta(hours=-7)))

        key = _build_project_key("joins_and-dates", now=now, suffix="8f3a2c1d")

        self.assertEqual(key, "AGT_JOINS_AND_DATES_20260422_1431_8F3A2C1D")

    def test_build_project_name_is_human_readable_and_includes_profile(self):
        now = datetime(2026, 4, 22, 14, 31, tzinfo=timezone(timedelta(hours=-7)))

        name = _build_project_name("joins_and-dates", profile_name="claude-vanilla", now=now)

        self.assertEqual(name, "[Agent Test] joins and dates | claude-vanilla | 2026-04-22 14:31")


if __name__ == "__main__":
    unittest.main()
