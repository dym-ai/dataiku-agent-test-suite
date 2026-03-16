#!/usr/bin/env python3
"""CLI agent script for running Claude Code against the test protocol."""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from suite.prompting import build_agent_prompt
from suite.stats import normalize_stats


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
        ["claude", "-p", "--output-format", "stream-json", "--verbose", prompt],
        cwd=str(workspace),
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    duration_ms = int((time.time() - start) * 1000)

    tool_trace, parsed_stats, result_text = _parse_stream_json(result.stdout)
    parsed_stats["duration_ms"] = duration_ms
    parsed_stats["tool_uses"] = len(tool_trace)
    if tool_trace:
        by_name = {}
        for call in tool_trace:
            name = call.get("name") or "unknown"
            by_name[name] = by_name.get(name, 0) + 1
        parsed_stats["tool_uses_by_type"] = by_name

    stats = normalize_stats(parsed_stats)
    response = {
        "version": 1,
        "status": "completed" if result.returncode == 0 else "failed",
        "summary": f"Claude Code executed in workspace {workspace}",
        "stdout": result_text,
        "stderr": result.stderr,
        "stats": stats,
        "tool_trace": tool_trace,
    }
    Path(args.response).write_text(json.dumps(response, indent=2))


def _build_prompt(request):
    return build_agent_prompt(request)


def _parse_stream_json(stdout):
    """Parse claude --output-format stream-json output into (tool_trace, stats, result_text)."""
    tool_trace = []
    stats = {}
    result_text = ""

    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        event_type = event.get("type")

        if event_type == "assistant":
            for block in (event.get("message") or {}).get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tool_trace.append({
                        "name": block.get("name"),
                        "input": block.get("input") or {},
                    })

        elif event_type == "result":
            result_text = event.get("result") or ""
            usage = event.get("usage") or {}
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            cache_creation = usage.get("cache_creation_input_tokens", 0)
            cache_read = usage.get("cache_read_input_tokens", 0)
            stats["input_tokens"] = input_tokens
            stats["cache_creation_tokens"] = cache_creation
            stats["cache_read_tokens"] = cache_read
            stats["output_tokens"] = output_tokens
            stats["total_tokens"] = input_tokens + output_tokens + cache_creation + cache_read

    return tool_trace, stats, result_text


if __name__ == "__main__":
    main()
