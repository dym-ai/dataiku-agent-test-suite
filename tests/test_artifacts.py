import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from suite.artifacts import summarize_execution_result, write_run_artifacts
from suite.workspaces import StagedWorkspace


class ArtifactWritingTests(unittest.TestCase):
    def test_write_run_artifacts_writes_manifest_and_separate_payloads(self):
        started_at = datetime(2026, 4, 19, 12, 30, 0, tzinfo=timezone.utc)
        finished_at = datetime(2026, 4, 19, 12, 31, 5, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            artifacts_root = temp_path / "artifacts"
            case_path = temp_path / "case.json"
            case_path.write_text('{"name":"dates"}\n')
            source_workspace = temp_path / "source-workspace"
            source_workspace.mkdir()
            run_workspace = temp_path / "run-workspace"
            run_workspace.mkdir()

            artifact_dir = write_run_artifacts(
                artifacts_root,
                case_name="dates",
                case_path=case_path,
                project_key="COBUILD_DATES_123",
                profile={
                    "name": "codex-vanilla",
                    "description": "Plain Codex profile",
                    "agent_command": "codex",
                    "agent_workspace": None,
                    "tags": ["codex", "vanilla"],
                    "dss_url": "https://dss.example.com",
                    "env_keys": ["DATAIKU_API_KEY", "DATAIKU_URL"],
                },
                request={
                    "version": 1,
                    "case_name": "dates",
                    "project_key": "COBUILD_DATES_123",
                    "workspace": str(run_workspace),
                },
                agent_result={
                    "status": "completed",
                    "summary": "done",
                    "stdout": "hello",
                    "stderr": "",
                    "agent_returncode": 0,
                    "stats": {
                        "duration_ms": 65000,
                        "total_tokens": 42,
                        "tool_uses": 3,
                    },
                },
                execution_result={
                    "status": "completed",
                    "agent_returncode": 0,
                    "timeout": False,
                    "launch_error": False,
                    "duration_ms": 65000,
                    "total_tokens": 42,
                    "tool_uses": 3,
                    "tool_uses_by_type": {},
                },
                validation_result={
                    "passed": True,
                    "checks": [
                        {"check": "exists", "passed": True, "dataset": "Dates_with_expiration"},
                    ],
                    "agent_stats": {"duration_ms": 65000},
                },
                overall_passed=True,
                report_text="Result: PASS",
                started_at=started_at,
                finished_at=finished_at,
                staged_workspace=StagedWorkspace(
                    source_workspace=source_workspace,
                    run_workspace=run_workspace,
                    is_copy=True,
                ),
                keep=False,
                harness_repo_root=temp_path,
            )

            manifest = json.loads((artifact_dir / "run_manifest.json").read_text())
            persisted_validation = json.loads((artifact_dir / "validation_result.json").read_text())
            persisted_agent = json.loads((artifact_dir / "agent_response.json").read_text())

            self.assertTrue(artifact_dir.name.startswith("run__dates__codex-vanilla__2026-04-19T12-30-00Z__"))
            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual(manifest["case_name"], "dates")
            self.assertEqual(manifest["profile_name"], "codex-vanilla")
            self.assertEqual(manifest["project"]["project_key"], "COBUILD_DATES_123")
            self.assertEqual(manifest["execution_result"]["status"], "completed")
            self.assertEqual(manifest["validation_result"]["check_count"], 1)
            self.assertEqual(manifest["validation_result"]["failed_check_count"], 0)
            self.assertEqual(manifest["workspace"]["source_path"], str(source_workspace))
            self.assertEqual(manifest["workspace"]["run_path"], str(run_workspace))
            self.assertEqual(manifest["profile"]["dss_url"], "https://dss.example.com")
            self.assertEqual(manifest["artifacts"]["run_manifest"], "run_manifest.json")
            self.assertTrue(manifest["case_digest"].startswith("sha256:"))
            self.assertTrue(manifest["profile_digest"].startswith("sha256:"))

            self.assertEqual(persisted_validation["checks"][0]["check"], "exists")
            self.assertNotIn("agent_returncode", [check["check"] for check in persisted_validation["checks"]])
            self.assertNotIn("agent_stats", persisted_validation)
            self.assertEqual(persisted_agent["status"], "completed")
            self.assertEqual((artifact_dir / "agent_stdout.txt").read_text(), "hello")
            self.assertEqual((artifact_dir / "report.txt").read_text(), "Result: PASS\n")


class ExecutionSummaryTests(unittest.TestCase):
    def test_summarize_execution_result_normalizes_timeout_and_token_fields(self):
        summary = summarize_execution_result(
            {
                "status": "aborted",
                "agent_returncode": None,
                "error_type": "timeout",
                "stats": {
                    "duration_ms": 1234,
                    "input_tokens": 10,
                    "cached_input_tokens": 3,
                    "output_tokens": 8,
                    "total_tokens": 18,
                    "tool_uses": 2,
                    "tool_uses_by_type": {"Read": 1, "Bash": 1},
                },
            }
        )

        self.assertEqual(summary["status"], "aborted")
        self.assertIsNone(summary["agent_returncode"])
        self.assertTrue(summary["timeout"])
        self.assertFalse(summary["launch_error"])
        self.assertEqual(summary["input_tokens"], 10)
        self.assertEqual(summary["cached_input_tokens"], 3)
        self.assertEqual(summary["tool_uses_by_type"], {"Read": 1, "Bash": 1})


if __name__ == "__main__":
    unittest.main()
