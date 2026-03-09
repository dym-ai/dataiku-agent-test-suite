"""Evaluation helpers for case setup, validation, and teardown."""

import importlib
import json
import time
import uuid
from pathlib import Path

from .builtins import BUILTIN_EVALUATORS, BUILTIN_EVALUATOR_VALIDATORS

REPO_ROOT = Path(__file__).parent.parent
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
    path = CASES_DIR / f"{name}.json"
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
    case = _load_case(case_name)
    source_fixtures = _source_fixture_specs(case)
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
            fixture_spec = source_fixtures.get(ds_name)
            if fixture_spec is not None:
                _create_uploaded_dataset_from_fixture(test_project, ds_name, fixture_spec)
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

    source_fixtures = _source_fixture_specs(case)
    if not source_project_name and not source_fixtures:
        raise CaseValidationError(f"{path}: define 'source_project', 'source_fixtures', or both")

    for source_name in sources:
        if source_name not in source_fixtures and not source_project_name:
            raise CaseValidationError(
                f"{path}: source '{source_name}' requires either 'source_project' or a matching source_fixtures entry"
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
    return f"BOBTEST_{safe_case_name}_{ts}_{suffix}"


def _delete_project_quietly(client, project_key):
    try:
        client.get_project(project_key).delete()
    except Exception:
        pass


def _source_fixture_specs(case):
    raw_specs = case.get("source_fixtures") or {}
    if not isinstance(raw_specs, dict):
        raise CaseValidationError("field 'source_fixtures' must be an object when provided")

    specs = {}
    for dataset_name, spec in raw_specs.items():
        if not isinstance(dataset_name, str) or not dataset_name.strip():
            raise CaseValidationError("source_fixtures keys must be non-empty dataset names")
        if not isinstance(spec, dict):
            raise CaseValidationError(f"source_fixtures.{dataset_name} must be an object")

        path_value = spec.get("path")
        if not isinstance(path_value, str) or not path_value.strip():
            raise CaseValidationError(f"source_fixtures.{dataset_name}.path must be a non-empty string")

        resolved_path = (REPO_ROOT / path_value).resolve()
        if not resolved_path.is_file():
            raise CaseValidationError(f"source_fixtures.{dataset_name}.path does not exist: {resolved_path}")

        specs[dataset_name] = {
            "path": resolved_path,
        }
    return specs


def _create_managed_source_dataset(project, dataset_name):
    builder = project.new_managed_dataset(dataset_name)
    builder.with_store_into("filesystem_managed")
    builder.create()
    return project.get_dataset(dataset_name)


def _create_uploaded_dataset_from_fixture(project, dataset_name, fixture_spec):
    dataset = project.create_upload_dataset(dataset_name)
    fixture_path = fixture_spec["path"]
    with fixture_path.open("rb") as handle:
        dataset.uploaded_add_file(handle, fixture_path.name)
    settings = dataset.autodetect_settings()
    settings.save()


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
