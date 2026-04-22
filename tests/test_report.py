import tempfile
import unittest
from pathlib import Path

from suite.report import format_report


class ReportFormattingTests(unittest.TestCase):
    def test_report_header_includes_run_provenance(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            report = format_report(
                "dates",
                "AGT_DATES_20260422_1431_8F3A2C1D",
                {"status": "completed", "summary": "done"},
                {"passed": False, "checks": [{"check": "exists", "passed": False, "dataset": "Dates_with_expiration"}]},
                project_name="[Agent Test] dates | claude-vanilla | 2026-04-22 14:31",
                profile_name="claude-vanilla",
                agent_command="/usr/bin/python3 /tmp/agents/claude.py",
                harness_repo_root=repo_root,
            )

        self.assertIn("Project Name: [Agent Test] dates | claude-vanilla | 2026-04-22 14:31", report)
        self.assertIn("Setup: claude-vanilla", report)
        self.assertIn("Agent: claude", report)
        self.assertIn("Agent Workspace: none (fresh temporary workspace)", report)
        self.assertIn("Runner: bundled claude wrapper", report)
        self.assertIn("Test Harness: ", report)
        self.assertIn("Execution: completed", report)
        self.assertNotIn("Agent: completed", report)


if __name__ == "__main__":
    unittest.main()
