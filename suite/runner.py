"""Single-run orchestration helpers."""

import sys
from pathlib import Path

from evals import setup, teardown, validate

from .artifacts import write_run_artifacts
from .protocol import build_request, run_agent_command
from .redaction import redact_text
from .report import format_report
from .workspaces import stage_agent_workspace


def run_case(
    client,
    base_url,
    case_name,
    agent_command,
    keep=False,
    agent_workspace=None,
    verbose=False,
    artifacts_dir=None,
    agent_timeout_seconds=900,
    repo_root=None,
):
    """Run one case against one agent command and return the validation result."""
    print(f"--- Setting up case: {case_name}")
    try:
        case = setup(client, case_name)
    except Exception as exc:
        print(f"Setup failed: {exc}")
        return {"passed": False, "stage": "setup", "error": str(exc)}
    print(f"    Project: {case['project_key']}")
    print(f"    Sources: {case['sources']}")

    try:
        with stage_agent_workspace(agent_workspace) as staged_workspace:
            if staged_workspace.source_workspace is not None:
                warn_if_workspace_is_repo_visible(staged_workspace.source_workspace, repo_root)
            if staged_workspace.is_copy:
                print(f"    Source workspace: {staged_workspace.source_workspace}")
                print(f"    Run workspace: {staged_workspace.run_workspace} (temporary isolated copy)")
            else:
                print(f"    Run workspace: {staged_workspace.run_workspace} (temporary isolated workspace)")

            print("\n--- Running agent...")
            request = build_request(case_name, case, workspace=staged_workspace.run_workspace)
            agent_result = run_agent_command(
                agent_command,
                request,
                timeout_seconds=agent_timeout_seconds,
                cwd=staged_workspace.run_workspace,
            )
            print(redact_text(agent_result.get("summary", "Agent completed")))

            print("\n--- Validating...")
            result = validate(
                client,
                case_name,
                case["project_key"],
                agent_stats=agent_result.get("stats"),
                tool_trace=agent_result.get("tool_trace"),
            )
            result = apply_agent_outcome_checks(result, agent_result)
            artifact_path = None
            report_text = format_report(
                case_name,
                case["project_key"],
                agent_result,
                result,
                project_url=build_project_url(base_url, case["project_key"]) if keep else None,
                verbose=verbose,
            )
            if artifacts_dir:
                artifact_path = write_run_artifacts(
                    artifacts_dir,
                    case["project_key"],
                    request,
                    agent_result,
                    result,
                    report_text,
                )
                report_text = format_report(
                    case_name,
                    case["project_key"],
                    agent_result,
                    result,
                    project_url=build_project_url(base_url, case["project_key"]) if keep else None,
                    artifacts_dir=artifact_path,
                    verbose=verbose,
                )
                (artifact_path / "report.txt").write_text(report_text + "\n")
        print()
        print(report_text)
    finally:
        if keep:
            print(f"\n--- Keeping project: {case['project_key']}")
        else:
            print("\n--- Cleaning up...")
            try:
                teardown(client, case["project_key"])
            except Exception as exc:
                print(f"Cleanup failed for {case['project_key']}: {exc}")

    return result


def apply_agent_outcome_checks(validation_result, agent_result):
    """Fold basic harness execution checks into the validation result."""
    checks = list(validation_result["checks"])

    returncode = agent_result.get("agent_returncode")
    if returncode is not None:
        checks.insert(0, {
            "check": "agent_returncode",
            "passed": returncode == 0,
            "expected": 0,
            "actual": returncode,
        })

    status = agent_result.get("status")
    if status is not None:
        checks.insert(1 if returncode is not None else 0, {
            "check": "agent_status",
            "passed": status == "completed",
            "expected": "completed",
            "actual": status,
        })

    result = dict(validation_result)
    result["checks"] = checks
    result["passed"] = all(check["passed"] for check in checks)
    return result


def build_project_url(base_url, project_key):
    """Build a project URL for reporting."""
    return f"{base_url.rstrip('/')}/projects/{project_key}/"


def is_within(path, root):
    """Return True when path is inside root."""
    if root is None:
        return False
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def warn_if_workspace_is_repo_visible(agent_workspace, repo_root):
    """Warn when the configured agent workspace overlaps the harness repo."""
    if repo_root is None:
        return

    if is_within(agent_workspace, repo_root) or is_within(repo_root, agent_workspace):
        print(
            (
                "Warning: agent workspace is inside the harness repository. "
                "This can expose case definitions and evaluator logic to the agent "
                "and contaminate the test."
            ),
            file=sys.stderr,
        )
        print(f"         Workspace: {agent_workspace}", file=sys.stderr)
