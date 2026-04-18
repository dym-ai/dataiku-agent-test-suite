import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from suite.profiles import list_profiles, load_profile_config, resolve_profile


class ProfileConfigTests(unittest.TestCase):
    def test_loads_defaults_and_profiles(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            config_path = root / ".dataiku-agent-suite.json"
            config_path.write_text(
                json.dumps(
                    {
                        "defaults": {
                            "artifacts_dir": "./artifacts",
                            "agent_timeout_seconds": 1200,
                            "keep": True,
                            "verbose": True,
                        },
                        "profiles": {
                            "codex-vanilla": {
                                "description": "Vanilla Codex",
                                "agent_command": "codex",
                                "tags": ["codex", "vanilla"],
                            },
                            "repo-codex": {
                                "agent_command": "codex",
                                "agent_workspace": str(workspace),
                            },
                        },
                    }
                )
            )

            config = load_profile_config(config_path)

            self.assertEqual(config["defaults"]["agent_timeout_seconds"], 1200)
            self.assertEqual(config["defaults"]["artifacts_dir"], (root / "artifacts").resolve())
            self.assertEqual(sorted(config["profiles"]), ["codex-vanilla", "repo-codex"])
            self.assertEqual(config["profiles"]["repo-codex"]["agent_workspace"], workspace.resolve())

    def test_resolve_profile_applies_defaults_and_env_expansion(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / ".dataiku-agent-suite.json"
            config_path.write_text(
                json.dumps(
                    {
                        "defaults": {
                            "artifacts_dir": "./artifacts",
                            "agent_timeout_seconds": 900,
                            "env": {
                                "DATAIKU_URL": "${DATAIKU_URL}",
                                "DATAIKU_API_KEY": "${DATAIKU_API_KEY}",
                            },
                        },
                        "profiles": {
                            "codex-vanilla": {
                                "agent_command": "codex",
                                "env": {
                                    "EXTRA_FLAG": "enabled",
                                },
                            }
                        },
                    }
                )
            )

            with patch.dict(os.environ, {"DATAIKU_URL": "http://example", "DATAIKU_API_KEY": "secret"}, clear=False):
                resolved = resolve_profile(config_path, "codex-vanilla")

            self.assertEqual(resolved["agent_command"], "codex")
            self.assertEqual(resolved["artifacts_dir"], (root / "artifacts").resolve())
            self.assertEqual(resolved["agent_timeout_seconds"], 900)
            self.assertEqual(
                resolved["env"],
                {
                    "DATAIKU_URL": "http://example",
                    "DATAIKU_API_KEY": "secret",
                    "EXTRA_FLAG": "enabled",
                },
            )

    def test_list_profiles_returns_display_summaries(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / ".dataiku-agent-suite.json"
            config_path.write_text(
                json.dumps(
                    {
                        "profiles": {
                            "b-profile": {"agent_command": "b-agent", "description": "B"},
                            "a-profile": {"agent_command": "a-agent", "description": "A"},
                        }
                    }
                )
            )

            profiles = list_profiles(config_path)

            self.assertEqual([profile["name"] for profile in profiles], ["a-profile", "b-profile"])

    def test_requires_existing_named_profile(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / ".dataiku-agent-suite.json"
            config_path.write_text(json.dumps({"profiles": {"codex": {"agent_command": "codex"}}}))

            with self.assertRaisesRegex(ValueError, "Unknown profile 'missing'"):
                resolve_profile(config_path, "missing")

    def test_requires_environment_variables_for_placeholders(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / ".dataiku-agent-suite.json"
            config_path.write_text(
                json.dumps(
                    {
                        "defaults": {"env": {"DATAIKU_URL": "${DATAIKU_URL}"}},
                        "profiles": {"codex": {"agent_command": "codex"}},
                    }
                )
            )

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ValueError, "DATAIKU_URL"):
                    resolve_profile(config_path, "codex")

    def test_rejects_relative_agent_workspace_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / ".dataiku-agent-suite.json"
            config_path.write_text(
                json.dumps(
                    {
                        "profiles": {
                            "codex": {
                                "agent_command": "codex",
                                "agent_workspace": "./workspace",
                            }
                        }
                    }
                )
            )

            with self.assertRaisesRegex(ValueError, "must be an absolute directory path"):
                load_profile_config(config_path)


if __name__ == "__main__":
    unittest.main()
