"""Helpers for writing run artifacts to disk."""

import json

from .redaction import redact_value


def write_run_artifacts(artifacts_root, project_key, request, agent_result, validation_result, report_text):
    """Write the current run bundle and return the artifact directory path."""
    artifact_dir = artifacts_root / project_key
    artifact_dir.mkdir(parents=True, exist_ok=True)
    safe_agent_result = redact_value(agent_result)

    (artifact_dir / "request.json").write_text(json.dumps(request, indent=2) + "\n")
    (artifact_dir / "agent_response.json").write_text(json.dumps(safe_agent_result, indent=2) + "\n")
    (artifact_dir / "validation_result.json").write_text(json.dumps(validation_result, indent=2) + "\n")
    (artifact_dir / "agent_stdout.txt").write_text(safe_agent_result.get("stdout", ""))
    (artifact_dir / "agent_stderr.txt").write_text(safe_agent_result.get("stderr", ""))
    (artifact_dir / "report.txt").write_text(report_text + "\n")

    return artifact_dir
