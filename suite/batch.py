"""Sequential batch orchestration helpers."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


BATCH_ARTIFACT_SCHEMA_VERSION = 1


def run_batch(run_one, cases, profiles, artifacts_root=None):
    """Run a case/profile matrix sequentially using the provided run callback."""
    started_at = datetime.now(timezone.utc)
    batch_context = create_batch_artifact_dir(artifacts_root, started_at) if artifacts_root else None
    total_runs = len(cases) * len(profiles)
    run_entries = []

    print("=== Batch start")
    print(f"Cases: {', '.join(cases)}")
    print(f"Profiles: {', '.join(profile['profile_name'] for profile in profiles)}")
    print(f"Runs: {total_runs}")

    index = 0
    for case_name in cases:
        for profile in profiles:
            index += 1
            profile_name = profile["profile_name"]
            print(f"\n=== [{index}/{total_runs}] {case_name} x {profile_name}")
            child_artifacts_root = batch_context["runs_dir"] if batch_context else None
            result = run_one(case_name, profile, child_artifacts_root)
            run_entries.append(_build_batch_run_entry(result, batch_context["batch_dir"] if batch_context else None))

    finished_at = datetime.now(timezone.utc)
    report_text = format_batch_report(
        batch_id=batch_context["batch_id"] if batch_context else None,
        cases=cases,
        profiles=[profile["profile_name"] for profile in profiles],
        run_entries=run_entries,
        batch_artifact_dir=batch_context["batch_dir"] if batch_context else None,
    )

    if batch_context:
        write_batch_artifacts(
            batch_context["batch_dir"],
            batch_id=batch_context["batch_id"],
            cases=cases,
            profiles=[profile["profile_name"] for profile in profiles],
            run_entries=run_entries,
            started_at=started_at,
            finished_at=finished_at,
            report_text=report_text,
        )

    print(f"\n{report_text}")
    return {
        "passed": all(entry["passed"] for entry in run_entries),
        "runs": run_entries,
        "batch_artifact_dir": str(batch_context["batch_dir"]) if batch_context else None,
    }


def create_batch_artifact_dir(artifacts_root, started_at):
    """Create and return a self-contained batch artifact directory."""
    batch_id = uuid.uuid4().hex[:8]
    batch_dir = Path(artifacts_root) / f"batch__{_format_timestamp_for_path(started_at)}__{batch_id}"
    runs_dir = batch_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    return {
        "batch_id": batch_id,
        "batch_dir": batch_dir,
        "runs_dir": runs_dir,
    }


def write_batch_artifacts(batch_dir, *, batch_id, cases, profiles, run_entries, started_at, finished_at, report_text):
    """Write a thin batch manifest and report."""
    manifest = {
        "schema_version": BATCH_ARTIFACT_SCHEMA_VERSION,
        "batch_id": batch_id,
        "started_at": _format_timestamp(started_at),
        "finished_at": _format_timestamp(finished_at),
        "cases": list(cases),
        "profiles": list(profiles),
        "run_count": len(run_entries),
        "passed_run_count": sum(1 for entry in run_entries if entry["passed"]),
        "failed_run_count": sum(1 for entry in run_entries if not entry["passed"]),
        "runs": run_entries,
    }

    (batch_dir / "batch_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (batch_dir / "report.txt").write_text(report_text + "\n")


def format_batch_report(*, batch_id, cases, profiles, run_entries, batch_artifact_dir=None):
    """Format a short human-readable batch summary."""
    lines = []
    if batch_id:
        lines.append(f"Batch: {batch_id}")
    lines.append(f"Cases: {', '.join(cases)}")
    lines.append(f"Profiles: {', '.join(profiles)}")
    lines.append(f"Runs: {len(run_entries)}")
    lines.append(f"Passed: {sum(1 for entry in run_entries if entry['passed'])}")
    lines.append(f"Failed: {sum(1 for entry in run_entries if not entry['passed'])}")
    if batch_artifact_dir:
        lines.append(f"Artifacts: {batch_artifact_dir}")

    lines.append("")
    lines.append("Results")
    for entry in run_entries:
        status = "PASS" if entry["passed"] else "FAIL"
        lines.append(f"- {status} {entry['case_name']} x {entry['profile_name']}")

    return "\n".join(lines)


def _build_batch_run_entry(result, batch_dir):
    artifact_dir = result.get("artifact_dir")
    if artifact_dir and batch_dir is not None:
        artifact_dir = str(Path(artifact_dir).resolve().relative_to(batch_dir.resolve()))

    entry = {
        "case_name": result.get("case_name"),
        "profile_name": result.get("profile_name"),
        "artifact_dir": artifact_dir,
        "project_key": result.get("project_key"),
        "passed": result.get("passed", False),
    }

    if result.get("stage"):
        entry["stage"] = result["stage"]
    if result.get("error"):
        entry["error"] = result["error"]

    return entry


def _format_timestamp(value):
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _format_timestamp_for_path(value):
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
