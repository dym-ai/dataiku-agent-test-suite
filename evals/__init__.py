"""Evaluation helpers for case setup, validation, and teardown."""

import importlib
import json
import time
from pathlib import Path

from .builtins import BUILTIN_EVALUATORS

CASES_DIR = Path(__file__).parent.parent / "cases"
DEFAULT_EVALS = [{"name": "output_datasets"}]


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

    ts = int(time.time())
    project_key = f"BOBTEST_{case_name.upper()}_{ts}"
    auth_info = client.get_auth_info()
    owner = auth_info.get("associatedDSSUser") or auth_info["authIdentifier"]
    client.create_project(project_key, project_key, owner=owner)
    test_project = client.get_project(project_key)

    renames = case.get("source_renames", {})
    copied_names = []
    for ds_name in case["sources"]:
        source_ds = source_project.get_dataset(ds_name)
        target_name = renames.get(ds_name, ds_name)

        builder = test_project.new_managed_dataset(target_name)
        builder.with_store_into("filesystem_managed")
        builder.create()

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
    """Validate a project by running the case's configured evaluators."""
    case = _load_case(case_name)
    checks = []

    for spec in case.get("evals") or DEFAULT_EVALS:
        evaluator_name = spec["name"]
        evaluator = _resolve_evaluator(evaluator_name)
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


def _resolve_evaluator(name):
    if name in BUILTIN_EVALUATORS:
        return BUILTIN_EVALUATORS[name]

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

    return evaluator
