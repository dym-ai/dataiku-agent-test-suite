"""Evaluation helpers for case setup, validation, and teardown."""

import json
import time
from pathlib import Path

CASES_DIR = Path(__file__).parent.parent / "cases"


def _load_case(name):
    path = CASES_DIR / f"{name}.json"
    with open(path) as f:
        return json.load(f)


def setup(client, case_name):
    """Create a clean project and copy source datasets from a case source project.

    Returns dict with:
        - project_key: the new project key
        - prompt: the natural language task to give the agent
        - sources: list of source dataset names copied
    """
    case = _load_case(case_name)
    source_project = client.get_project(case["source_project"])

    # Create a fresh project for this run
    ts = int(time.time())
    project_key = f"BOBTEST_{case_name.upper()}_{ts}"
    auth_info = client.get_auth_info()
    owner = auth_info.get("associatedDSSUser") or auth_info["authIdentifier"]
    client.create_project(project_key, project_key, owner=owner)
    test_project = client.get_project(project_key)

    # Copy source datasets (optionally rename for cleaner case prompts)
    renames = case.get("source_renames", {})
    copied_names = []
    for ds_name in case["sources"]:
        source_ds = source_project.get_dataset(ds_name)
        target_name = renames.get(ds_name, ds_name)

        # Create dataset in the generated project
        builder = test_project.new_managed_dataset(target_name)
        builder.with_store_into("filesystem_managed")
        builder.create()

        # Copy data from source to target (also syncs schema)
        target_ds = test_project.get_dataset(target_name)
        future = source_ds.copy_to(target_ds, sync_schema=True)
        future.wait_for_result()
        copied_names.append(target_name)

    return {
        "project_key": project_key,
        "prompt": case["prompt"],
        "sources": copied_names,
    }


def validate(client, case_name, project_key, agent_stats=None):
    """Validate that the project outputs match expected case data.

    Args:
        client: DSSClient instance
        case_name: case name (e.g. "dates", "crane")
        project_key: the generated project to validate
        agent_stats: optional dict with agent performance metrics, e.g.
            {"total_tokens": 80064, "tool_uses": 93, "duration_ms": 745545}

    Returns dict with:
        - passed: bool
        - checks: list of individual check results
        - agent_stats: the stats dict if provided
    """
    case = _load_case(case_name)
    project = client.get_project(project_key)
    checks = []

    # Check recipes: no python recipes, and expected recipe types are present
    expected_recipes = case.get("expected_recipes", [])
    if expected_recipes:
        actual_recipes = project.list_recipes()
        actual_types = []
        has_python = False
        for r in actual_recipes:
            recipe = project.get_recipe(r["name"])
            settings = recipe.get_settings()
            actual_types.append(settings.type)
            if settings.type == "python":
                has_python = True

        # Check no python recipes used
        checks.append({
            "check": "no_python_recipes",
            "passed": not has_python,
            "actual_types": actual_types,
            "message": "Python recipe used — visual recipes preferred" if has_python else "",
        })

        # Check expected recipe types are present (by count, not by name)
        expected_type_counts = {}
        for er in expected_recipes:
            t = er["type"]
            expected_type_counts[t] = expected_type_counts.get(t, 0) + 1

        actual_type_counts = {}
        for t in actual_types:
            actual_type_counts[t] = actual_type_counts.get(t, 0) + 1

        for exp_type, exp_count in expected_type_counts.items():
            actual_count = actual_type_counts.get(exp_type, 0)
            checks.append({
                "check": "recipe_type_count",
                "recipe_type": exp_type,
                "passed": actual_count >= exp_count,
                "expected": f">={exp_count}",
                "actual": actual_count,
            })

    for ds_name, expected in case["expected_outputs"].items():
        # Check dataset exists
        try:
            ds = project.get_dataset(ds_name)
            ds_def = ds.get_definition()
        except Exception:
            checks.append({
                "dataset": ds_name,
                "check": "exists",
                "passed": False,
                "message": f"Dataset '{ds_name}' not found",
            })
            continue

        checks.append({
            "dataset": ds_name,
            "check": "exists",
            "passed": True,
        })

        # Check schema (column names)
        actual_cols = [c["name"] for c in ds_def["schema"]["columns"]]
        expected_cols = [c["name"] for c in expected["schema"]]
        cols_match = set(actual_cols) == set(expected_cols)
        checks.append({
            "dataset": ds_name,
            "check": "schema_columns",
            "passed": cols_match,
            "expected": expected_cols,
            "actual": actual_cols,
        })

        if not cols_match:
            continue

        # Check schema types for the expected columns
        actual_types = {c["name"]: c.get("type") for c in ds_def["schema"]["columns"]}
        expected_types = {c["name"]: c.get("type") for c in expected["schema"]}
        types_match = all(actual_types.get(col) == expected_types.get(col) for col in expected_cols)
        checks.append({
            "dataset": ds_name,
            "check": "schema_types",
            "passed": types_match,
            "expected": expected_types,
            "actual": {col: actual_types.get(col) for col in expected_cols},
        })

        if not types_match:
            continue

        # Check data
        try:
            actual_rows = _read_rows(ds, project)
        except Exception as e:
            checks.append({
                "dataset": ds_name,
                "check": "data_readable",
                "passed": False,
                "message": str(e),
            })
            continue

        # Check row count
        count_match = len(actual_rows) == expected["row_count"]
        checks.append({
            "dataset": ds_name,
            "check": "row_count",
            "passed": count_match,
            "expected": expected["row_count"],
            "actual": len(actual_rows),
        })

        # Spot-check sample rows from the case against actual data.
        # Match by row position (case data = first N rows in order).
        mismatches = []
        sample_data = expected.get("data", [])
        for i, exp in enumerate(sample_data):
            if i >= len(actual_rows):
                mismatches.append({
                    "row": i, "column": "*",
                    "expected": exp, "actual": "(missing row)",
                })
                continue
            actual = actual_rows[i]
            for col in expected_cols:
                actual_val = _normalize(actual.get(col))
                expected_val = _normalize(exp.get(col))
                if actual_val != expected_val:
                    mismatches.append({
                        "row": i, "column": col,
                        "expected": expected_val, "actual": actual_val,
                    })

        data_match = len(mismatches) == 0
        check = {
            "dataset": ds_name,
            "check": "data_values",
            "passed": data_match,
            "sample_size": len(sample_data),
            "mismatches": len(mismatches),
        }
        if not data_match:
            check["first_mismatches"] = mismatches[:5]
        checks.append(check)

    passed = all(c["passed"] for c in checks)
    result = {"passed": passed, "checks": checks}
    if agent_stats:
        result["agent_stats"] = agent_stats
    return result


def teardown(client, project_key):
    """Delete the generated project."""
    client.get_project(project_key).delete()


def _read_rows(ds, project):
    """Read all rows from a dataset as list of dicts. No MCP dependency."""
    schema = ds.get_definition().get("schema", {}).get("columns", [])
    col_names = [c["name"] for c in schema]
    rows = []
    for row in ds.iter_rows():
        if isinstance(row, dict):
            rows.append(row)
        else:
            rows.append(dict(zip(col_names, row)))
    return rows


def _normalize(val):
    """Normalize a value for comparison (handles datetime objects, timezone suffixes, numeric types)."""
    if val is None:
        return None
    if hasattr(val, "isoformat"):
        return val.strftime("%Y-%m-%d")
    # Normalize numeric values: 402.0 == 402
    if isinstance(val, float) and val == int(val):
        return str(int(val))
    s = str(val)
    # Strip timezone suffix for date comparison
    for suffix in ["T00:00:00+00:00", "T00:00:00Z", "T00:00:00"]:
        if s.endswith(suffix):
            s = s[: -len(suffix)]
    # Normalize numeric strings: "402.0" -> "402"
    try:
        f = float(s)
        if f == int(f):
            return str(int(f))
    except (ValueError, OverflowError):
        pass
    return s
