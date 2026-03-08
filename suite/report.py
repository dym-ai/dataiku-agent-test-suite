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
        if "timeout_seconds" in stats:
            lines.append(f"- timeout: {stats['timeout_seconds']}s")
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
    formatter = CHECK_FORMATTERS.get(name)
    if formatter:
        return formatter(check)
    return name


def _format_check_detail(check):
    name = check["check"]
    formatter = CHECK_DETAIL_FORMATTERS.get(name)
    if formatter:
        return formatter(check)
    return ""


def _format_expected_actual(check):
    return f"{check['check']}(expected {check['expected']}, actual {check['actual']})"


def _format_flow_shape(check):
    return f"flow_shape_match(nodes {check['expected_nodes']}, recipes {check['expected_recipes']})"


def _format_recipe_config_match(check):
    return f"recipe_config_match(mode {check['mode']}, compare {check['compare']})"


def _format_recipe_config_entry(check):
    return f"recipe_config_entry({check['recipe_type']}, inputs {check['inputs']}, outputs {check['outputs']})"


def _format_recipe_type_count(check):
    return f"recipe_type_count({check['recipe_type']} {check['expected']}, actual {check['actual']})"


def _format_forbidden_recipe_type(check):
    return f"forbidden_recipe_type({check['recipe_type']}, expected {check['expected']}, actual {check['actual']})"


def _format_row_count(check):
    return f"row_count({check['dataset']}, expected {check['expected']}, actual {check['actual']})"


def _format_dataset_name_only(check):
    return f"{check['check']}({check['dataset']})"


def _format_data_values(check):
    mode = check.get("sample_mode", "ordered")
    return (
        f"data_values({check['dataset']}, mode {mode}, sample {check['sample_size']}, "
        f"mismatches {check['mismatches']})"
    )


def _format_message_detail(check):
    return check.get("message", "")


def _expected_actual_detail(check):
    if "expected" in check and "actual" in check:
        return f"expected={check['expected']!r}, actual={check['actual']!r}"
    return ""


def _format_data_values_detail(check):
    mismatches = check.get("first_mismatches") or []
    if not mismatches:
        return ""

    parts = []
    for mismatch in mismatches[:3]:
        row = mismatch.get("row", "?")
        column = mismatch.get("column", "?")
        expected = mismatch.get("expected")
        actual = mismatch.get("actual")
        parts.append(f"row {row} col {column}: expected {expected!r}, actual {actual!r}")
    return "; ".join(parts)


def _excerpt(text, limit=2000):
    if not text:
        return ""
    trimmed = text.strip()
    if len(trimmed) <= limit:
        return trimmed
    return trimmed[-limit:]


CHECK_FORMATTERS = {
    "agent_returncode": _format_expected_actual,
    "agent_status": _format_expected_actual,
    "flow_dataset_count": _format_expected_actual,
    "flow_recipe_count": _format_expected_actual,
    "flow_shape_match": _format_flow_shape,
    "recipe_config_match": _format_recipe_config_match,
    "recipe_config_entry": _format_recipe_config_entry,
    "recipe_type_count": _format_recipe_type_count,
    "forbidden_recipe_type": _format_forbidden_recipe_type,
    "row_count": _format_row_count,
    "schema_columns": _format_dataset_name_only,
    "schema_types": _format_dataset_name_only,
    "data_values": _format_data_values,
    "exists": _format_dataset_name_only,
    "data_readable": _format_dataset_name_only,
}


CHECK_DETAIL_FORMATTERS = {
    "agent_returncode": _expected_actual_detail,
    "agent_status": _expected_actual_detail,
    "flow_dataset_count": _expected_actual_detail,
    "flow_recipe_count": _expected_actual_detail,
    "flow_shape_match": _format_message_detail,
    "recipe_config_match": _format_message_detail,
    "recipe_type_count": _expected_actual_detail,
    "forbidden_recipe_type": _expected_actual_detail,
    "exists": _format_message_detail,
    "schema_columns": _expected_actual_detail,
    "schema_types": _expected_actual_detail,
    "row_count": _expected_actual_detail,
    "data_readable": _format_message_detail,
    "data_values": _format_data_values_detail,
}
