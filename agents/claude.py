#!/usr/bin/env python3
"""CLI agent script for running Claude Code against the test protocol."""

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
    parser = argparse.ArgumentParser(description="Run Claude Code via the test agent protocol")
    parser.add_argument("--request", required=True)
    parser.add_argument("--response", required=True)
    parser.add_argument("--workspace", help="Override workspace from the request payload")
    args = parser.parse_args()

    request = json.loads(Path(args.request).read_text())
    workspace = Path(args.workspace or request.get("workspace") or os.getcwd()).resolve()
    prompt = _build_prompt(request)

    start = time.time()
    result = subprocess.run(
        ["claude", "-p", prompt],
        cwd=str(workspace),
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    duration_ms = int((time.time() - start) * 1000)

    stats = _parse_stats(result.stdout)
    stats["duration_ms"] = duration_ms
    response = {
        "version": 1,
        "status": "completed" if result.returncode == 0 else "failed",
        "summary": f"Claude Code executed in workspace {workspace}",
        "stdout": result.stdout,
        "stderr": result.stderr,
        "stats": stats,
    }
    Path(args.response).write_text(json.dumps(response, indent=2))


def _build_prompt(request):
    return build_agent_prompt(request)


def _parse_stats(stdout):
    stats = {}
    for line in stdout.splitlines():
        line = line.strip()
        if "total_tokens" in line:
            match = re.search(r"total_tokens[:\s]+(\d+)", line)
            if match:
                stats["total_tokens"] = int(match.group(1))
        if "tool_uses" in line or "tool_calls" in line:
            match = re.search(r"(?:tool_uses|tool_calls)[:\s]+(\d+)", line)
            if match:
                stats["tool_uses"] = int(match.group(1))
    return stats


if __name__ == "__main__":
    main()
