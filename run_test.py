#!/usr/bin/env python3
"""Run a case against a CLI agent.

Usage:
    python run_test.py dates --agent codex
    python run_test.py dates --agent codex --keep
    python run_test.py dates --agent codex --verbose
    python run_test.py dates --agent codex --artifacts-dir /path/to/artifacts
    python run_test.py dates --agent "python /path/to/my_agent.py"
    python run_test.py dates --agent codex --workspace /path/to/workspace

Requires DATAIKU_URL and DATAIKU_API_KEY environment variables.
"""

import argparse
import json
import os
import shlex
import sys
from pathlib import Path

import dataikuapi
import urllib3

from evals import setup, validate, teardown
from suite.protocol import build_request, run_agent_command
from suite.report import format_report


BUILTIN_AGENTS = {"claude", "codex"}


def _resolve_agent_command(agent_name):
    if agent_name not in BUILTIN_AGENTS:
        return agent_name

    script = Path(__file__).parent / "agents" / f"{agent_name}.py"
    return f"{shlex.quote(sys.executable)} {shlex.quote(str(script))}"


def _configure_ssl_verify(client):
    ssl_verify = os.environ.get("DATAIKU_SSL_VERIFY", "true")
    lowered = ssl_verify.lower()

    if lowered == "false":
        client._session.verify = False
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        return

    if lowered == "true":
        client._session.verify = True
        return

    client._session.verify = ssl_verify


def _build_project_url(base_url, project_key):
    return f"{base_url.rstrip('/')}/projects/{project_key}/"


def _apply_agent_outcome_checks(validation_result, agent_result):
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


def _write_artifacts(artifacts_root, project_key, request, agent_result, validation_result, report_text):
    artifact_dir = artifacts_root / project_key
    artifact_dir.mkdir(parents=True, exist_ok=True)

    (artifact_dir / "request.json").write_text(json.dumps(request, indent=2) + "\n")
    (artifact_dir / "agent_response.json").write_text(json.dumps(agent_result, indent=2) + "\n")
    (artifact_dir / "validation_result.json").write_text(json.dumps(validation_result, indent=2) + "\n")
    (artifact_dir / "agent_stdout.txt").write_text(agent_result.get("stdout", ""))
    (artifact_dir / "agent_stderr.txt").write_text(agent_result.get("stderr", ""))
    (artifact_dir / "report.txt").write_text(report_text + "\n")

    return artifact_dir


def run(
    case_name,
    agent_name,
    keep=False,
    workspace=None,
    verbose=False,
    artifacts_dir=None,
    agent_timeout_seconds=900,
):
    url = os.environ["DATAIKU_URL"]
    key = os.environ["DATAIKU_API_KEY"]
    client = dataikuapi.DSSClient(url, key)
    _configure_ssl_verify(client)

    print(f"--- Setting up case: {case_name}")
    try:
        case = setup(client, case_name)
    except Exception as exc:
        print(f"Setup failed: {exc}")
        return {"passed": False, "stage": "setup", "error": str(exc)}
    print(f"    Project: {case['project_key']}")
    print(f"    Sources: {case['sources']}")

    try:
        agent_command = _resolve_agent_command(agent_name)
        print(f"\n--- Running agent...")
        request = build_request(case_name, case, workspace=workspace)
        agent_result = run_agent_command(
            agent_command,
            request,
            timeout_seconds=agent_timeout_seconds,
        )
        print(agent_result.get("summary", "Agent completed"))

        print(f"\n--- Validating...")
        result = validate(client, case_name, case["project_key"], agent_stats=agent_result.get("stats"))
        result = _apply_agent_outcome_checks(result, agent_result)
        artifact_path = None
        report_text = format_report(
            case_name,
            case["project_key"],
            agent_result,
            result,
            project_url=_build_project_url(url, case["project_key"]) if keep else None,
            verbose=verbose,
        )
        if artifacts_dir:
            artifact_path = _write_artifacts(artifacts_dir, case["project_key"], request, agent_result, result, report_text)
            report_text = format_report(
                case_name,
                case["project_key"],
                agent_result,
                result,
                project_url=_build_project_url(url, case["project_key"]) if keep else None,
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
            print(f"\n--- Cleaning up...")
            try:
                teardown(client, case["project_key"])
            except Exception as exc:
                print(f"Cleanup failed for {case['project_key']}: {exc}")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a Dataiku agent evaluation case")
    parser.add_argument("case_name")
    parser.add_argument("--keep", action="store_true", help="Keep the generated project after validation")
    parser.add_argument(
        "--workspace",
        help="Workspace path to include in the agent request (defaults to current directory)",
    )
    parser.add_argument("--verbose", action="store_true", help="Show raw agent stdout/stderr excerpts in the report")
    parser.add_argument(
        "--artifacts-dir",
        help="Directory where full request/response/report artifacts should be written",
    )
    parser.add_argument(
        "--agent-timeout-seconds",
        type=int,
        default=900,
        help="Maximum time to wait for the agent process before aborting it (default: 900)",
    )
    parser.add_argument("--agent", help="Agent to run (required)")
    args = parser.parse_args()

    if not args.agent:
        parser.error(
            "--agent is required. Use a built-in agent like 'codex' or 'claude', or pass a custom command string."
        )

    result = run(
        args.case_name,
        agent_name=args.agent,
        keep=args.keep,
        workspace=Path(args.workspace).resolve() if args.workspace else Path.cwd(),
        verbose=args.verbose,
        artifacts_dir=Path(args.artifacts_dir).resolve() if args.artifacts_dir else None,
        agent_timeout_seconds=args.agent_timeout_seconds,
    )
    sys.exit(0 if result["passed"] else 1)
