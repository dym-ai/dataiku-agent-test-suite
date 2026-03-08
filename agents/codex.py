#!/usr/bin/env python3
"""CLI agent script for running Codex against the test protocol."""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from suite.prompting import build_agent_prompt


def main():
    parser = argparse.ArgumentParser(description="Run Codex via the test agent protocol")
    parser.add_argument("--request", required=True)
    parser.add_argument("--response", required=True)
    parser.add_argument("--workspace", help="Override workspace from the request payload")
    args = parser.parse_args()

    request = json.loads(Path(args.request).read_text())
    workspace = Path(args.workspace or request.get("workspace") or os.getcwd()).resolve()
    prompt = _build_prompt(request)

    start = time.time()
    result = subprocess.run(
        [
            "codex",
            "exec",
            "--dangerously-bypass-approvals-and-sandbox",
            "-C",
            str(workspace),
            "-c",
            "shell_environment_policy.inherit=all",
            prompt,
        ],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    duration_ms = int((time.time() - start) * 1000)

    stats = _parse_stats(result.stdout, result.stderr)
    stats["duration_ms"] = duration_ms
    response = {
        "version": 1,
        "status": "completed" if result.returncode == 0 else "failed",
        "summary": f"Codex executed in workspace {workspace}",
        "stdout": result.stdout,
        "stderr": result.stderr,
        "stats": stats,
    }
    Path(args.response).write_text(json.dumps(response, indent=2))


def _build_prompt(request):
    return build_agent_prompt(request)


def _parse_stats(stdout, stderr=""):
    stats = {}
    lines = [line.strip().lower() for line in f"{stdout}\n{stderr}".splitlines()]
    for index, line in enumerate(lines):
        next_line = lines[index + 1] if index + 1 < len(lines) else ""

        token_match = re.search(r"tokens used\s+([\d,]+)", line)
        if token_match:
            stats["total_tokens"] = int(token_match.group(1).replace(",", ""))
        elif line == "tokens used" and re.fullmatch(r"[\d,]+", next_line):
            stats["total_tokens"] = int(next_line.replace(",", ""))

        tool_match = re.search(r"tool uses?\s+([\d,]+)", line)
        if tool_match:
            stats["tool_uses"] = int(tool_match.group(1).replace(",", ""))
        elif line in {"tool use", "tool uses"} and re.fullmatch(r"[\d,]+", next_line):
            stats["tool_uses"] = int(next_line.replace(",", ""))

    return stats


if __name__ == "__main__":
    main()
