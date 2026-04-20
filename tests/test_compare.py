import json
import tempfile
import unittest
from pathlib import Path

from suite.compare import compare_artifact_dirs


class CompareArtifactTests(unittest.TestCase):
    def test_compare_errors_with_fewer_than_two_runs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            run_dir = self._write_run_bundle(temp_path / "run-a", case_name="dates", profile_name="codex-vanilla")

            with self.assertRaisesRegex(ValueError, "at least 2 run bundles"):
                compare_artifact_dirs([run_dir])

    def test_compare_errors_when_case_names_differ(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            run_a = self._write_run_bundle(temp_path / "run-a", case_name="dates", profile_name="codex-vanilla")
            run_b = self._write_run_bundle(temp_path / "run-b", case_name="crane", profile_name="cli-codex")

            with self.assertRaisesRegex(ValueError, "exactly one case"):
                compare_artifact_dirs([run_a, run_b])

    def test_compare_writes_outputs_for_single_batch_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            batch_dir = temp_path / "batch__2026-04-20T00-00-00Z__abcd1234"
            runs_dir = batch_dir / "runs"
            runs_dir.mkdir(parents=True)
            self._write_batch_manifest(batch_dir, ["dates"], ["codex-vanilla", "cli-codex"])
            self._write_run_bundle(runs_dir / "run-a", case_name="dates", profile_name="codex-vanilla", passed=True, duration_ms=1000, total_tokens=10, tool_uses=2)
            self._write_run_bundle(runs_dir / "run-b", case_name="dates", profile_name="cli-codex", passed=False, duration_ms=2000, total_tokens=20, tool_uses=4)

            summary, report = compare_artifact_dirs([batch_dir], output_dir=batch_dir)

            self.assertEqual(summary["case_name"], "dates")
            self.assertEqual(summary["run_count"], 2)
            self.assertEqual(len(summary["profiles"]), 2)
            self.assertTrue((batch_dir / "compare_summary.json").is_file())
            self.assertTrue((batch_dir / "compare_report.txt").is_file())
            self.assertIn("Case: dates", report)
            self.assertIn("- FAIL cli-codex runs/run-b", report)

    def test_compare_summarizes_profile_medians(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            run_a = self._write_run_bundle(temp_path / "run-a", case_name="dates", profile_name="codex-vanilla", passed=True, duration_ms=1000, total_tokens=10, tool_uses=2)
            run_b = self._write_run_bundle(temp_path / "run-b", case_name="dates", profile_name="codex-vanilla", passed=False, duration_ms=3000, total_tokens=30, tool_uses=6)

            summary, _ = compare_artifact_dirs([run_a, run_b])

            self.assertEqual(summary["profiles"][0]["profile_name"], "codex-vanilla")
            self.assertEqual(summary["profiles"][0]["run_count"], 2)
            self.assertEqual(summary["profiles"][0]["pass_count"], 1)
            self.assertEqual(summary["profiles"][0]["fail_count"], 1)
            self.assertEqual(summary["profiles"][0]["median_duration_ms"], 2000.0)
            self.assertEqual(summary["profiles"][0]["median_total_tokens"], 20.0)
            self.assertEqual(summary["profiles"][0]["median_tool_uses"], 4.0)

    def _write_batch_manifest(self, batch_dir, cases, profiles):
        payload = {
            "schema_version": 1,
            "batch_id": "abcd1234",
            "cases": cases,
            "profiles": profiles,
            "runs": [],
        }
        (batch_dir / "batch_manifest.json").write_text(json.dumps(payload, indent=2) + "\n")

    def _write_run_bundle(
        self,
        run_dir,
        *,
        case_name,
        profile_name,
        passed=True,
        duration_ms=1000,
        total_tokens=10,
        tool_uses=2,
    ):
        run_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "schema_version": 1,
            "run_id": "abcd1234",
            "case_name": case_name,
            "profile_name": profile_name,
            "passed": passed,
            "execution_result": {
                "status": "completed" if passed else "failed",
                "duration_ms": duration_ms,
                "total_tokens": total_tokens,
                "tool_uses": tool_uses,
            },
        }
        (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        return run_dir


if __name__ == "__main__":
    unittest.main()
