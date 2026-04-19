"""Helpers for writing run artifacts to disk."""

from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from datetime import timezone
from pathlib import Path

from .redaction import redact_value


RUN_ARTIFACT_SCHEMA_VERSION = 1


def write_run_artifacts(
    artifacts_root,
    *,
    case_name,
    case_path,
    project_key,
    profile,
    request,
    agent_result,
    execution_result,
    validation_result,
    overall_passed,
    report_text,
    started_at,
    finished_at,
    staged_workspace,
    keep,
    harness_repo_root=None,
):
    """Write the current run bundle and return the artifact directory path."""
    run_id = uuid.uuid4().hex[:8]
    timestamp = _format_timestamp_for_path(started_at)
    artifact_dir = artifacts_root / _build_run_dir_name(case_name, profile["name"], timestamp, run_id)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    safe_agent_result = redact_value(agent_result)
    case_path = Path(case_path).resolve()
    harness_repo_root = harness_repo_root.resolve() if harness_repo_root is not None else None

    manifest = {
        "schema_version": RUN_ARTIFACT_SCHEMA_VERSION,
        "run_id": run_id,
        "started_at": _format_timestamp(started_at),
        "finished_at": _format_timestamp(finished_at),
        "passed": overall_passed,
        "case_name": case_name,
        "case_path": str(case_path),
        "case_digest": _sha256_file(case_path),
        "profile_name": profile["name"],
        "profile_digest": _sha256_json(_safe_profile_digest_payload(profile)),
        "profile": {
            "description": profile.get("description", ""),
            "agent_command": profile["agent_command"],
            "agent_workspace_source": str(profile["agent_workspace"]) if profile.get("agent_workspace") else None,
            "tags": list(profile.get("tags") or []),
            "dss_url": profile.get("dss_url"),
        },
        "workspace": {
            "source_path": str(staged_workspace.source_workspace) if staged_workspace.source_workspace else None,
            "run_path": str(staged_workspace.run_workspace),
            "source_git_sha": _git_sha(staged_workspace.source_workspace),
        },
        "project": {
            "project_key": project_key,
            "kept": keep,
        },
        "execution_result": execution_result,
        "validation_result": {
            "passed": validation_result["passed"],
            "check_count": len(validation_result["checks"]),
            "failed_check_count": sum(1 for check in validation_result["checks"] if not check["passed"]),
            "skipped_check_count": sum(1 for check in validation_result["checks"] if check.get("skipped")),
        },
        "artifacts": {
            "request": "request.json",
            "agent_response": "agent_response.json",
            "validation_result": "validation_result.json",
            "stdout": "agent_stdout.txt",
            "stderr": "agent_stderr.txt",
            "report": "report.txt",
            "run_manifest": "run_manifest.json",
        },
        "harness": {
            "repo_root": str(harness_repo_root) if harness_repo_root is not None else None,
            "git_sha": _git_sha(harness_repo_root),
        },
    }

    (artifact_dir / "request.json").write_text(json.dumps(request, indent=2) + "\n")
    (artifact_dir / "agent_response.json").write_text(json.dumps(safe_agent_result, indent=2) + "\n")
    persisted_validation_result = {
        "passed": validation_result["passed"],
        "checks": validation_result["checks"],
    }

    (artifact_dir / "validation_result.json").write_text(json.dumps(persisted_validation_result, indent=2) + "\n")
    (artifact_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (artifact_dir / "agent_stdout.txt").write_text(safe_agent_result.get("stdout", ""))
    (artifact_dir / "agent_stderr.txt").write_text(safe_agent_result.get("stderr", ""))
    (artifact_dir / "report.txt").write_text(report_text + "\n")

    return artifact_dir


def summarize_execution_result(agent_result):
    """Return a normalized execution summary for manifests and later comparisons."""
    stats = agent_result.get("stats") or {}
    return {
        "status": agent_result.get("status"),
        "agent_returncode": agent_result.get("agent_returncode"),
        "timeout": agent_result.get("error_type") == "timeout",
        "launch_error": agent_result.get("error_type") == "launch_error",
        "duration_ms": stats.get("duration_ms"),
        "input_tokens": stats.get("input_tokens"),
        "cached_input_tokens": stats.get("cached_input_tokens"),
        "cache_read_tokens": stats.get("cache_read_tokens"),
        "cache_creation_tokens": stats.get("cache_creation_tokens"),
        "output_tokens": stats.get("output_tokens"),
        "total_tokens": stats.get("total_tokens"),
        "tool_uses": stats.get("tool_uses"),
        "tool_uses_by_type": stats.get("tool_uses_by_type") or {},
    }


def _build_run_dir_name(case_name, profile_name, timestamp, run_id):
    return f"run__{_slugify(case_name)}__{_slugify(profile_name)}__{timestamp}__{run_id}"


def _slugify(value):
    chars = []
    for char in value:
        if char.isalnum():
            chars.append(char.lower())
        else:
            chars.append("-")
    slug = "".join(chars).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "run"


def _format_timestamp(value):
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _format_timestamp_for_path(value):
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _sha256_json(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _safe_profile_digest_payload(profile):
    return {
        "name": profile["name"],
        "description": profile.get("description", ""),
        "agent_command": profile["agent_command"],
        "agent_workspace": str(profile["agent_workspace"]) if profile.get("agent_workspace") else None,
        "tags": list(profile.get("tags") or []),
        "dss_url": profile.get("dss_url"),
        "env_keys": sorted(profile.get("env_keys") or []),
    }


def _git_sha(path):
    if path is None:
        return None

    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(path),
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, NotADirectoryError):
        return None

    sha = completed.stdout.strip()
    return sha or None
