# Dataiku Agent Test Suite

This repository lets you test whether an AI agent can complete a Dataiku task successfully.

You give the harness a test case and an agent command. It creates a fresh Dataiku project, gives the task to the agent, and checks whether the final result matches the case.

The agent being tested does not need to live in this repo. It can be Codex, Claude Code, or any other command-line agent that can read a request file and write a response file.

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

If you use `--artifacts-dir`, the harness also writes the full request, agent response, validation result, and report to disk for later inspection.

<details>
<summary>Example terminal report</summary>

```text
Case: dates
Project: BOBTEST_DATES_1772835245_A1B2C3D4
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
- A working agent CLI, or a custom agent command

Optional:

- `DATAIKU_SSL_VERIFY=true|false|/path/to/ca-bundle.pem` if you need explicit TLS verification control

## Quick Start

The basic command is:

```bash
python run_test.py <case_name> --agent "<agent command>"
```

Example with the built-in `dates` case and the bundled Codex wrapper:

```bash
python run_test.py dates --agent codex
```

Common add-ons:

- `--keep` to keep the generated DSS project so you can inspect it
- `--verbose` to show agent stdout and stderr excerpts in the report
- `--artifacts-dir /path/to/output-artifacts` to write the full run bundle to disk
- `--workspace /path/to/agent-workspace` to tell the agent which local folder it may use

Keep the generated DSS project after validation:

```bash
python run_test.py dates --agent codex --keep
```

Run the agent from another workspace:

```bash
python run_test.py dates \
  --agent codex \
  --workspace /path/to/agent-workspace
```

Write the full run bundle to disk:

```bash
python run_test.py dates \
  --agent codex \
  --artifacts-dir /path/to/output-artifacts
```

Show agent stdout/stderr excerpts in the terminal report:

```bash
python run_test.py dates --agent codex --verbose
```

Use a custom agent script:

```bash
python run_test.py dates --agent "python /path/to/my_agent.py"
```

## How A Run Works

Each run has three stages:

1. `setup()` checks the case definition, creates a new DSS project, and copies the source datasets into it.
2. The harness runs your agent command with `--request <path>` and `--response <path>`.
3. `validate()` checks the finished DSS project against the case's validation rules.

If `--keep` is not set, the harness deletes the generated project at the end.

By default, the harness keeps validation simple and focuses on the final output datasets:

- required output datasets exist
- schemas match
- row counts match
- sampled values match

Cases can also use stricter checks when you want to judge the flow shape, recipe counts, or recipe configuration.

## Reports And Artifacts

The terminal report includes:

- case name and generated project key
- agent status
- overall pass/fail result
- per-check validation results
- agent stats when available
- a short agent summary

With `--artifacts-dir`, each run writes a subdirectory named after the generated project key containing:

- `request.json`
- `agent_response.json`
- `validation_result.json`
- `report.txt`
- `agent_stdout.txt`
- `agent_stderr.txt`

If `--keep` is also set, the report includes the DSS project URL.

## CLI Flags

`run_test.py` is the main entrypoint.

Supported flags:

- `--agent`: required; either `codex`, `claude`, or a custom command string
- `--keep`: keep the generated DSS project after validation
- `--workspace`: folder path to include in the agent request; defaults to the current directory
- `--verbose`: include agent stdout and stderr excerpts in the terminal report
- `--artifacts-dir`: write request/response/report files to disk
- `--agent-timeout-seconds`: abort the agent process after a timeout; default `900`

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
2. Point `--agent` at a built-in wrapper or your own CLI command.
3. Let the harness create a fresh DSS project and run the agent.
4. Read the terminal report, or inspect the artifact bundle and kept project.
