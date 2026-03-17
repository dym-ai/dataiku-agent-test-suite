"""Helpers for redacting secrets from persisted harness output."""

import os
import re


SENSITIVE_ENV_NAME_RE = re.compile(
    r"(?:^|_)(?:API_KEY|TOKEN|SECRET|PASSWORD|PASSWD|PWD|ACCESS_TOKEN|REFRESH_TOKEN)(?:$|_)",
    re.IGNORECASE,
)
SENSITIVE_FIELD_RE = re.compile(
    r"(?:api[_-]?key|token|secret|password|passwd|pwd|access[_-]?token|refresh[_-]?token)",
    re.IGNORECASE,
)
SENSITIVE_FIELD_PATTERN = (
    r"[A-Za-z0-9_-]*?"
    r"(?:api[_-]?key|token|secret|password|passwd|pwd|access[_-]?token|refresh[_-]?token)"
    r"[A-Za-z0-9_-]*"
)
REDACTION_TOKEN = "[REDACTED]"


def collect_secret_values(env=None):
    env = env or os.environ

    values = []
    for name, value in env.items():
        if not value or not SENSITIVE_ENV_NAME_RE.search(name):
            continue
        if value in ("\n", "\r\n"):
            continue
        values.append(value)

    return sorted(set(values), key=len, reverse=True)


def redact_text(text, secret_values=None):
    if not text:
        return text

    redacted = str(text)
    secrets = secret_values if secret_values is not None else collect_secret_values()

    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, REDACTION_TOKEN)

    patterns = [
        (
            re.compile(r"(?i)(Authorization\s*:\s*Bearer\s+)([^\s\"'`]+)"),
            r"\1" + REDACTION_TOKEN,
        ),
        (
            re.compile(r"(?i)(Bearer\s+)([^\s\"'`]+)"),
            r"\1" + REDACTION_TOKEN,
        ),
        (
            re.compile(
                rf"(?i)(\"{SENSITIVE_FIELD_PATTERN}\""
                r"\s*:\s*\")([^\"]*)(\")"
            ),
            r"\1" + REDACTION_TOKEN + r"\3",
        ),
        (
            re.compile(
                rf"(?i)('{SENSITIVE_FIELD_PATTERN}'"
                r"\s*:\s*')([^']*)(')"
            ),
            r"\1" + REDACTION_TOKEN + r"\3",
        ),
        (
            re.compile(
                rf"(?i)((?:{SENSITIVE_FIELD_PATTERN})"
                r"\s*=\s*)([^\s\"']+)"
            ),
            r"\1" + REDACTION_TOKEN,
        ),
        (
            re.compile(
                rf"(?i)((?:{SENSITIVE_FIELD_PATTERN})"
                r"\s*:\s*)([^\s\"',}]+)"
            ),
            r"\1" + REDACTION_TOKEN,
        ),
        (
            re.compile(r"(https?://[^/\s:@]+:)([^@\s/]+)(@)"),
            r"\1" + REDACTION_TOKEN + r"\3",
        ),
    ]

    for pattern, replacement in patterns:
        redacted = pattern.sub(replacement, redacted)

    return redacted


def redact_value(value, secret_values=None):
    secrets = secret_values if secret_values is not None else collect_secret_values()

    if isinstance(value, str):
        return redact_text(value, secret_values=secrets)
    if isinstance(value, list):
        return [redact_value(item, secret_values=secrets) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_value(item, secret_values=secrets) for item in value)
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            redacted[key] = redact_value(item, secret_values=secrets)
        return redacted
    return value
