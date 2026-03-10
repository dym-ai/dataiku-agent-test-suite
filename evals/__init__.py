"""Evaluation helpers for case setup, validation, and teardown."""

import importlib
import json
import os
import time
import uuid
from pathlib import Path

from .builtins import BUILTIN_EVALUATORS, BUILTIN_EVALUATOR_VALIDATORS

CASES_DIR = Path(__file__).parent.parent / "cases"
DEFAULT_EVALS = [{"name": "output_datasets"}]
REQUIRED_CASE_FIELDS = {
    "name": str,
    "description": str,
    "prompt": str,
}


class CaseValidationError(ValueError):
    """Raised when a case definition is invalid."""


def _load_case(name):
    path = _resolve_case_path(name)
    return _load_case_from_path(path)


def list_cases():
    """Return validated case summaries in display order."""
    cases = []
    for name, path in _iter_case_paths():
        case = _load_case_from_path(path)
        cases.append({
            "name": name,
            "path": path,
            "description": case["description"],
        })
    return cases


def describe_case(name):
    """Return a validated case definition and its resolved path."""
    path = _resolve_case_path(name)
    case = _load_case_from_path(path)
    return {
        "name": name,
        "path": path,
        "case": case,
    }


def _load_case_from_path(path):
    with open(path) as f:
        case = json.load(f)
    _validate_case(case, path)
    return case


def setup(client, case_name):
    """Create a clean project and prepare source datasets for a case.

    Returns dict with:
        - project_key: the new project key
        - prompt: the natural language task to give the agent
        - sources: list of source dataset names prepared in the project
    """
    case_path = _resolve_case_path(case_name)
    case = _load_case_from_path(case_path)
    input_data = _input_data_specs(case, case_path)
    source_project_name = case.get("source_project")
    source_project = client.get_project(source_project_name) if source_project_name else None

    project_key = _build_project_key(case_name)
    auth_info = client.get_auth_info()
    owner = auth_info.get("associatedDSSUser") or auth_info["authIdentifier"]

    created_project = False
    try:
        client.create_project(project_key, project_key, owner=owner)
        created_project = True
        test_project = client.get_project(project_key)

        copied_names = []
        for ds_name in case["sources"]:
            input_spec = input_data.get(ds_name)
            if input_spec is not None:
                _create_uploaded_dataset_from_input_data(test_project, ds_name, input_spec)
            else:
                source_ds = source_project.get_dataset(ds_name)
                target_ds = _create_managed_source_dataset(test_project, ds_name)
                future = source_ds.copy_to(target_ds, sync_schema=True)
                future.wait_for_result()
            copied_names.append(ds_name)
    except Exception:
        if created_project:
            _delete_project_quietly(client, project_key)
        raise

    return {
        "project_key": project_key,
        "prompt": case["prompt"],
        "sources": copied_names,
    }


def validate(client, case_name, project_key, agent_stats=None):
    """Validate a project by running the case's configured evaluators."""
    case = _load_case(case_name)
    checks = []

    for spec in case.get("evals") or DEFAULT_EVALS:
        evaluator_name = spec["name"]
        evaluator, _ = _resolve_evaluator(evaluator_name)
        eval_checks = evaluator(client, project_key, case, spec)
        for check in eval_checks:
            check.setdefault("evaluator", evaluator_name)
        checks.extend(eval_checks)

    result = {
        "passed": all(check["passed"] for check in checks),
        "checks": checks,
    }
    if agent_stats:
        result["agent_stats"] = agent_stats
    return result


def teardown(client, project_key):
    """Delete the generated project."""
    client.get_project(project_key).delete()


def _validate_case(case, path):
    if not isinstance(case, dict):
        raise CaseValidationError(f"{path}: case file must contain a JSON object")

    for field_name, field_type in REQUIRED_CASE_FIELDS.items():
        if field_name not in case:
            raise CaseValidationError(f"{path}: missing required field '{field_name}'")
        if not isinstance(case[field_name], field_type) or not case[field_name].strip():
            raise CaseValidationError(f"{path}: field '{field_name}' must be a non-empty {field_type.__name__}")

    sources = case.get("sources")
    if not isinstance(sources, list) or not sources:
        raise CaseValidationError(f"{path}: field 'sources' must be a non-empty list")
    for index, source_name in enumerate(sources):
        if not isinstance(source_name, str) or not source_name.strip():
            raise CaseValidationError(f"{path}: sources[{index}] must be a non-empty string")

    source_project_name = case.get("source_project")
    if source_project_name is not None:
        if not isinstance(source_project_name, str) or not source_project_name.strip():
            raise CaseValidationError(f"{path}: field 'source_project' must be a non-empty string when provided")

    input_data = _input_data_specs(case, path)
    if not source_project_name and not input_data:
        raise CaseValidationError(f"{path}: define 'source_project', 'input_data', or both")

    for source_name in sources:
        if source_name not in input_data and not source_project_name:
            raise CaseValidationError(
                f"{path}: source '{source_name}' requires either 'source_project' or a matching input_data entry"
            )

    eval_specs = case.get("evals") or DEFAULT_EVALS
    if not isinstance(eval_specs, list) or not eval_specs:
        raise CaseValidationError(f"{path}: field 'evals' must be a non-empty list when provided")

    for index, spec in enumerate(eval_specs):
        _validate_eval_spec(case, spec, path, index)


def _validate_eval_spec(case, spec, path, index):
    if not isinstance(spec, dict):
        raise CaseValidationError(f"{path}: evals[{index}] must be an object")

    name = spec.get("name")
    if not isinstance(name, str) or not name.strip():
        raise CaseValidationError(f"{path}: evals[{index}].name must be a non-empty string")

    _, validator = _resolve_evaluator(name)
    if validator is None:
        return

    try:
        validator(spec, case)
    except CaseValidationError:
        raise
    except ValueError as exc:
        raise CaseValidationError(f"{path}: evals[{index}] invalid: {exc}") from exc


def _build_project_key(case_name):
    ts = int(time.time())
    suffix = uuid.uuid4().hex[:8].upper()
    safe_case_name = "".join(ch if ch.isalnum() else "_" for ch in case_name.upper()).strip("_")
    return f"COBUILD_{safe_case_name}_{ts}_{suffix}"


def _delete_project_quietly(client, project_key):
    try:
        client.get_project(project_key).delete()
    except Exception:
        pass


def _resolve_case_path(name):
    case_paths = dict(_iter_case_paths())
    path = case_paths.get(name)
    if path is not None:
        return path

    raise FileNotFoundError(f"Case '{name}' was not found under {CASES_DIR}")


def _iter_case_paths():
    case_paths = {}

    for legacy_path in sorted(CASES_DIR.glob("*.json")):
        case_paths.setdefault(legacy_path.stem, legacy_path)

    for case_dir in sorted(CASES_DIR.iterdir()):
        case_path = case_dir / "case.json"
        if case_dir.is_dir() and case_path.is_file():
            case_paths[case_dir.name] = case_path

    return sorted(case_paths.items())


def _input_data_specs(case, case_path):
    raw_specs = case.get("input_data") or {}
    if not isinstance(raw_specs, dict):
        raise CaseValidationError("field 'input_data' must be an object when provided")

    specs = {}
    for dataset_name, spec in raw_specs.items():
        if not isinstance(dataset_name, str) or not dataset_name.strip():
            raise CaseValidationError("input_data keys must be non-empty dataset names")
        if not isinstance(spec, dict):
            raise CaseValidationError(f"input_data.{dataset_name} must be an object")

        path_value = spec.get("path")
        if not isinstance(path_value, str) or not path_value.strip():
            raise CaseValidationError(f"input_data.{dataset_name}.path must be a non-empty string")

        resolved_path = (case_path.parent / path_value).resolve()
        if not resolved_path.is_file():
            raise CaseValidationError(f"input_data.{dataset_name}.path does not exist: {resolved_path}")

        specs[dataset_name] = {
            "path": resolved_path,
        }
    return specs


def _create_managed_source_dataset(project, dataset_name):
    builder = project.new_managed_dataset(dataset_name)
    builder.with_store_into("filesystem_managed")
    builder.create()
    return project.get_dataset(dataset_name)


def _create_uploaded_dataset_from_input_data(project, dataset_name, input_spec):
    dataset = project.create_upload_dataset(dataset_name, connection=_input_data_connection())
    input_path = input_spec["path"]
    with input_path.open("rb") as handle:
        dataset.uploaded_add_file(handle, input_path.name)
    settings = dataset.autodetect_settings()
    settings.save()


def _input_data_connection():
    return os.environ.get("DATAIKU_INPUT_DATA_CONNECTION", "filesystem_managed")


def _resolve_evaluator(name):
    if name in BUILTIN_EVALUATORS:
        return BUILTIN_EVALUATORS[name], BUILTIN_EVALUATOR_VALIDATORS.get(name)

    if ":" not in name:
        raise ValueError(
            f"Unknown evaluator '{name}'. Use a built-in name or a custom import path like 'my_module:my_eval'."
        )

    module_name, func_name = name.split(":", 1)
    module = importlib.import_module(module_name)
    try:
        evaluator = getattr(module, func_name)
    except AttributeError as exc:
        raise ValueError(f"Custom evaluator '{name}' was not found") from exc

    validator = getattr(evaluator, "validate_spec", None)
    if validator is not None and not callable(validator):
        raise ValueError(f"Custom evaluator '{name}' has a non-callable validate_spec attribute")

    return evaluator, validator
