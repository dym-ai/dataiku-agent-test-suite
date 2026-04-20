"""Artifact-based comparison helpers."""

from __future__ import annotations

import json
import statistics
from pathlib import Path


COMPARE_SCHEMA_VERSION = 1


def compare_artifact_dirs(paths, output_dir=None):
    """Load run bundles from directories and return a compare summary/report."""
    run_dirs = discover_run_dirs(paths)
    if len(run_dirs) < 2:
        raise ValueError("Compare requires at least 2 run bundles")

    runs = [load_run_bundle(run_dir) for run_dir in run_dirs]
    case_names = sorted({run["manifest"]["case_name"] for run in runs})
    if len(case_names) != 1:
        raise ValueError(f"Compare requires runs from exactly one case. Found cases: {', '.join(case_names)}")

    summary = build_compare_summary(runs, output_dir=output_dir)
    report_text = format_compare_report(summary)

    if output_dir is not None:
        write_compare_outputs(output_dir, summary, report_text)

    return summary, report_text


def discover_run_dirs(paths):
    """Expand run bundle directories from a list of run or batch directories."""
    run_dirs = []
    for raw_path in paths:
        path = Path(raw_path).resolve()
        if not path.is_dir():
            raise ValueError(f"Compare expects directory paths only: {path}")

        if is_run_dir(path):
            run_dirs.append(path)
            continue

        if is_batch_dir(path):
            child_run_dirs = sorted(
                child for child in (path / "runs").iterdir()
                if child.is_dir() and is_run_dir(child)
            )
            run_dirs.extend(child_run_dirs)
            continue

        raise ValueError(f"Unrecognized artifact directory: {path}")

    return run_dirs


def is_run_dir(path):
    return (path / "run_manifest.json").is_file()


def is_batch_dir(path):
    return (path / "batch_manifest.json").is_file() and (path / "runs").is_dir()


def load_run_bundle(run_dir):
    manifest = json.loads((run_dir / "run_manifest.json").read_text())
    return {
        "run_dir": run_dir,
        "manifest": manifest,
    }


def build_compare_summary(runs, output_dir=None):
    case_name = runs[0]["manifest"]["case_name"]
    profile_names = []
    grouped = {}
    run_entries = []

    for run in runs:
        manifest = run["manifest"]
        profile_name = manifest["profile_name"]
        if profile_name not in grouped:
            grouped[profile_name] = []
            profile_names.append(profile_name)
        grouped[profile_name].append(run)
        run_entries.append(_build_run_entry(run, output_dir))

    profile_summaries = [_build_profile_summary(profile_name, grouped[profile_name]) for profile_name in profile_names]
    return {
        "schema_version": COMPARE_SCHEMA_VERSION,
        "case_name": case_name,
        "run_count": len(runs),
        "profile_count": len(profile_summaries),
        "profiles": profile_summaries,
        "runs": run_entries,
    }


def format_compare_report(summary):
    lines = [
        f"Case: {summary['case_name']}",
        f"Runs: {summary['run_count']}",
        "",
        "Profiles",
    ]

    for profile in summary["profiles"]:
        lines.append(
            f"- {profile['profile_name']}: {profile['run_count']} runs, "
            f"{profile['pass_count']} passed, {profile['fail_count']} failed, "
            f"median duration {_format_metric(profile['median_duration_ms'], suffix='ms')}, "
            f"median tokens {_format_metric(profile['median_total_tokens'])}, "
            f"median tool uses {_format_metric(profile['median_tool_uses'])}"
        )

    lines.append("")
    lines.append("Run results")
    for run in summary["runs"]:
        status = "PASS" if run["passed"] else "FAIL"
        lines.append(f"- {status} {run['profile_name']} {run['artifact_dir']}")

    return "\n".join(lines)


def write_compare_outputs(output_dir, summary, report_text):
    output_dir = Path(output_dir)
    (output_dir / "compare_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (output_dir / "compare_report.txt").write_text(report_text + "\n")


def _build_run_entry(run, output_dir):
    manifest = run["manifest"]
    execution = manifest.get("execution_result") or {}
    run_dir = run["run_dir"]
    if output_dir is not None:
        artifact_dir = str(run_dir.resolve().relative_to(Path(output_dir).resolve()))
    else:
        artifact_dir = str(run_dir)

    return {
        "profile_name": manifest["profile_name"],
        "artifact_dir": artifact_dir,
        "passed": manifest["passed"],
        "status": execution.get("status"),
        "duration_ms": execution.get("duration_ms"),
        "total_tokens": execution.get("total_tokens"),
        "tool_uses": execution.get("tool_uses"),
    }


def _build_profile_summary(profile_name, runs):
    durations = [run["manifest"].get("execution_result", {}).get("duration_ms") for run in runs]
    total_tokens = [run["manifest"].get("execution_result", {}).get("total_tokens") for run in runs]
    tool_uses = [run["manifest"].get("execution_result", {}).get("tool_uses") for run in runs]

    return {
        "profile_name": profile_name,
        "run_count": len(runs),
        "pass_count": sum(1 for run in runs if run["manifest"]["passed"]),
        "fail_count": sum(1 for run in runs if not run["manifest"]["passed"]),
        "median_duration_ms": _median_or_none(durations),
        "median_total_tokens": _median_or_none(total_tokens),
        "median_tool_uses": _median_or_none(tool_uses),
    }


def _median_or_none(values):
    filtered = [value for value in values if value is not None]
    if not filtered:
        return None
    return statistics.median(filtered)


def _format_metric(value, suffix=""):
    if value is None:
        return "n/a"
    if suffix:
        return f"{value}{suffix}"
    return str(value)
