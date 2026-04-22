"""Batch orchestration helpers."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .compare import compare_artifact_dirs


BATCH_ARTIFACT_SCHEMA_VERSION = 1


def run_batch(run_one, cases, profiles, artifacts_root=None, max_parallel=1):
    """Run a case/profile matrix using the provided run callback."""
    started_at = datetime.now(timezone.utc)
    batch_context = create_batch_artifact_dir(artifacts_root, started_at) if artifacts_root else None
    run_specs = [
        (index, case_name, profile)
        for index, (case_name, profile) in enumerate(
            (pair for case_name in cases for pair in ((case_name, profile) for profile in profiles)),
            start=1,
        )
    ]
    total_runs = len(run_specs)
    run_entries = [None] * total_runs

    print("=== Batch start")
    print(f"Cases: {', '.join(cases)}")
    print(f"Profiles: {', '.join(profile['profile_name'] for profile in profiles)}")
    print(f"Runs: {total_runs}")
    print(f"Max parallel: {max_parallel}")

    if max_parallel <= 1:
        for index, case_name, profile in run_specs:
            profile_name = profile["profile_name"]
            print(f"\n=== [{index}/{total_runs}] {case_name} x {profile_name}")
            child_artifacts_root = batch_context["runs_dir"] if batch_context else None
            result = run_one(case_name, profile, child_artifacts_root)
            run_entries[index - 1] = _build_batch_run_entry(result, batch_context["batch_dir"] if batch_context else None)
    else:
        print("Mode: parallel")
        with ThreadPoolExecutor(max_workers=max_parallel) as executor:
            future_map = {}
            for index, case_name, profile in run_specs:
                profile_name = profile["profile_name"]
                print(f"\n=== Queued [{index}/{total_runs}] {case_name} x {profile_name}")
                child_artifacts_root = batch_context["runs_dir"] if batch_context else None
                future = executor.submit(run_one, case_name, profile, child_artifacts_root)
                future_map[future] = (index, case_name, profile_name)

            for future in as_completed(future_map):
                index, case_name, profile_name = future_map[future]
                result = future.result()
                run_entries[index - 1] = _build_batch_run_entry(
                    result,
                    batch_context["batch_dir"] if batch_context else None,
                )
                status = "PASS" if result.get("passed", False) else "FAIL"
                print(f"\n=== Finished [{index}/{total_runs}] {case_name} x {profile_name}: {status}")

    finished_at = datetime.now(timezone.utc)
    report_text = format_batch_report(
        batch_id=batch_context["batch_id"] if batch_context else None,
        cases=cases,
        profiles=[profile["profile_name"] for profile in profiles],
        run_entries=run_entries,
        max_parallel=max_parallel,
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
            max_parallel=max_parallel,
            report_text=report_text,
        )
        if len(cases) == 1 and len(run_entries) >= 2:
            compare_artifact_dirs([batch_context["batch_dir"]], output_dir=batch_context["batch_dir"])

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


def write_batch_artifacts(
    batch_dir,
    *,
    batch_id,
    cases,
    profiles,
    run_entries,
    started_at,
    finished_at,
    max_parallel,
    report_text,
):
    """Write a thin batch manifest and report."""
    manifest = {
        "schema_version": BATCH_ARTIFACT_SCHEMA_VERSION,
        "batch_id": batch_id,
        "started_at": _format_timestamp(started_at),
        "finished_at": _format_timestamp(finished_at),
        "max_parallel": max_parallel,
        "cases": list(cases),
        "profiles": list(profiles),
        "run_count": len(run_entries),
        "passed_run_count": sum(1 for entry in run_entries if entry["passed"]),
        "failed_run_count": sum(1 for entry in run_entries if not entry["passed"]),
        "runs": run_entries,
    }

    (batch_dir / "batch_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (batch_dir / "report.txt").write_text(report_text + "\n")


def format_batch_report(*, batch_id, cases, profiles, run_entries, max_parallel, batch_artifact_dir=None):
    """Format a short human-readable batch summary."""
    lines = []
    if batch_id:
        lines.append(f"Batch: {batch_id}")
    lines.append(f"Cases: {', '.join(cases)}")
    lines.append(f"Profiles: {', '.join(profiles)}")
    lines.append(f"Max parallel: {max_parallel}")
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
