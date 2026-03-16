"""Built-in evaluators for Dataiku agent cases."""

from collections import Counter
from copy import deepcopy


def output_datasets(client, project_key, case, spec):
    """Validate output datasets for existence, schema, row count, and sample rows."""
    project = client.get_project(project_key)
    outputs = spec.get("outputs")
    if outputs is None:
        outputs = case.get("expected_outputs", {})
    if not outputs:
        raise ValueError("output_datasets evaluator requires outputs or case.expected_outputs")
    sample_mode = spec.get("sample_mode", "unordered")
    key_columns = spec.get("key_columns", [])
    if sample_mode not in {"ordered", "unordered", "by_key"}:
        raise ValueError("output_datasets sample_mode must be 'ordered', 'unordered', or 'by_key'")
    if sample_mode == "by_key" and not key_columns:
        raise ValueError("output_datasets key_columns is required when sample_mode='by_key'")

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

        sample_data = expected.get("data", [])
        if sample_mode == "ordered":
            mismatches = _ordered_sample_mismatches(actual_rows, sample_data, expected_cols)
        elif sample_mode == "unordered":
            mismatches = _unordered_sample_mismatches(actual_rows, sample_data, expected_cols)
        else:
            mismatches = _keyed_sample_mismatches(actual_rows, sample_data, expected_cols, key_columns)

        check = {
            "dataset": ds_name,
            "check": "data_values",
            "passed": len(mismatches) == 0,
            "sample_size": len(sample_data),
            "mismatches": len(mismatches),
            "sample_mode": sample_mode,
        }
        if mismatches:
            check["first_mismatches"] = mismatches[:5]
        checks.append(check)

    return checks


def validate_output_datasets_spec(spec, case):
    outputs = spec.get("outputs")
    if outputs is None:
        outputs = case.get("expected_outputs")
    _validate_expected_outputs(outputs, "output_datasets requires outputs or case.expected_outputs")

    sample_mode = spec.get("sample_mode", "unordered")
    if sample_mode not in {"ordered", "unordered", "by_key"}:
        raise ValueError("output_datasets sample_mode must be 'ordered', 'unordered', or 'by_key'")

    key_columns = spec.get("key_columns", [])
    if sample_mode == "by_key":
        if not isinstance(key_columns, list) or not key_columns:
            raise ValueError("output_datasets key_columns is required when sample_mode='by_key'")
        for index, column_name in enumerate(key_columns):
            if not isinstance(column_name, str) or not column_name.strip():
                raise ValueError(f"output_datasets key_columns[{index}] must be a non-empty string")


def flow_shape_match(client, project_key, case, spec):
    """Validate anonymous flow structure using dataset schemas and recipe connectivity."""
    project_state = _collect_project_state(client, project_key)
    expected_nodes = spec.get("nodes", {})
    expected_recipes = spec.get("recipes", [])
    if not expected_nodes or not expected_recipes:
        raise ValueError("flow_shape_match requires non-empty nodes and recipes")

    exact_recipe_count = spec.get("exact_recipe_count", True)
    exact_dataset_count = spec.get("exact_dataset_count", False)
    match = _find_alias_assignment(
        expected_nodes=expected_nodes,
        expected_recipes=expected_recipes,
        actual_datasets=project_state["datasets"],
        actual_recipes=project_state["recipes"],
    )

    checks = []
    if exact_dataset_count:
        checks.append({
            "check": "flow_dataset_count",
            "passed": len(project_state["datasets"]) == len(expected_nodes),
            "expected": len(expected_nodes),
            "actual": len(project_state["datasets"]),
        })

    if exact_recipe_count:
        checks.append({
            "check": "flow_recipe_count",
            "passed": len(project_state["recipes"]) == len(expected_recipes),
            "expected": len(expected_recipes),
            "actual": len(project_state["recipes"]),
        })

    check = {
        "check": "flow_shape_match",
        "passed": match is not None,
        "expected_nodes": len(expected_nodes),
        "expected_recipes": len(expected_recipes),
    }
    if match is not None:
        check["alias_mapping"] = match["assignment"]
    else:
        check["message"] = "No dataset-to-schema mapping satisfied the expected recipe graph"
    checks.append(check)
    return checks


def validate_flow_shape_match_spec(spec, case):
    _validate_flow_spec(spec, require_recipe_config=False)


def recipe_config_match(client, project_key, case, spec):
    """Validate recipe payload/params on a matched anonymous flow."""
    project_state = _collect_project_state(client, project_key)
    expected_nodes = spec.get("nodes", {})
    expected_recipes = spec.get("recipes", [])
    if not expected_nodes or not expected_recipes:
        raise ValueError("recipe_config_match requires non-empty nodes and recipes")

    config_mode = spec.get("mode", "raw")
    compare_mode = spec.get("compare", "subset")
    if config_mode not in {"raw", "normalized"}:
        raise ValueError("recipe_config_match mode must be 'raw' or 'normalized'")
    if compare_mode not in {"subset", "exact"}:
        raise ValueError("recipe_config_match compare must be 'subset' or 'exact'")

    match = _find_alias_assignment(
        expected_nodes=expected_nodes,
        expected_recipes=expected_recipes,
        actual_datasets=project_state["datasets"],
        actual_recipes=project_state["recipes"],
        require_config=True,
        config_mode=config_mode,
        compare_mode=compare_mode,
    )

    checks = []
    if match is None:
        checks.append({
            "check": "recipe_config_match",
            "passed": False,
            "mode": config_mode,
            "compare": compare_mode,
            "message": "No recipe mapping matched the expected flow shape and recipe config",
        })
        return checks

    checks.append({
        "check": "recipe_config_match",
        "passed": True,
        "mode": config_mode,
        "compare": compare_mode,
        "matched_recipes": len(expected_recipes),
        "alias_mapping": match["assignment"],
    })

    for expected_index, actual_index in sorted(match["recipe_matches"].items()):
        expected_recipe = expected_recipes[expected_index]
        actual_recipe = project_state["recipes"][actual_index]
        checks.append({
            "check": "recipe_config_entry",
            "passed": True,
            "recipe_type": expected_recipe["type"],
            "inputs": expected_recipe["inputs"],
            "outputs": expected_recipe["outputs"],
            "recipe_name": actual_recipe["name"],
        })

    return checks


def validate_recipe_config_match_spec(spec, case):
    _validate_flow_spec(spec, require_recipe_config=True)

    mode = spec.get("mode", "raw")
    compare = spec.get("compare", "subset")
    if mode not in {"raw", "normalized"}:
        raise ValueError("recipe_config_match mode must be 'raw' or 'normalized'")
    if compare not in {"subset", "exact"}:
        raise ValueError("recipe_config_match compare must be 'subset' or 'exact'")


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


def validate_recipe_type_counts_spec(spec, case):
    expected = spec.get("expected")
    if not isinstance(expected, list) or not expected:
        raise ValueError("recipe_type_counts requires a non-empty expected list")
    for index, item in enumerate(expected):
        if not isinstance(item, dict):
            raise ValueError(f"recipe_type_counts expected[{index}] must be an object")
        recipe_type = item.get("type")
        count = item.get("count")
        if not isinstance(recipe_type, str) or not recipe_type.strip():
            raise ValueError(f"recipe_type_counts expected[{index}].type must be a non-empty string")
        if not isinstance(count, int) or count < 0:
            raise ValueError(f"recipe_type_counts expected[{index}].count must be a non-negative integer")


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


def validate_forbid_recipe_types_spec(spec, case):
    forbidden_types = spec.get("types")
    if not isinstance(forbidden_types, list) or not forbidden_types:
        raise ValueError("forbid_recipe_types requires a non-empty types list")
    for index, recipe_type in enumerate(forbidden_types):
        if not isinstance(recipe_type, str) or not recipe_type.strip():
            raise ValueError(f"forbid_recipe_types types[{index}] must be a non-empty string")


def _collect_project_state(client, project_key):
    project = client.get_project(project_key)
    datasets = {}
    for dataset in project.list_datasets(as_type="objects"):
        ds_def = dataset.get_definition()
        datasets[dataset.name] = {
            "name": dataset.name,
            "schema": ds_def.get("schema", {}).get("columns", []),
            "schema_signature": _schema_signature(ds_def.get("schema", {}).get("columns", [])),
        }

    recipes = []
    for recipe_summary in project.list_recipes():
        recipe = project.get_recipe(recipe_summary["name"])
        settings = recipe.get_settings()
        recipes.append({
            "name": recipe_summary["name"],
            "type": settings.type,
            "inputs": sorted(
                ref for ref in (_strip_project_ref(r, project_key) for r in settings.get_flat_input_refs()) if ref in datasets
            ),
            "outputs": sorted(
                ref for ref in (_strip_project_ref(r, project_key) for r in settings.get_flat_output_refs()) if ref in datasets
            ),
            "config_raw": _recipe_config(settings, mode="raw"),
            "config_normalized": _recipe_config(settings, mode="normalized"),
        })

    return {"datasets": datasets, "recipes": recipes}


def _find_alias_assignment(
    expected_nodes,
    expected_recipes,
    actual_datasets,
    actual_recipes,
    require_config=False,
    config_mode="raw",
    compare_mode="subset",
):
    aliases = sorted(expected_nodes, key=lambda alias: len(_candidate_dataset_names(alias, expected_nodes, actual_datasets)))
    candidates = {alias: _candidate_dataset_names(alias, expected_nodes, actual_datasets) for alias in aliases}
    if any(len(names) == 0 for names in candidates.values()):
        return None

    def search(index, assignment, used_dataset_names):
        if index == len(aliases):
            recipe_matches = _find_recipe_matches(
                expected_recipes=expected_recipes,
                actual_recipes=actual_recipes,
                assignment=assignment,
                require_config=require_config,
                config_mode=config_mode,
                compare_mode=compare_mode,
            )
            if recipe_matches is None:
                return None
            return {
                "assignment": dict(assignment),
                "recipe_matches": recipe_matches,
            }

        alias = aliases[index]
        for dataset_name in candidates[alias]:
            if dataset_name in used_dataset_names:
                continue
            assignment[alias] = dataset_name
            used_dataset_names.add(dataset_name)
            result = search(index + 1, assignment, used_dataset_names)
            if result is not None:
                return result
            used_dataset_names.remove(dataset_name)
            del assignment[alias]
        return None

    return search(0, {}, set())


def _find_recipe_matches(
    expected_recipes,
    actual_recipes,
    assignment,
    require_config=False,
    config_mode="raw",
    compare_mode="subset",
):
    candidates = {}
    for expected_index, expected_recipe in enumerate(expected_recipes):
        expected_inputs = sorted(assignment[alias] for alias in expected_recipe["inputs"])
        expected_outputs = sorted(assignment[alias] for alias in expected_recipe["outputs"])
        matching_actuals = []
        for actual_index, actual_recipe in enumerate(actual_recipes):
            if actual_recipe["type"] != expected_recipe["type"]:
                continue
            if actual_recipe["inputs"] != expected_inputs:
                continue
            if actual_recipe["outputs"] != expected_outputs:
                continue
            if require_config and not _config_matches(
                expected_recipe.get("config", {}),
                actual_recipe[f"config_{config_mode}"],
                compare_mode=compare_mode,
                config_mode=config_mode,
            ):
                continue
            matching_actuals.append(actual_index)
        candidates[expected_index] = matching_actuals

    if any(len(indices) == 0 for indices in candidates.values()):
        return None

    ordered_expected = sorted(candidates, key=lambda idx: len(candidates[idx]))

    def search(index, used_actual_indices, mapping):
        if index == len(ordered_expected):
            return dict(mapping)

        expected_index = ordered_expected[index]
        for actual_index in candidates[expected_index]:
            if actual_index in used_actual_indices:
                continue
            mapping[expected_index] = actual_index
            used_actual_indices.add(actual_index)
            result = search(index + 1, used_actual_indices, mapping)
            if result is not None:
                return result
            used_actual_indices.remove(actual_index)
            del mapping[expected_index]
        return None

    return search(0, set(), {})


def _candidate_dataset_names(alias, expected_nodes, actual_datasets):
    expected_schema = _schema_signature(expected_nodes[alias]["schema"])
    return [
        dataset_name
        for dataset_name, dataset in actual_datasets.items()
        if dataset["schema_signature"] == expected_schema
    ]


def _validate_flow_spec(spec, require_recipe_config):
    nodes = spec.get("nodes")
    recipes = spec.get("recipes")
    if not isinstance(nodes, dict) or not nodes:
        raise ValueError("nodes must be a non-empty object")
    if not isinstance(recipes, list) or not recipes:
        raise ValueError("recipes must be a non-empty list")

    for alias, node in nodes.items():
        if not isinstance(alias, str) or not alias.strip():
            raise ValueError("node aliases must be non-empty strings")
        if not isinstance(node, dict):
            raise ValueError(f"node '{alias}' must be an object")
        schema = node.get("schema")
        _validate_schema(schema, f"nodes['{alias}'].schema")

    known_aliases = set(nodes)
    for index, recipe in enumerate(recipes):
        if not isinstance(recipe, dict):
            raise ValueError(f"recipes[{index}] must be an object")
        recipe_type = recipe.get("type")
        if not isinstance(recipe_type, str) or not recipe_type.strip():
            raise ValueError(f"recipes[{index}].type must be a non-empty string")
        _validate_alias_list(recipe.get("inputs"), known_aliases, f"recipes[{index}].inputs")
        _validate_alias_list(recipe.get("outputs"), known_aliases, f"recipes[{index}].outputs")
        if require_recipe_config and "config" not in recipe:
            raise ValueError(f"recipes[{index}].config is required")
        if "config" in recipe and not isinstance(recipe["config"], dict):
            raise ValueError(f"recipes[{index}].config must be an object")

    for field_name in ("exact_recipe_count", "exact_dataset_count"):
        if field_name in spec and not isinstance(spec[field_name], bool):
            raise ValueError(f"{field_name} must be a boolean")


def _validate_expected_outputs(outputs, missing_message):
    if not isinstance(outputs, dict) or not outputs:
        raise ValueError(missing_message)
    for dataset_name, expected in outputs.items():
        if not isinstance(dataset_name, str) or not dataset_name.strip():
            raise ValueError("output dataset names must be non-empty strings")
        if not isinstance(expected, dict):
            raise ValueError(f"expected output '{dataset_name}' must be an object")
        _validate_schema(expected.get("schema"), f"expected_outputs['{dataset_name}'].schema")
        row_count = expected.get("row_count")
        if not isinstance(row_count, int) or row_count < 0:
            raise ValueError(f"expected_outputs['{dataset_name}'].row_count must be a non-negative integer")
        data = expected.get("data", [])
        if not isinstance(data, list):
            raise ValueError(f"expected_outputs['{dataset_name}'].data must be a list")
        for index, row in enumerate(data):
            if not isinstance(row, dict):
                raise ValueError(f"expected_outputs['{dataset_name}'].data[{index}] must be an object")


def _validate_schema(schema, label):
    if not isinstance(schema, list) or not schema:
        raise ValueError(f"{label} must be a non-empty list")
    for index, column in enumerate(schema):
        if not isinstance(column, dict):
            raise ValueError(f"{label}[{index}] must be an object")
        name = column.get("name")
        column_type = column.get("type")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{label}[{index}].name must be a non-empty string")
        if not isinstance(column_type, str) or not column_type.strip():
            raise ValueError(f"{label}[{index}].type must be a non-empty string")


def _validate_alias_list(aliases, known_aliases, label):
    if not isinstance(aliases, list) or not aliases:
        raise ValueError(f"{label} must be a non-empty list")
    for index, alias in enumerate(aliases):
        if not isinstance(alias, str) or not alias.strip():
            raise ValueError(f"{label}[{index}] must be a non-empty string")
        if alias not in known_aliases:
            raise ValueError(f"{label}[{index}] refers to unknown node alias '{alias}'")


def _recipe_config(settings, mode):
    config = {
        "params": deepcopy(settings.get_recipe_params() or {}),
        "payload": _recipe_payload(settings),
    }
    if mode == "raw":
        return config
    if mode == "normalized":
        return _prune_empty(config)
    raise ValueError(f"Unsupported recipe config mode: {mode}")


def _recipe_payload(settings):
    try:
        return deepcopy(settings.get_json_payload())
    except Exception:
        return settings.get_payload()


def _config_matches(expected_config, actual_config, compare_mode, config_mode):
    if compare_mode == "exact":
        if config_mode == "normalized":
            return _prune_empty(deepcopy(expected_config)) == actual_config
        return deepcopy(expected_config) == actual_config
    if compare_mode == "subset":
        return _is_subset(_prune_empty(deepcopy(expected_config)), actual_config)
    raise ValueError(f"Unsupported compare mode: {compare_mode}")


def _is_subset(expected, actual):
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        return all(key in actual and _is_subset(value, actual[key]) for key, value in expected.items())

    if isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) > len(actual):
            return False
        return all(_is_subset(expected[index], actual[index]) for index in range(len(expected)))

    return expected == actual


def _prune_empty(value):
    if isinstance(value, dict):
        pruned = {}
        for key, item in value.items():
            normalized = _prune_empty(item)
            if normalized in (None, {}, []):
                continue
            pruned[key] = normalized
        return pruned

    if isinstance(value, list):
        return [_prune_empty(item) for item in value]

    return value


def _schema_signature(columns):
    return tuple(
        (column.get("name"), column.get("type"))
        for column in columns
    )


def _get_recipe_type_counts(client, project_key):
    project = client.get_project(project_key)
    counts = Counter()
    for recipe_summary in project.list_recipes():
        recipe = project.get_recipe(recipe_summary["name"])
        counts[recipe.get_settings().type] += 1
    return counts


def _strip_project_ref(ref, project_key):
    prefix = f"{project_key}."
    if ref.startswith(prefix):
        return ref[len(prefix):]
    return ref


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


def _ordered_sample_mismatches(actual_rows, sample_data, expected_cols):
    mismatches = []
    for index, expected_row in enumerate(sample_data):
        if index >= len(actual_rows):
            mismatches.append({
                "row": index,
                "column": "*",
                "expected": expected_row,
                "actual": "(missing row)",
            })
            continue

        mismatches.extend(_row_mismatches(index, actual_rows[index], expected_row, expected_cols))
    return mismatches


def _unordered_sample_mismatches(actual_rows, sample_data, expected_cols):
    mismatches = []
    remaining_indices = set(range(len(actual_rows)))

    for index, expected_row in enumerate(sample_data):
        matched_index = None
        matched_row_mismatches = None

        for actual_index in sorted(remaining_indices):
            candidate_mismatches = _row_mismatches(index, actual_rows[actual_index], expected_row, expected_cols)
            if not candidate_mismatches:
                matched_index = actual_index
                matched_row_mismatches = []
                break
            if matched_row_mismatches is None or len(candidate_mismatches) < len(matched_row_mismatches):
                matched_row_mismatches = candidate_mismatches

        if matched_index is not None:
            remaining_indices.remove(matched_index)
            continue

        if matched_row_mismatches:
            mismatches.extend(matched_row_mismatches[:1])
        else:
            mismatches.append({
                "row": index,
                "column": "*",
                "expected": expected_row,
                "actual": "(no matching row found)",
            })

    return mismatches


def _keyed_sample_mismatches(actual_rows, sample_data, expected_cols, key_columns):
    mismatches = []
    actual_by_key = {}

    for actual_index, actual_row in enumerate(actual_rows):
        key = _row_key(actual_row, key_columns)
        if key in actual_by_key:
            mismatches.append({
                "row": actual_index,
                "column": ",".join(key_columns),
                "expected": "(unique key)",
                "actual": f"duplicate actual key {key}",
            })
            continue
        actual_by_key[key] = actual_row

    seen_expected_keys = set()
    for index, expected_row in enumerate(sample_data):
        key = _row_key(expected_row, key_columns)
        if key in seen_expected_keys:
            mismatches.append({
                "row": index,
                "column": ",".join(key_columns),
                "expected": "(unique key)",
                "actual": f"duplicate expected key {key}",
            })
            continue
        seen_expected_keys.add(key)

        actual_row = actual_by_key.get(key)
        if actual_row is None:
            mismatches.append({
                "row": index,
                "column": ",".join(key_columns),
                "expected": key,
                "actual": "(missing key)",
            })
            continue

        mismatches.extend(_row_mismatches(index, actual_row, expected_row, expected_cols))

    return mismatches


def _row_key(row, key_columns):
    return tuple(_normalize(row.get(column)) for column in key_columns)


def _row_mismatches(index, actual_row, expected_row, expected_cols):
    mismatches = []
    for col in expected_cols:
        actual_val = _normalize(actual_row.get(col))
        expected_val = _normalize(expected_row.get(col))
        if actual_val != expected_val:
            mismatches.append({
                "row": index,
                "column": col,
                "expected": expected_val,
                "actual": actual_val,
            })
    return mismatches


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


def skill_files_read(client, project_key, case, spec, context):
    """Check that all listed skill file paths were read via the Read tool."""
    required = spec.get("skills", [])
    tool_trace = context.get("tool_trace") or []
    read_paths = {
        call.get("input", {}).get("file_path", "")
        for call in tool_trace
        if call.get("name") == "Read"
    }

    if not read_paths:
        return [{
            "check": "skill_files_read",
            "passed": True,
            "skipped": True,
            "message": "skipped: no Read tool calls in trace",
        }]

    return [
        {
            "check": "skill_file_read",
            "skill": skill_path,
            "passed": any(p.endswith(skill_path) for p in read_paths),
        }
        for skill_path in required
    ]


def validate_skill_files_read_spec(spec, case):
    skills = spec.get("skills")
    if not isinstance(skills, list) or not skills:
        raise ValueError("skill_files_read requires a non-empty skills list")
    for index, skill_path in enumerate(skills):
        if not isinstance(skill_path, str) or not skill_path.strip():
            raise ValueError(f"skill_files_read skills[{index}] must be a non-empty string")


def tool_calls_include(client, project_key, case, spec, context):
    """Check that all listed tool names appear at least once in the tool trace."""
    required = spec.get("tools", [])
    tool_trace = context.get("tool_trace") or []
    actual_names = {call.get("name") for call in tool_trace}
    return [
        {
            "check": "tool_call_present",
            "tool": tool_name,
            "passed": tool_name in actual_names,
        }
        for tool_name in required
    ]


def validate_tool_calls_include_spec(spec, case):
    _validate_tool_name_list(spec.get("tools"), "tool_calls_include", "tools")


def skills_used(client, project_key, case, spec, context):
    """Check that all listed skills were invoked via the Skill tool."""
    required = spec.get("skills", [])
    tool_trace = context.get("tool_trace") or []
    skill_calls = [call for call in tool_trace if call.get("name") == "Skill"]

    if not skill_calls:
        return [{
            "check": "skills_used",
            "passed": True,
            "skipped": True,
            "message": "skipped: no Skill tool calls in trace (Claude Code only)",
        }]

    actual_skills = {call.get("input", {}).get("skill") for call in skill_calls}
    return [
        {
            "check": "skill_used",
            "skill": skill_name,
            "passed": skill_name in actual_skills,
        }
        for skill_name in required
    ]


def validate_skills_used_spec(spec, case):
    skills = spec.get("skills")
    if not isinstance(skills, list) or not skills:
        raise ValueError("skills_used requires a non-empty skills list")
    for index, skill_name in enumerate(skills):
        if not isinstance(skill_name, str) or not skill_name.strip():
            raise ValueError(f"skills_used skills[{index}] must be a non-empty string")


def tool_calls_exclude(client, project_key, case, spec, context):
    """Check that none of the listed tool names appear in the tool trace."""
    forbidden = spec.get("tools", [])
    tool_trace = context.get("tool_trace") or []
    actual_names = {call.get("name") for call in tool_trace}
    return [
        {
            "check": "tool_call_absent",
            "tool": tool_name,
            "passed": tool_name not in actual_names,
        }
        for tool_name in forbidden
    ]


def validate_tool_calls_exclude_spec(spec, case):
    _validate_tool_name_list(spec.get("tools"), "tool_calls_exclude", "tools")


def _validate_tool_name_list(tools, evaluator_name, field_name):
    if not isinstance(tools, list) or not tools:
        raise ValueError(f"{evaluator_name} requires a non-empty {field_name} list")
    for index, tool_name in enumerate(tools):
        if not isinstance(tool_name, str) or not tool_name.strip():
            raise ValueError(f"{evaluator_name} {field_name}[{index}] must be a non-empty string")


BUILTIN_EVALUATORS = {
    "output_datasets": output_datasets,
    "flow_shape_match": flow_shape_match,
    "recipe_config_match": recipe_config_match,
    "recipe_type_counts": recipe_type_counts,
    "forbid_recipe_types": forbid_recipe_types,
    "tool_calls_include": tool_calls_include,
    "skills_used": skills_used,
    "tool_calls_exclude": tool_calls_exclude,
    "skill_files_read": skill_files_read,
}

BUILTIN_EVALUATOR_VALIDATORS = {
    "output_datasets": validate_output_datasets_spec,
    "flow_shape_match": validate_flow_shape_match_spec,
    "recipe_config_match": validate_recipe_config_match_spec,
    "recipe_type_counts": validate_recipe_type_counts_spec,
    "forbid_recipe_types": validate_forbid_recipe_types_spec,
    "tool_calls_include": validate_tool_calls_include_spec,
    "skills_used": validate_skills_used_spec,
    "tool_calls_exclude": validate_tool_calls_exclude_spec,
    "skill_files_read": validate_skill_files_read_spec,
}
