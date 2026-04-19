#!/usr/bin/env python3
"""Run a case against a CLI agent.

Usage:
    python run_test.py list-cases
    python run_test.py describe-case dates
    python run_test.py list-profiles
    python run_test.py run dates --profile codex-vanilla
    python run_test.py run dates --profile codex-vanilla --keep

Requires DATAIKU_URL and DATAIKU_API_KEY environment variables.
"""

import argparse
import os
import shlex
import sys
from pathlib import Path

import dataikuapi
import urllib3

from evals import DEFAULT_EVALS, describe_case, list_cases
from suite.profiles import list_profiles, resolve_profile
from suite.runner import run_case


BUILTIN_AGENTS = {"claude", "codex"}
REPO_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = REPO_ROOT / ".dataiku-agent-suite.json"


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


def _resolve_settings(args):
    if not args.profile:
        raise ValueError(
            "No profile configured. Pass --profile, and define that profile in .dataiku-agent-suite.json."
        )

    settings = resolve_profile(CONFIG_PATH, args.profile)

    if args.keep is not None:
        settings["keep"] = args.keep
    if args.verbose is not None:
        settings["verbose"] = args.verbose
    if args.artifacts_dir is not None:
        settings["artifacts_dir"] = Path(args.artifacts_dir).resolve()
    if args.agent_timeout_seconds is not None:
        settings["agent_timeout_seconds"] = args.agent_timeout_seconds

    return settings


def _print_profile_list():
    profiles = list_profiles(CONFIG_PATH)
    if not profiles:
        print(f"No profiles configured in {CONFIG_PATH}")
        return

    print("Available profiles")
    for profile in profiles:
        description = profile["description"] or "(no description)"
        print(f"- {profile['name']}: {description}")


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


def run(
    case_name,
    agent_command,
    keep=False,
    agent_workspace=None,
    verbose=False,
    artifacts_dir=None,
    agent_timeout_seconds=900,
    env=None,
):
    if env:
        previous_values = {name: os.environ.get(name) for name in env}
        os.environ.update(env)
    else:
        previous_values = None

    try:
        url = os.environ["DATAIKU_URL"]
        key = os.environ["DATAIKU_API_KEY"]
        client = dataikuapi.DSSClient(url, key)
        _configure_ssl_verify(client)

        return run_case(
            client,
            url,
            case_name,
            agent_command=_resolve_agent_command(agent_command),
            keep=keep,
            agent_workspace=agent_workspace,
            verbose=verbose,
            artifacts_dir=artifacts_dir,
            agent_timeout_seconds=agent_timeout_seconds,
            repo_root=REPO_ROOT,
        )
    finally:
        if previous_values is not None:
            for name, value in previous_values.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run or inspect Dataiku agent evaluation cases")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("list-cases", help="List available cases and exit")

    describe_parser = subparsers.add_parser("describe-case", help="Show one case and exit")
    describe_parser.add_argument("case_name")

    subparsers.add_parser("list-profiles", help="List configured profiles and exit")

    run_parser = subparsers.add_parser("run", help="Run one case against one profile")
    run_parser.add_argument("case_name")
    run_parser.add_argument("--profile", required=True, help="Named profile from .dataiku-agent-suite.json")
    run_parser.add_argument(
        "--keep",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Keep the generated project after validation",
    )
    run_parser.add_argument(
        "--verbose",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Show raw agent stdout/stderr excerpts in the report",
    )
    run_parser.add_argument(
        "--artifacts-dir",
        help="Directory where full request/response/report artifacts should be written",
    )
    run_parser.add_argument(
        "--agent-timeout-seconds",
        type=int,
        default=None,
        help="Maximum time to wait for the agent process before aborting it (default: 900)",
    )
    args = parser.parse_args()

    try:
        if args.command == "list-cases":
            _print_case_list()
            sys.exit(0)

        if args.command == "describe-case":
            _print_case_description(args.case_name)
            sys.exit(0)

        if args.command == "list-profiles":
            _print_profile_list()
            sys.exit(0)

        if args.command != "run":
            parser.error("Choose a subcommand: run, list-cases, describe-case, or list-profiles.")

        settings = _resolve_settings(args)
    except Exception as exc:
        parser.error(str(exc))

    result = run(
        args.case_name,
        agent_command=settings["agent_command"],
        keep=settings["keep"],
        agent_workspace=settings["agent_workspace"],
        verbose=settings["verbose"],
        artifacts_dir=settings["artifacts_dir"],
        agent_timeout_seconds=settings["agent_timeout_seconds"],
        env=settings["env"],
    )
    sys.exit(0 if result["passed"] else 1)
