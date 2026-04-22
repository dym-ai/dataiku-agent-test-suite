import contextlib
import io
import json
import tempfile
import time
import unittest
from pathlib import Path

from suite.batch import run_batch


class BatchRunTests(unittest.TestCase):
    def test_run_batch_writes_thin_manifest_and_relative_run_paths(self):
        calls = []

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            def run_one(case_name, profile, child_artifacts_root):
                calls.append((case_name, profile["profile_name"], child_artifacts_root))
                run_dir = child_artifacts_root / (
                    f"run__{case_name}__{profile['profile_name']}__2026-04-20T00-00-00Z__abcd1234"
                )
                run_dir.mkdir(parents=True, exist_ok=True)
                return {
                    "passed": not (case_name == "crane" and profile["profile_name"] == "cli-codex"),
                    "artifact_dir": str(run_dir),
                    "case_name": case_name,
                    "profile_name": profile["profile_name"],
                    "project_key": f"COBUILD_{case_name.upper()}",
                }

            with contextlib.redirect_stdout(io.StringIO()):
                result = run_batch(
                    run_one,
                    ["dates", "crane"],
                    [
                        {"profile_name": "codex-vanilla"},
                        {"profile_name": "cli-codex"},
                    ],
                    artifacts_root=temp_path / "artifacts",
                )

            self.assertFalse(result["passed"])
            self.assertEqual(
                [(case, profile) for case, profile, _ in calls],
                [
                    ("dates", "codex-vanilla"),
                    ("dates", "cli-codex"),
                    ("crane", "codex-vanilla"),
                    ("crane", "cli-codex"),
                ],
            )
            self.assertTrue(result["batch_artifact_dir"])

            batch_dir = Path(result["batch_artifact_dir"])
            manifest = json.loads((batch_dir / "batch_manifest.json").read_text())
            report = (batch_dir / "report.txt").read_text()

            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual(manifest["max_parallel"], 1)
            self.assertEqual(manifest["cases"], ["dates", "crane"])
            self.assertEqual(manifest["profiles"], ["codex-vanilla", "cli-codex"])
            self.assertEqual(manifest["run_count"], 4)
            self.assertEqual(manifest["passed_run_count"], 3)
            self.assertEqual(manifest["failed_run_count"], 1)
            self.assertEqual(manifest["runs"][0]["artifact_dir"].split("/")[0], "runs")
            self.assertIn("Batch:", report)
            self.assertIn("Max parallel: 1", report)
            self.assertIn("- FAIL crane x cli-codex", report)

    def test_single_case_batch_writes_compare_outputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            def run_one(case_name, profile, child_artifacts_root):
                run_dir = child_artifacts_root / (
                    f"run__{case_name}__{profile['profile_name']}__2026-04-20T00-00-00Z__abcd1234"
                )
                run_dir.mkdir(parents=True, exist_ok=True)
                manifest = {
                    "schema_version": 1,
                    "run_id": "abcd1234",
                    "case_name": case_name,
                    "profile_name": profile["profile_name"],
                    "passed": True,
                    "execution_result": {
                        "status": "completed",
                        "duration_ms": 1000,
                        "total_tokens": 10,
                        "tool_uses": 2,
                    },
                }
                (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
                return {
                    "passed": True,
                    "artifact_dir": str(run_dir),
                    "case_name": case_name,
                    "profile_name": profile["profile_name"],
                    "project_key": f"COBUILD_{case_name.upper()}",
                }

            with contextlib.redirect_stdout(io.StringIO()):
                result = run_batch(
                    run_one,
                    ["dates"],
                    [
                        {"profile_name": "codex-vanilla"},
                        {"profile_name": "cli-codex"},
                    ],
                    artifacts_root=temp_path / "artifacts",
                )

            batch_dir = Path(result["batch_artifact_dir"])
            self.assertTrue((batch_dir / "compare_summary.json").is_file())
            self.assertTrue((batch_dir / "compare_report.txt").is_file())

    def test_run_batch_parallel_preserves_submission_order(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            def run_one(case_name, profile, child_artifacts_root):
                delay = 0.05 if profile["profile_name"] == "slow-profile" else 0.01
                time.sleep(delay)
                run_dir = child_artifacts_root / (
                    f"run__{case_name}__{profile['profile_name']}__2026-04-20T00-00-00Z__abcd1234"
                )
                run_dir.mkdir(parents=True, exist_ok=True)
                manifest = {
                    "schema_version": 1,
                    "run_id": "abcd1234",
                    "case_name": case_name,
                    "profile_name": profile["profile_name"],
                    "passed": True,
                    "execution_result": {
                        "status": "completed",
                        "duration_ms": 1000,
                        "total_tokens": 10,
                        "tool_uses": 2,
                    },
                }
                (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
                return {
                    "passed": True,
                    "artifact_dir": str(run_dir),
                    "case_name": case_name,
                    "profile_name": profile["profile_name"],
                    "project_key": f"AGT_{case_name.upper()}",
                }

            with contextlib.redirect_stdout(io.StringIO()):
                result = run_batch(
                    run_one,
                    ["dates"],
                    [
                        {"profile_name": "slow-profile"},
                        {"profile_name": "fast-profile"},
                    ],
                    artifacts_root=temp_path / "artifacts",
                    max_parallel=2,
                )

            self.assertEqual(
                [entry["profile_name"] for entry in result["runs"]],
                ["slow-profile", "fast-profile"],
            )


if __name__ == "__main__":
    unittest.main()
