"""Built-in evaluators for Dataiku agent cases."""

from collections import Counter


def output_datasets(client, project_key, case, spec):
    """Validate output datasets for existence, schema, row count, and sample rows."""
    project = client.get_project(project_key)
    outputs = spec.get("outputs")
    if outputs is None:
        outputs = case.get("expected_outputs", {})
    if not outputs:
        raise ValueError("output_datasets evaluator requires outputs or case.expected_outputs")

    checks = []
    for ds_name, expected in outputs.items():
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

        try:
            actual_rows = _read_rows(ds)
        except Exception as exc:
            checks.append({
                "dataset": ds_name,
                "check": "data_readable",
                "passed": False,
                "message": str(exc),
            })
            continue

        checks.append({
            "dataset": ds_name,
            "check": "row_count",
            "passed": len(actual_rows) == expected["row_count"],
            "expected": expected["row_count"],
            "actual": len(actual_rows),
        })

        mismatches = []
        sample_data = expected.get("data", [])
        for i, exp in enumerate(sample_data):
            if i >= len(actual_rows):
                mismatches.append({
                    "row": i,
                    "column": "*",
                    "expected": exp,
                    "actual": "(missing row)",
                })
                continue

            actual = actual_rows[i]
            for col in expected_cols:
                actual_val = _normalize(actual.get(col))
                expected_val = _normalize(exp.get(col))
                if actual_val != expected_val:
                    mismatches.append({
                        "row": i,
                        "column": col,
                        "expected": expected_val,
                        "actual": actual_val,
                    })

        check = {
            "dataset": ds_name,
            "check": "data_values",
            "passed": len(mismatches) == 0,
            "sample_size": len(sample_data),
            "mismatches": len(mismatches),
        }
        if mismatches:
            check["first_mismatches"] = mismatches[:5]
        checks.append(check)

    return checks


def recipe_type_counts(client, project_key, case, spec):
    """Validate recipe counts by type."""
    expected = spec.get("expected", [])
    if not expected:
        raise ValueError("recipe_type_counts evaluator requires a non-empty expected list")

    actual_types = _get_recipe_type_counts(client, project_key)
    checks = []
    for item in expected:
        recipe_type = item["type"]
        expected_count = item["count"]
        checks.append({
            "check": "recipe_type_count",
            "recipe_type": recipe_type,
            "passed": actual_types.get(recipe_type, 0) == expected_count,
            "expected": expected_count,
            "actual": actual_types.get(recipe_type, 0),
        })
    return checks


def forbid_recipe_types(client, project_key, case, spec):
    """Fail when any recipe of a forbidden type is present."""
    forbidden_types = spec.get("types", [])
    if not forbidden_types:
        raise ValueError("forbid_recipe_types evaluator requires a non-empty types list")

    actual_types = _get_recipe_type_counts(client, project_key)
    checks = []
    for recipe_type in forbidden_types:
        checks.append({
            "check": "forbidden_recipe_type",
            "recipe_type": recipe_type,
            "passed": actual_types.get(recipe_type, 0) == 0,
            "expected": 0,
            "actual": actual_types.get(recipe_type, 0),
        })
    return checks


def _get_recipe_type_counts(client, project_key):
    project = client.get_project(project_key)
    counts = Counter()
    for recipe_summary in project.list_recipes():
        recipe = project.get_recipe(recipe_summary["name"])
        counts[recipe.get_settings().type] += 1
    return counts


def _read_rows(ds):
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
    if val is None:
        return None
    if hasattr(val, "isoformat"):
        return val.strftime("%Y-%m-%d")
    if isinstance(val, float) and val == int(val):
        return str(int(val))
    s = str(val)
    for suffix in ["T00:00:00+00:00", "T00:00:00Z", "T00:00:00"]:
        if s.endswith(suffix):
            s = s[: -len(suffix)]
    try:
        f = float(s)
        if f == int(f):
            return str(int(f))
    except (ValueError, OverflowError):
        pass
    return s


BUILTIN_EVALUATORS = {
    "output_datasets": output_datasets,
    "recipe_type_counts": recipe_type_counts,
    "forbid_recipe_types": forbid_recipe_types,
}
