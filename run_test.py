#!/usr/bin/env python3
"""Run a case against a CLI agent.

Usage:
    python run_test.py --list-cases
    python run_test.py --describe-case dates
    python run_test.py dates
    python run_test.py dates --agent codex
    python run_test.py dates --keep

Requires DATAIKU_URL and DATAIKU_API_KEY environment variables.
"""

import argparse
from contextlib import contextmanager
import json
import os
import shlex
import sys
import tempfile
from pathlib import Path

import dataikuapi
import urllib3

from evals import DEFAULT_EVALS, describe_case, list_cases, setup, teardown, validate
from suite.protocol import build_request, run_agent_command
from suite.report import format_report


BUILTIN_AGENTS = {"claude", "codex"}
REPO_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = REPO_ROOT / ".dataiku-agent-suite.json"
DEFAULT_SETTINGS = {
    "agent_command": None,
    "keep": False,
    "verbose": False,
    "agent_workspace": None,
    "artifacts_dir": None,
    "agent_timeout_seconds": 900,
}
CONFIG_KEYS = {
    "agent_command",
    "keep",
    "verbose",
    "agent_workspace",
    "artifacts_dir",
    "agent_timeout_seconds",
}


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


def _load_repo_config():
    if not CONFIG_PATH.is_file():
        return {}

    try:
        raw_config = json.loads(CONFIG_PATH.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {CONFIG_PATH}: {exc}") from exc

    if not isinstance(raw_config, dict):
        raise ValueError(f"{CONFIG_PATH} must contain a JSON object")

    unknown_keys = sorted(set(raw_config) - CONFIG_KEYS)
    if unknown_keys:
        raise ValueError(f"{CONFIG_PATH} contains unsupported keys: {', '.join(unknown_keys)}")

    config = {}
    if "agent_command" in raw_config:
        config["agent_command"] = _require_string(raw_config["agent_command"], "agent_command")
    if "keep" in raw_config:
        config["keep"] = _require_bool(raw_config["keep"], "keep")
    if "verbose" in raw_config:
        config["verbose"] = _require_bool(raw_config["verbose"], "verbose")
    if "agent_workspace" in raw_config:
        config["agent_workspace"] = _resolve_directory_config_path(raw_config["agent_workspace"], "agent_workspace")
    if "artifacts_dir" in raw_config:
        config["artifacts_dir"] = _resolve_config_path(raw_config["artifacts_dir"], "artifacts_dir")
    if "agent_timeout_seconds" in raw_config:
        config["agent_timeout_seconds"] = _require_positive_int(
            raw_config["agent_timeout_seconds"],
            "agent_timeout_seconds",
        )

    return config
def _require_string(value, field_name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{CONFIG_PATH}: '{field_name}' must be a non-empty string")
    return value


def _require_bool(value, field_name):
    if not isinstance(value, bool):
        raise ValueError(f"{CONFIG_PATH}: '{field_name}' must be true or false")
    return value


def _require_positive_int(value, field_name):
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"{CONFIG_PATH}: '{field_name}' must be a positive integer")
    return value


def _resolve_config_path(value, field_name):
    raw_path = _require_string(value, field_name)
    return (CONFIG_PATH.parent / raw_path).resolve()


def _resolve_directory_config_path(value, field_name):
    return _require_directory(_resolve_config_path(value, field_name), f"{CONFIG_PATH}: '{field_name}'")


def _require_directory(path, label):
    if not path.exists():
        raise ValueError(f"{label} does not exist: {path}")
    if not path.is_dir():
        raise ValueError(f"{label} must be a directory: {path}")
    return path


def _resolve_settings(args):
    settings = dict(DEFAULT_SETTINGS)
    settings.update(_load_repo_config())

    if args.agent is not None:
        settings["agent_command"] = args.agent
    if args.keep is not None:
        settings["keep"] = args.keep
    if args.verbose is not None:
        settings["verbose"] = args.verbose
    if args.agent_workspace is not None:
        settings["agent_workspace"] = _require_directory(
            Path(args.agent_workspace).resolve(),
            "--agent-workspace",
        )
    if args.artifacts_dir is not None:
        settings["artifacts_dir"] = Path(args.artifacts_dir).resolve()
    if args.agent_timeout_seconds is not None:
        settings["agent_timeout_seconds"] = args.agent_timeout_seconds

    return settings


def _is_within(path, root):
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _warn_if_workspace_is_repo_visible(agent_workspace):
    if _is_within(agent_workspace, REPO_ROOT) or _is_within(REPO_ROOT, agent_workspace):
        print(
            (
                "Warning: agent workspace is inside the harness repository. "
                "This can expose case definitions and evaluator logic to the agent "
                "and contaminate the test."
            ),
            file=sys.stderr,
        )
        print(f"         Workspace: {agent_workspace}", file=sys.stderr)


@contextmanager
def _resolved_agent_workspace(agent_workspace):
    if agent_workspace is not None:
        resolved_workspace = agent_workspace.resolve()
        _warn_if_workspace_is_repo_visible(resolved_workspace)
        yield resolved_workspace, False
        return

    with tempfile.TemporaryDirectory(prefix="dataiku-agent-workspace-") as temp_dir:
        yield Path(temp_dir).resolve(), True


def _print_case_list():
    cases = list_cases()
    print("Available cases")
    for case in cases:
        print(f"- {case['name']}: {case['description']}")


def _print_case_description(case_name):
    info = describe_case(case_name)
    case = info["case"]
    eval_specs = case.get("evals") or DEFAULT_EVALS
    expected_outputs = sorted((case.get("expected_outputs") or {}).keys())
    input_data = case.get("input_data") or {}

    print(f"Case: {info['name']}")
    print(f"Path: {info['path']}")
    print(f"Description: {case['description']}")
    print(f"Sources: {', '.join(case['sources'])}")

    source_project = case.get("source_project")
    if source_project:
        print(f"Source project: {source_project}")
    if input_data:
        print(f"Inline input data: {', '.join(sorted(input_data))}")
    if expected_outputs:
        print(f"Expected outputs: {', '.join(expected_outputs)}")

    print("Evaluators:")
    for spec in eval_specs:
        print(f"- {spec['name']}")

    print("Prompt:")
    print(case["prompt"])


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
    agent_workspace=None,
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
        with _resolved_agent_workspace(agent_workspace) as (resolved_workspace, is_temporary_workspace):
            workspace_label = "temporary isolated workspace" if is_temporary_workspace else "configured agent workspace"
            print(f"    Agent workspace: {resolved_workspace} ({workspace_label})")

            agent_command = _resolve_agent_command(agent_name)
            print(f"\n--- Running agent...")
            request = build_request(case_name, case, workspace=resolved_workspace)
            agent_result = run_agent_command(
                agent_command,
                request,
                timeout_seconds=agent_timeout_seconds,
                cwd=resolved_workspace,
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
                artifact_path = _write_artifacts(
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
    parser = argparse.ArgumentParser(description="Run or inspect Dataiku agent evaluation cases")
    parser.add_argument("case_name", nargs="?")
    parser.add_argument("--list-cases", action="store_true", help="List available cases and exit")
    parser.add_argument("--describe-case", metavar="CASE_NAME", help="Show case details and exit")
    parser.add_argument(
        "--keep",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Keep the generated project after validation",
    )
    parser.add_argument(
        "--agent-workspace",
        help="Workspace for the agent to use (defaults to a temporary isolated directory)",
    )
    parser.add_argument(
        "--verbose",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Show raw agent stdout/stderr excerpts in the report",
    )
    parser.add_argument(
        "--artifacts-dir",
        help="Directory where full request/response/report artifacts should be written",
    )
    parser.add_argument(
        "--agent-timeout-seconds",
        type=int,
        default=None,
        help="Maximum time to wait for the agent process before aborting it (default: 900)",
    )
    parser.add_argument("--agent", help="Agent to run (defaults to config when available)")
    args = parser.parse_args()

    try:
        if args.list_cases:
            _print_case_list()
            sys.exit(0)

        if args.describe_case:
            _print_case_description(args.describe_case)
            sys.exit(0)

        if not args.case_name:
            parser.error("Provide a case name, or use --list-cases / --describe-case.")

        settings = _resolve_settings(args)
    except Exception as exc:
        parser.error(str(exc))

    if not settings.get("agent_command"):
        parser.error(
            "No agent configured. Pass --agent, or set 'agent_command' in .dataiku-agent-suite.json."
        )

    result = run(
        args.case_name,
        agent_name=settings["agent_command"],
        keep=settings["keep"],
        agent_workspace=settings["agent_workspace"],
        verbose=settings["verbose"],
        artifacts_dir=settings["artifacts_dir"],
        agent_timeout_seconds=settings["agent_timeout_seconds"],
    )
    sys.exit(0 if result["passed"] else 1)
