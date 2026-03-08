#!/usr/bin/env python3
"""CLI agent script for running Codex against the test protocol."""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from suite.prompting import build_agent_prompt
from suite.stats import extract_stats, normalize_stats


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

    stats = normalize_stats(extract_stats(result.stdout, result.stderr))
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
if __name__ == "__main__":
    main()
