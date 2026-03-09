# Dataiku Agent Test Suite

This repository is a CLI-first harness for testing whether an external agent can complete a Dataiku task correctly.

For each run, the harness creates a fresh DSS project, copies in the case's source datasets, runs your agent through a small request/response protocol, and evaluates the resulting project.

The agent being tested does not need to live in this repo. It can be Codex, Claude Code, or any other CLI-driven system that can read a request file and write a response file.

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

Command shape:

```bash
python run_test.py <case_name> --agent "<agent command>"
```

Example with the built-in `dates` case and the bundled Codex wrapper:

```bash
python run_test.py dates --agent codex
```

Common add-ons:

- `--keep` to retain the generated DSS project for inspection
- `--verbose` to include stdout/stderr excerpts in the report
- `--artifacts-dir /path/to/output-artifacts` to write the full run bundle to disk
- `--workspace /path/to/agent-workspace` to tell the agent which local workspace it may use

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

1. `setup()` validates the case, creates a new DSS project, and copies the source datasets into it.
2. The harness runs your agent command with `--request <path>` and `--response <path>`.
3. `validate()` runs the case's evaluator list against the finished DSS project.

If `--keep` is not set, the harness deletes the generated project at the end.

By default, a case uses the `output_datasets` evaluator only. That default path is intentionally minimal and focused on final outputs:

- required output datasets exist
- schemas match
- row counts match
- sampled values match

Cases can opt into stricter or more opinionated evaluators when they want to judge flow shape, recipe counts, or recipe configuration.

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
- `--workspace`: path to include in the agent request JSON; defaults to the current directory
- `--verbose`: include agent stdout/stderr excerpts in the terminal report
- `--artifacts-dir`: write request/response/report files to disk
- `--agent-timeout-seconds`: abort the agent process after a timeout; default `900`

## Reference

Deeper reference material lives here:

- [`docs/agent-contract.md`](docs/agent-contract.md): request/response protocol, custom agent expectations, bundled wrappers
- [`docs/cases-and-evaluators.md`](docs/cases-and-evaluators.md): case format, built-in evaluators, and custom evaluator hooks

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
