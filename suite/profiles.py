"""Profile loading and resolution helpers."""

import json
import os
import re
from pathlib import Path


ENV_VAR_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


def load_profile_config(config_path):
    """Load and validate the local profile config file."""
    if not config_path.is_file():
        return {"defaults": {}, "profiles": {}}

    try:
        raw_config = json.loads(config_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {config_path}: {exc}") from exc

    if not isinstance(raw_config, dict):
        raise ValueError(f"{config_path} must contain a JSON object")

    unknown_keys = sorted(set(raw_config) - {"defaults", "profiles"})
    if unknown_keys:
        raise ValueError(f"{config_path} contains unsupported keys: {', '.join(unknown_keys)}")

    defaults = _validate_defaults(raw_config.get("defaults") or {}, config_path)
    profiles = _validate_profiles(raw_config.get("profiles") or {}, config_path)
    return {
        "defaults": defaults,
        "profiles": profiles,
    }


def list_profiles(config_path):
    """Return validated profile summaries in display order."""
    config = load_profile_config(config_path)
    profiles = []
    for name in sorted(config["profiles"]):
        profile = config["profiles"][name]
        profiles.append({
            "name": name,
            "description": profile.get("description", ""),
            "agent_command": profile["agent_command"],
            "agent_workspace": profile.get("agent_workspace"),
            "tags": profile.get("tags", []),
        })
    return profiles


def resolve_profile(config_path, profile_name):
    """Resolve one named profile into effective run settings."""
    config = load_profile_config(config_path)
    profiles = config["profiles"]
    if not profiles:
        raise ValueError(
            f"No profiles configured in {config_path}. Define a 'profiles' object in .dataiku-agent-suite.json."
        )

    if profile_name not in profiles:
        available = ", ".join(sorted(profiles)) or "(none)"
        raise ValueError(f"Unknown profile '{profile_name}'. Available profiles: {available}")

    defaults = config["defaults"]
    profile = profiles[profile_name]
    env = dict(defaults.get("env") or {})
    env.update(profile.get("env") or {})

    return {
        "profile_name": profile_name,
        "agent_command": profile["agent_command"],
        "agent_workspace": profile.get("agent_workspace"),
        "artifacts_dir": defaults.get("artifacts_dir"),
        "agent_timeout_seconds": defaults.get("agent_timeout_seconds", 900),
        "keep": defaults.get("keep", False),
        "verbose": defaults.get("verbose", False),
        "env": _expand_env_map(env, config_path),
        "description": profile.get("description", ""),
        "tags": list(profile.get("tags") or []),
    }


def _validate_defaults(raw_defaults, config_path):
    if not isinstance(raw_defaults, dict):
        raise ValueError(f"{config_path}: 'defaults' must be an object")

    unknown_keys = sorted(set(raw_defaults) - {"artifacts_dir", "agent_timeout_seconds", "keep", "verbose", "env"})
    if unknown_keys:
        raise ValueError(f"{config_path}: unsupported defaults keys: {', '.join(unknown_keys)}")

    defaults = {}
    if "artifacts_dir" in raw_defaults:
        defaults["artifacts_dir"] = _resolve_path(raw_defaults["artifacts_dir"], config_path, "defaults.artifacts_dir")
    if "agent_timeout_seconds" in raw_defaults:
        defaults["agent_timeout_seconds"] = _require_positive_int(
            raw_defaults["agent_timeout_seconds"],
            config_path,
            "defaults.agent_timeout_seconds",
        )
    if "keep" in raw_defaults:
        defaults["keep"] = _require_bool(raw_defaults["keep"], config_path, "defaults.keep")
    if "verbose" in raw_defaults:
        defaults["verbose"] = _require_bool(raw_defaults["verbose"], config_path, "defaults.verbose")
    if "env" in raw_defaults:
        defaults["env"] = _require_string_map(raw_defaults["env"], config_path, "defaults.env")

    return defaults


def _validate_profiles(raw_profiles, config_path):
    if not isinstance(raw_profiles, dict):
        raise ValueError(f"{config_path}: 'profiles' must be an object")

    profiles = {}
    for name, raw_profile in raw_profiles.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{config_path}: profile names must be non-empty strings")
        profiles[name] = _validate_profile(name, raw_profile, config_path)
    return profiles


def _validate_profile(name, raw_profile, config_path):
    if not isinstance(raw_profile, dict):
        raise ValueError(f"{config_path}: profiles.{name} must be an object")

    unknown_keys = sorted(set(raw_profile) - {"description", "agent_command", "agent_workspace", "env", "tags"})
    if unknown_keys:
        raise ValueError(f"{config_path}: profiles.{name} has unsupported keys: {', '.join(unknown_keys)}")

    if "agent_command" not in raw_profile:
        raise ValueError(f"{config_path}: profiles.{name}.agent_command is required")

    profile = {
        "agent_command": _require_string(raw_profile["agent_command"], config_path, f"profiles.{name}.agent_command"),
    }

    if "description" in raw_profile:
        profile["description"] = _require_string(raw_profile["description"], config_path, f"profiles.{name}.description")
    if "agent_workspace" in raw_profile:
        profile["agent_workspace"] = _require_directory_path(
            raw_profile["agent_workspace"],
            config_path,
            f"profiles.{name}.agent_workspace",
        )
    if "env" in raw_profile:
        profile["env"] = _require_string_map(raw_profile["env"], config_path, f"profiles.{name}.env")
    if "tags" in raw_profile:
        profile["tags"] = _require_string_list(raw_profile["tags"], config_path, f"profiles.{name}.tags")

    return profile


def _expand_env_map(env_map, config_path):
    expanded = {}
    for key, value in env_map.items():
        expanded[key] = _expand_placeholders(value, config_path, f"env.{key}")
    return expanded


def _expand_placeholders(value, config_path, field_name):
    def replace(match):
        env_name = match.group(1)
        if env_name not in os.environ:
            raise ValueError(
                f"{config_path}: '{field_name}' references environment variable '{env_name}' which is not set"
            )
        return os.environ[env_name]

    return ENV_VAR_PATTERN.sub(replace, value)


def _require_string(value, config_path, field_name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{config_path}: '{field_name}' must be a non-empty string")
    return value


def _require_bool(value, config_path, field_name):
    if not isinstance(value, bool):
        raise ValueError(f"{config_path}: '{field_name}' must be true or false")
    return value


def _require_positive_int(value, config_path, field_name):
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"{config_path}: '{field_name}' must be a positive integer")
    return value


def _resolve_path(value, config_path, field_name):
    raw_path = _require_string(value, config_path, field_name)
    return (config_path.parent / raw_path).resolve()


def _require_directory_path(value, config_path, field_name):
    raw_path = _require_string(value, config_path, field_name)
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        raise ValueError(f"{config_path}: '{field_name}' must be an absolute directory path")
    if not path.exists():
        raise ValueError(f"{config_path}: '{field_name}' does not exist: {path}")
    if not path.is_dir():
        raise ValueError(f"{config_path}: '{field_name}' must be a directory: {path}")
    return path.resolve()


def _require_string_map(value, config_path, field_name):
    if not isinstance(value, dict):
        raise ValueError(f"{config_path}: '{field_name}' must be an object")

    result = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"{config_path}: '{field_name}' keys must be non-empty strings")
        result[key] = _require_string(item, config_path, f"{field_name}.{key}")
    return result


def _require_string_list(value, config_path, field_name):
    if not isinstance(value, list):
        raise ValueError(f"{config_path}: '{field_name}' must be a list")

    result = []
    for index, item in enumerate(value):
        result.append(_require_string(item, config_path, f"{field_name}[{index}]"))
    return result
