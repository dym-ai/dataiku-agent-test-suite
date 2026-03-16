"""Helpers for extracting and normalizing agent run statistics."""

import re


STAT_PATTERNS = {
    "total_tokens": [
        r"(?:total[_ ]tokens|tokens used)\"?\s*[:=]\s*([0-9][0-9,]*)",
        r"(?:total[_ ]tokens|tokens used)[ \t]+([0-9][0-9,]*)",
        r"(?:total[_ ]tokens|tokens used)\s*\n\s*([0-9][0-9,]*)",
    ],
    "tool_uses": [
        r"(?:tool[_ ]uses?|tool[_ ]calls?)\"?\s*[:=]\s*([0-9][0-9,]*)",
        r"(?:tool[_ ]uses?|tool[_ ]calls?)[ \t]+([0-9][0-9,]*)",
        r"(?:tool[_ ]uses?|tool[_ ]calls?)\s*\n\s*([0-9][0-9,]*)",
        r"([0-9][0-9,]*)[ \t]+tool[_ ](?:uses?|calls?)",
    ],
}


def extract_stats(stdout="", stderr=""):
    """Best-effort extraction of common agent stats from CLI output."""
    text = "\n".join(part for part in (stdout, stderr) if part)
    stats = {}
    for stat_name, patterns in STAT_PATTERNS.items():
        value = _extract_last_int_match(text, patterns)
        if value is not None:
            stats[stat_name] = value
    return stats


def normalize_stats(stats):
    """Coerce common stats fields to integers when possible."""
    if not isinstance(stats, dict):
        return {}

    normalized = dict(stats)
    if "tool_calls" in normalized and "tool_uses" not in normalized:
        normalized["tool_uses"] = normalized["tool_calls"]

    for stat_name in (
        "duration_ms",
        "input_tokens",
        "cache_creation_tokens",
        "cache_read_tokens",
        "cached_input_tokens",
        "output_tokens",
        "total_tokens",
        "tool_uses",
    ):
        if stat_name in normalized:
            coerced = _coerce_int(normalized.get(stat_name))
            if coerced is None:
                normalized.pop(stat_name, None)
            else:
                normalized[stat_name] = coerced

    tool_uses_by_type = normalized.get("tool_uses_by_type")
    if isinstance(tool_uses_by_type, dict):
        coerced_breakdown = {}
        for tool_type, value in tool_uses_by_type.items():
            if not isinstance(tool_type, str) or not tool_type.strip():
                continue
            coerced_value = _coerce_int(value)
            if coerced_value is not None:
                coerced_breakdown[tool_type] = coerced_value
        if coerced_breakdown:
            normalized["tool_uses_by_type"] = coerced_breakdown
        else:
            normalized.pop("tool_uses_by_type", None)
    else:
        normalized.pop("tool_uses_by_type", None)

    normalized.pop("tool_calls", None)
    return normalized


def _extract_last_int_match(text, patterns):
    matches = []
    for pattern in patterns:
        matches.extend(re.findall(pattern, text, flags=re.IGNORECASE))
    if not matches:
        return None
    return _coerce_int(matches[-1])


def _coerce_int(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        cleaned = value.replace(",", "").strip()
        if cleaned.isdigit():
            return int(cleaned)
    return None
