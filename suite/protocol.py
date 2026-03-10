"""Agent request/response protocol helpers."""

import json
import shlex
import subprocess
import tempfile
import time
from pathlib import Path

from .stats import normalize_stats

PROTOCOL_VERSION = 1


def build_request(case_name, case, workspace=None):
    """Build the agent request payload for a case run."""
    return {
        "version": PROTOCOL_VERSION,
        "case_name": case_name,
        "project_key": case["project_key"],
        "prompt": case["prompt"],
        "sources": case["sources"],
        "workspace": str(workspace) if workspace else None,
    }


def run_agent_command(agent_command, request, timeout_seconds=None, cwd=None):
    """Run an agent command with request/response JSON files."""
    if not agent_command:
        raise ValueError("Agent command is required")

    args = shlex.split(agent_command)
    with tempfile.TemporaryDirectory(prefix="dataiku-eval-") as temp_dir:
        temp_path = Path(temp_dir)
        request_path = temp_path / "request.json"
        response_path = temp_path / "response.json"
        request_path.write_text(json.dumps(request, indent=2))

        started_at = time.monotonic()
        try:
            completed = subprocess.run(
                [*args, "--request", str(request_path), "--response", str(response_path)],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                cwd=str(cwd) if cwd is not None else None,
            )
        except subprocess.TimeoutExpired as exc:
            response = _load_response(response_path)
            return _build_timeout_result(
                exc,
                response,
                elapsed_ms=int((time.monotonic() - started_at) * 1000),
                timeout_seconds=timeout_seconds,
            )
        except OSError as exc:
            response = _load_response(response_path)
            return _build_launch_error_result(exc, response)

        response = _load_response(response_path)
        return _merge_result(completed, response)


def _load_response(response_path):
    if not response_path.exists():
        return {}

    try:
        return json.loads(response_path.read_text())
    except json.JSONDecodeError as exc:
        return {
            "version": PROTOCOL_VERSION,
            "status": "failed",
            "summary": f"Agent wrote invalid JSON to {response_path}: {exc}",
        }


def _merge_result(completed, response):
    result = dict(response)
    result.setdefault("version", PROTOCOL_VERSION)
    result.setdefault("status", "completed" if completed.returncode == 0 else "failed")
    result.setdefault(
        "summary",
        "Agent completed without a summary"
        if completed.returncode == 0
        else f"Agent exited with code {completed.returncode}",
    )
    result.setdefault("stdout", result.get("stdout") or completed.stdout)
    result.setdefault("stderr", result.get("stderr") or completed.stderr)
    result["stats"] = normalize_stats(result.get("stats", {}))
    result["agent_returncode"] = completed.returncode
    return result


def _build_timeout_result(exc, response, elapsed_ms, timeout_seconds):
    result = dict(response)
    result.setdefault("version", PROTOCOL_VERSION)
    result["status"] = "aborted"
    result["summary"] = f"Agent timed out after {timeout_seconds}s"
    result["stdout"] = result.get("stdout") or _coerce_text(exc.stdout)
    result["stderr"] = result.get("stderr") or _coerce_text(exc.stderr)
    stats = dict(result.get("stats") or {})
    stats["duration_ms"] = elapsed_ms
    if timeout_seconds is not None:
        stats["timeout_seconds"] = timeout_seconds
    result["stats"] = stats
    result["agent_returncode"] = None
    result["error_type"] = "timeout"
    return result


def _build_launch_error_result(exc, response):
    result = dict(response)
    result.setdefault("version", PROTOCOL_VERSION)
    result["status"] = "failed"
    result["summary"] = f"Failed to launch agent command: {exc}"
    result["stdout"] = result.get("stdout") or ""
    result["stderr"] = result.get("stderr") or str(exc)
    result.setdefault("stats", {})
    result["agent_returncode"] = None
    result["error_type"] = "launch_error"
    return result


def _coerce_text(value):
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value
