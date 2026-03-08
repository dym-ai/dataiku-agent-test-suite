"""Human-friendly formatting for test results."""


def format_report(
    case_name,
    project_key,
    agent_result,
    validation_result,
    project_url=None,
    artifacts_dir=None,
    verbose=False,
):
    lines = [
        f"Case: {case_name}",
        f"Project: {project_key}",
        f"Agent: {agent_result.get('status', 'unknown')}",
        f"Result: {'PASS' if validation_result['passed'] else 'FAIL'}",
    ]

    if project_url:
        lines.append(f"Project URL: {project_url}")
    if artifacts_dir:
        lines.append(f"Artifacts: {artifacts_dir}")

    first_failure = _first_failure(validation_result)
    if first_failure:
        lines.append(f"First failure: {_format_check(first_failure)}")
        detail = _format_check_detail(first_failure)
        if detail:
            lines.append(f"Failure detail: {detail}")

    lines.append("")
    lines.append("Checks")
    for check in validation_result["checks"]:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {_format_check(check)}: {status}")
        if not check["passed"]:
            detail = _format_check_detail(check)
            if detail:
                lines.append(f"  detail: {detail}")

    stats = agent_result.get("stats") or validation_result.get("agent_stats") or {}
    if stats:
        lines.append("")
        lines.append("Agent stats")
        if "duration_ms" in stats:
            lines.append(f"- duration: {stats['duration_ms'] / 1000:.1f}s")
        if "total_tokens" in stats:
            lines.append(f"- total tokens: {stats['total_tokens']:,}")
        if "tool_uses" in stats:
            lines.append(f"- tool uses: {stats['tool_uses']}")

    summary = agent_result.get("summary")
    if summary:
        lines.append("")
        lines.append("Agent summary")
        lines.append(f"- {summary}")

    if verbose:
        stdout_excerpt = _excerpt(agent_result.get("stdout"))
        if stdout_excerpt:
            lines.append("")
            lines.append("Agent stdout excerpt")
            lines.append(stdout_excerpt)

        stderr_excerpt = _excerpt(agent_result.get("stderr"))
        if stderr_excerpt:
            lines.append("")
            lines.append("Agent stderr excerpt")
            lines.append(stderr_excerpt)

    return "\n".join(lines)


def _first_failure(validation_result):
    for check in validation_result["checks"]:
        if not check["passed"]:
            return check
    return None


def _format_check(check):
    name = check["check"]
    if name == "agent_returncode":
        return f"agent_returncode(expected {check['expected']}, actual {check['actual']})"
    if name == "agent_status":
        return f"agent_status(expected {check['expected']}, actual {check['actual']})"
    if name == "flow_dataset_count":
        return f"flow_dataset_count(expected {check['expected']}, actual {check['actual']})"
    if name == "flow_recipe_count":
        return f"flow_recipe_count(expected {check['expected']}, actual {check['actual']})"
    if name == "flow_shape_match":
        return f"flow_shape_match(nodes {check['expected_nodes']}, recipes {check['expected_recipes']})"
    if name == "recipe_config_match":
        return f"recipe_config_match(mode {check['mode']}, compare {check['compare']})"
    if name == "recipe_config_entry":
        return f"recipe_config_entry({check['recipe_type']}, inputs {check['inputs']}, outputs {check['outputs']})"
    if name == "recipe_type_count":
        return f"recipe_type_count({check['recipe_type']} {check['expected']}, actual {check['actual']})"
    if name == "forbidden_recipe_type":
        return f"forbidden_recipe_type({check['recipe_type']}, expected {check['expected']}, actual {check['actual']})"
    if "dataset" in check:
        if name == "row_count":
            return f"row_count({check['dataset']}, expected {check['expected']}, actual {check['actual']})"
        if name == "schema_columns":
            return f"schema_columns({check['dataset']})"
        if name == "schema_types":
            return f"schema_types({check['dataset']})"
        if name == "data_values":
            mode = check.get("sample_mode", "ordered")
            return f"data_values({check['dataset']}, mode {mode}, sample {check['sample_size']}, mismatches {check['mismatches']})"
        if name == "exists":
            return f"exists({check['dataset']})"
        if name == "data_readable":
            return f"data_readable({check['dataset']})"
    return name


def _format_check_detail(check):
    name = check["check"]
    if name in {"agent_returncode", "agent_status", "flow_dataset_count", "flow_recipe_count"}:
        return _expected_actual_detail(check)
    if name == "flow_shape_match":
        return check.get("message", "")
    if name == "recipe_config_match":
        return check.get("message", "")
    if name == "recipe_type_count":
        return _expected_actual_detail(check)
    if name == "forbidden_recipe_type":
        return _expected_actual_detail(check)
    if name == "exists":
        return check.get("message", "")
    if name == "schema_columns":
        return _expected_actual_detail(check)
    if name == "schema_types":
        return _expected_actual_detail(check)
    if name == "row_count":
        return _expected_actual_detail(check)
    if name == "data_readable":
        return check.get("message", "")
    if name == "data_values":
        mismatches = check.get("first_mismatches") or []
        if mismatches:
            parts = []
            for mismatch in mismatches[:3]:
                row = mismatch.get("row", "?")
                column = mismatch.get("column", "?")
                expected = mismatch.get("expected")
                actual = mismatch.get("actual")
                parts.append(f"row {row} col {column}: expected {expected!r}, actual {actual!r}")
            return "; ".join(parts)
    return ""


def _expected_actual_detail(check):
    if "expected" in check and "actual" in check:
        return f"expected={check['expected']!r}, actual={check['actual']!r}"
    return ""


def _excerpt(text, limit=2000):
    if not text:
        return ""
    trimmed = text.strip()
    if len(trimmed) <= limit:
        return trimmed
    return trimmed[-limit:]
