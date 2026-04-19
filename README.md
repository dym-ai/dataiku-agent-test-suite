# Dataiku Agent Test Suite

This repository lets you test whether an AI agent can complete a Dataiku task successfully.

You give the harness a test case and a configured profile. It creates a fresh Dataiku project, gives the task to the selected agent setup, and checks whether the final result matches the case.

Your agent does not need to live in this repository. It can be Codex, Claude Code, another CLI agent, or your own wrapper script, as long as it can take a task from the harness and return a result.

## What This Repo Does

For each run, the harness:

1. Creates a new temporary project in Dataiku DSS.
2. Copies in the source datasets needed for the test case.
3. Runs your agent on the task.
4. Checks the finished project against the case definition.

If the checks pass, the run passes. If they fail, the report shows what did not match.

### What You Get Back

A typical successful run gives you a short terminal report with:

- **Case information**: the case name and generated Dataiku project
- **Agent outcome**: whether the agent finished successfully
- **Pass/fail result**: whether the run passed overall
- **Check results**: which validations passed or failed
- **Agent summary**: a short human-readable summary from the agent

If you use `--artifacts-dir`, the harness also writes a self-contained run bundle to disk for later inspection. Persisted agent output is sanitized to redact secrets before it is written.

<details>
<summary>Example terminal report</summary>

```text
Case: dates
Project: COBUILD_DATES_1772835245_A1B2C3D4
Agent: completed
Result: PASS

Checks
- agent_returncode(expected 0, actual 0): PASS
- agent_status(expected completed, actual completed): PASS
- exists(Dates_with_expiration): PASS
- schema_columns(Dates_with_expiration): PASS
- schema_types(Dates_with_expiration): PASS
- row_count(Dates_with_expiration, expected 1016, actual 1016): PASS
```

</details>

## Prerequisites

You need:

- Python with `dataikuapi` installed
- A running Dataiku DSS instance
- `DATAIKU_URL` and `DATAIKU_API_KEY` exported
- An API key that can create and delete DSS projects
- A source project on that DSS instance matching the case definition
- Source datasets in that project that already contain data
- A working agent CLI, or a custom agent command referenced by one of your profiles

Optional:

- `DATAIKU_SSL_VERIFY=true|false|/path/to/ca-bundle.pem` if you need explicit TLS verification control

## Quick Start

The basic command is:

```bash
python run_test.py run <case_name> --profile <profile_name>
```

If you prefer not to repeat the same flags every time, you can start from [`.dataiku-agent-suite.example.json`](.dataiku-agent-suite.example.json), create a local `.dataiku-agent-suite.json`, and then run:

```bash
python run_test.py run <case_name> --profile codex-vanilla
```

Example with the built-in `dates` case and the bundled Codex wrapper:

```bash
python run_test.py run dates --profile codex-vanilla
```

Example config:

```json
{
  "defaults": {
    "artifacts_dir": "./artifacts",
    "agent_timeout_seconds": 900,
    "env": {
      "DATAIKU_URL": "${DATAIKU_URL}",
      "DATAIKU_API_KEY": "${DATAIKU_API_KEY}"
    }
  },
  "profiles": {
    "codex-vanilla": {
      "agent_command": "codex"
    },
    "repo-codex": {
      "agent_command": "codex",
      "agent_workspace": "/path/to/your-agent-repo"
    }
  }
}
```

With `.dataiku-agent-suite.json` in the repository root, the command becomes:

```bash
python run_test.py run dates --profile repo-codex
```

Profiles define which agent command to run and, optionally, which external workspace that profile should use.

For real use, it is strongly recommended to point `agent_workspace` at your own agent repository when you want the agent to work from a repo with tools, skills, and scripts.

If you do not set `agent_workspace`, the harness creates a fresh empty temporary workspace for each run so the agent does not get access to this harness repo by default.

If you do set `agent_workspace`, the harness now treats it as a source workspace. For each run, it copies that directory into a temporary isolated run workspace and executes the agent in the copy. The source workspace is not used in place.

Avoid pointing `agent_workspace` at this harness repo, because that can expose case definitions and evaluator logic to the agent.

`agent_command` can point to the bundled shortcuts (`codex`, `claude`) or to your own command, such as:

```json
{
  "profiles": {
    "custom-agent": {
      "agent_command": "python /path/to/my_agent.py"
    }
  }
}
```

Command-line flags still override config values when you need a one-off change.

Common add-ons:

- `--keep` to keep the generated DSS project so you can inspect it
- `--verbose` to show agent stdout and stderr excerpts in the report
- `--artifacts-dir /path/to/output-artifacts` to write the full run bundle to disk

Keep the generated DSS project after validation:

```bash
python run_test.py run dates --profile codex-vanilla --keep
```

That source workspace is copied into a temporary run workspace for the duration of the run and then discarded after completion.

Write the full run bundle to disk:

```bash
python run_test.py run dates \
  --profile codex-vanilla \
  --artifacts-dir /path/to/output-artifacts
```

Show agent stdout/stderr excerpts in the terminal report:

```bash
python run_test.py run dates --profile codex-vanilla --verbose
```

Use a custom agent script or wrapper:

```bash
python run_test.py run dates --profile custom-agent
```

See what is available before you run anything:

```bash
python run_test.py list-cases
python run_test.py describe-case dates
python run_test.py list-profiles
```

## How A Run Works

Each run has three stages:

1. `setup()` checks the case definition, creates a new DSS project, and copies the source datasets into it.
2. The harness runs the selected profile's agent command with `--request <path>` and `--response <path>`.
3. `validate()` checks the finished DSS project against the case's validation rules.

If `--keep` is not set, the harness deletes the generated project at the end.

By default, the harness keeps validation simple and focuses on the final output datasets:

- required output datasets exist
- schemas match
- row counts match
- sampled values match

### Checking tool and skill usage

You can assert that an agent used specific MCP tools or skills by adding evaluators to your case. 
`skills_used` relies on `Skill` tool calls appearing in the agent's trace. The
bundled Claude wrapper can emit these calls; the bundled Codex wrapper does not,
so `skills_used` will be skipped rather than fail when no `Skill` calls are
present.

For example, to verify that an agent used the right skills and tools for the `dates` case, add this to the case.json. This assumes that you named your MCP server "dataiku-mcp" in your config:

```json
"evals": [
  {"name": "output_datasets"},
  {
    "name": "tool_calls_include",
    "tools": [
      "mcp__dataiku-mcp__create_recipe",
      "mcp__dataiku-mcp__get_recipe_settings",
      "mcp__dataiku-mcp__set_recipe_settings"
    ]
  },
  {
    "name": "skills_used",
    "skills": [
      "recipes/SKILL.md",
      "recipes/recipe-types/prepare/skill.md"
    ]
  }
]
```

- `tool_calls_include` passes if every listed tool was called at least once.
- `tool_calls_exclude` passes if none of the listed tools were called.
- `skills_used` passes if every listed skill was invoked via the `Skill` tool.
  If no `Skill` tool calls are present in the trace, the check is skipped.

The tool name format is `mcp__{server}__{tool}`. Both bundled wrappers emit a `tool_trace` automatically. For cross-agent compatibility, make sure the MCP server is registered under the same name in both agents (e.g. `dataiku-mcp`).

## Running Tests

The repository test suite currently uses Python's built-in `unittest` runner:

```bash
python -m unittest discover -s tests -v
```

## Reports And Artifacts

The terminal report includes:

- case name and generated project key
- agent status
- overall pass/fail result
- per-check validation results
- agent stats when available
- a short agent summary

With `--artifacts-dir`, each run writes a dedicated run bundle containing:

- `request.json`
- `agent_response.json`
- `validation_result.json`
- `run_manifest.json`
- `report.txt`
- `agent_stdout.txt`
- `agent_stderr.txt`

The run manifest records the stable run metadata:

- run id and timestamps
- case name and case file path
- profile name and profile digest
- DSS instance URL
- source workspace and staged run workspace
- project key and whether the DSS project was kept
- execution summary such as status, return code, timeout, duration, tokens, and tool use
- validation summary such as check counts and overall evaluator pass/fail

The persisted `validation_result.json` contains evaluator output only. Basic harness execution checks such as agent status and return code are summarized separately in `run_manifest.json`.

Persisted agent output and verbose report excerpts are sanitized to redact exact environment secret values and common auth patterns such as bearer tokens and `*_api_key` fields.

If `--keep` is also set, the report includes the DSS project URL.

## CLI Flags

`run_test.py` is the main entrypoint.

Supported flags:

- `list-cases`: show available cases and exit
- `describe-case <case>`: show the details of one case and exit
- `list-profiles`: show configured profiles and exit
- `run <case> --profile <name>`: run one case against one profile
- `run ... --keep` / `--no-keep`: keep or discard the generated DSS project after validation
- `run ... --verbose` / `--no-verbose`: include or suppress agent stdout and stderr excerpts in the terminal report
- `run ... --artifacts-dir`: write request/response/report files to disk
- `run ... --agent-timeout-seconds`: abort the agent process after a timeout; default `900`

## Reference

Deeper reference material lives here:

- [`docs/agent-contract.md`](docs/agent-contract.md): how the harness talks to agents, plus the bundled wrappers
- [`docs/cases-and-evaluators.md`](docs/cases-and-evaluators.md): how to write cases and how the built-in checks work

## Repository Layout

- `run_test.py`: main CLI entrypoint
- `cases/*.json`: case definitions
- `docs/*.md`: protocol and case-authoring reference
- `evals/__init__.py`: setup, validation, teardown, and evaluator loading
- `evals/builtins.py`: built-in evaluators and their spec validators
- `agents/*.py`: bundled agent wrappers
- `suite/*.py`: request/response, prompting, stats, and report helpers

## Typical Usage Pattern

1. Pick a case from `cases/` or add a new one.
2. Define a profile in `.dataiku-agent-suite.json` that points at a built-in wrapper or your own CLI command.
3. Let the harness create a fresh DSS project and run the agent.
4. Read the terminal report, or inspect the artifact bundle and kept project.
