#!/usr/bin/env python3
"""CLI agent script for running Codex against the test protocol."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from suite.prompting import build_agent_prompt
from suite.stats import extract_stats, normalize_stats

TOOL_EVENT_TYPES = {"command_execution", "web_search", "mcp_tool_call"}


def main():
    parser = argparse.ArgumentParser(description="Run Codex via the test agent protocol")
    parser.add_argument("--request", required=True)
    parser.add_argument("--response", required=True)
    parser.add_argument("--workspace", help="Override workspace from the request payload")
    args = parser.parse_args()

    request = json.loads(Path(args.request).read_text())
    workspace = Path(args.workspace or request.get("workspace") or os.getcwd()).resolve()
    prompt = _build_prompt(request)

    with tempfile.TemporaryDirectory(prefix="codex-wrapper-") as temp_dir:
        last_message_path = Path(temp_dir) / "last_message.txt"
        start = time.time()
        result = subprocess.run(
            [
                "codex",
                "exec",
                "--json",
                "--dangerously-bypass-approvals-and-sandbox",
                "-C",
                str(workspace),
                "-c",
                "shell_environment_policy.inherit=all",
                "--output-last-message",
                str(last_message_path),
                prompt,
            ],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        final_message = _read_final_message(last_message_path)

    duration_ms = int((time.time() - start) * 1000)

    structured_stats, last_agent_message, tool_trace = _extract_codex_stats(result.stdout)
    stats = extract_stats(result.stdout, result.stderr)
    stats.update(structured_stats)
    stats = normalize_stats(stats)
    stats["duration_ms"] = duration_ms
    response = {
        "version": 1,
        "status": "completed" if result.returncode == 0 else "failed",
        "summary": f"Codex executed in workspace {workspace}",
        "stdout": final_message or last_agent_message or result.stdout,
        "stderr": result.stderr,
        "stats": stats,
        "tool_trace": tool_trace,
    }
    Path(args.response).write_text(json.dumps(response, indent=2))


def _extract_codex_stats(event_stream):
    stats = {}
    last_agent_message = ""
    tool_uses_by_type = {}
    tool_trace = []

    for event in _parse_jsonl_events(event_stream):
        event_type = event.get("type")
        if event_type == "turn.completed":
            usage = event.get("usage") or {}
            for field_name in ("input_tokens", "cached_input_tokens", "output_tokens"):
                value = usage.get(field_name)
                if isinstance(value, int):
                    stats[field_name] = value
            if "input_tokens" in stats and "output_tokens" in stats:
                stats["total_tokens"] = stats["input_tokens"] + stats["output_tokens"]
            continue

        if event_type != "item.completed":
            continue

        item = event.get("item") or {}
        item_type = item.get("type")
        if item_type == "agent_message" and isinstance(item.get("text"), str):
            last_agent_message = item["text"]
        if item_type in TOOL_EVENT_TYPES:
            tool_uses_by_type[item_type] = tool_uses_by_type.get(item_type, 0) + 1
            if item_type == "mcp_tool_call":
                server = item.get("server") or ""
                tool = item.get("tool") or ""
                tool_trace.append({
                    "name": f"mcp__{server}__{tool}",
                    "input": item.get("arguments") or {},
                })
            else:
                tool_trace.append({
                    "name": item_type,
                    "input": {},
                })

    if tool_uses_by_type:
        stats["tool_uses_by_type"] = tool_uses_by_type
        stats["tool_uses"] = sum(tool_uses_by_type.values())

    return stats, last_agent_message, tool_trace


def _parse_jsonl_events(text):
    events = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def _read_final_message(path):
    if not path.exists():
        return ""
    return path.read_text().strip()


def _build_prompt(request):
    return build_agent_prompt(request)


if __name__ == "__main__":
    main()
