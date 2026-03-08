# Dataiku Agent Test Suite

This repository is a small CLI-first harness for running a Dataiku task against an agent and checking whether the final output is correct.

At a high level, the harness does four things:

1. Creates a fresh Dataiku project for the case.
2. Copies the source datasets into that project.
3. Runs your agent through a simple CLI request/response protocol.
4. Validates the finished project against the case definition.

The agent can be Codex, Claude Code, or any other CLI-driven system that can read a request JSON and write a response JSON.

## Assumptions

To run a case successfully, this README assumes:

- You already have a compatible agent CLI installed and working.
- You have a running Dataiku DSS instance.
- The source project referenced by the case exists on that instance.
- The source datasets in that project already contain data.
- You have Python with `dataikuapi` installed.
- You have exported `DATAIKU_URL` and `DATAIKU_API_KEY`.
- Your Dataiku API key can create and delete projects.
- Optional: set `DATAIKU_SSL_VERIFY=true|false|/path/to/ca-bundle.pem` if you need explicit TLS verification control.

## Quick Start

The generic command shape is:

```bash
python run_test.py <case_name> --agent "<your agent command>"
```

Assuming you are using Codex, the fastest way to run the built-in `dates` case is:

```bash
python run_test.py dates --agent codex
```

Keep the generated Dataiku project after validation:

```bash
python run_test.py dates --agent codex --keep
```

Run Codex from another workspace:

```bash
python run_test.py dates \
  --agent codex \
  --workspace /Users/dmitriryssev/Documents/GitHub/dataiku-agent-dev-kit
```

Show transcript excerpts in the terminal report:

```bash
python run_test.py dates --agent codex --verbose
```

Write the full request/response/report/transcript bundle to disk:

```bash
python run_test.py dates \
  --agent codex \
  --artifacts-dir /tmp/dataiku-agent-runs
```

## Layout

- `cases/*.json`: case definitions
- `evals/__init__.py`: setup, validate, teardown, and evaluator loading
- `evals/builtins.py`: built-in evaluators you can reuse or copy
- `agents/*.py`: bundled agent scripts for common CLIs
- `suite/*.py`: shared protocol, prompt, and report helpers
- `run_test.py`: main CLI entrypoint

## How A Run Works

Each run has three phases.

1. `setup()` creates a clean Dataiku project and copies the source datasets listed by the case.
2. The harness runs your agent command with a request JSON and waits for a response JSON.
3. `validate()` inspects the resulting Dataiku project and checks the output datasets.

By default, validation is intentionally minimal and focuses on final output datasets:

- expected output datasets should exist
- schemas should match
- row counts should match
- sampled data values should match

Cases can opt into additional built-in evaluators or custom evaluators if they want to test workflow choices, policy rules, recipe counts, or other project-level behavior.

## Running A Custom Agent

Your agent is just a CLI command.

The harness invokes it by appending:

```bash
--request /tmp/request.json --response /tmp/response.json
```

So if you run:

```bash
python run_test.py dates --agent "python /path/to/my_agent.py"
```

the harness will invoke:

```bash
python /path/to/my_agent.py --request /tmp/request.json --response /tmp/response.json
```

`--workspace` is not passed on the command line. Instead, the workspace path is included in the request JSON. Your agent can use it as its working directory if that is helpful.

The bundled scripts live in:

- `agents/codex.py`
- `agents/claude.py`

Those scripts work out of the box if the underlying `codex` or `claude` CLI is already installed.

## Agent Script Contract

Your agent command should:

1. Accept `--request <path>` and `--response <path>`.
2. Read the request JSON from disk.
3. Perform the task in the target Dataiku project.
4. Write a response JSON to the response path.

The harness owns setup, validation, reporting, cleanup, and artifact writing. The agent only needs to do the work required by the prompt.

## Request JSON

The request JSON currently looks like this:

```json
{
  "version": 1,
  "case_name": "dates",
  "project_key": "BOBTEST_DATES_1772835245",
  "prompt": "The natural language task...",
  "sources": ["Dates"],
  "workspace": "/path/to/agent/workspace"
}
```

Field meanings:

- `version`: protocol version
- `case_name`: the case being run
- `project_key`: the generated Dataiku project the agent should work in
- `prompt`: the natural-language task
- `sources`: source datasets already present in the generated project
- `workspace`: directory the agent can use for local tooling, scripts, skills, or scaffolding

## Response JSON

Your agent should write a response JSON like this:

```json
{
  "version": 1,
  "status": "completed",
  "summary": "Short human-readable summary",
  "stdout": "Optional agent stdout",
  "stderr": "Optional agent stderr",
  "stats": {
    "duration_ms": 12345,
    "total_tokens": 1234,
    "tool_uses": 10
  }
}
```

Common `status` values:

- `completed`
- `failed`
- `aborted`
- `unsupported`

## CLI Output And Artifacts

By default, the CLI prints a compact report:

- case and project
- pass/fail result
- per-check validation results
- agent stats when available
- short agent summary

Use `--verbose` if you want stdout/stderr excerpts inline in the terminal report.

Use `--artifacts-dir` if you want the full run bundle written to disk. For each run, the harness writes a subdirectory named after the generated project key containing:

- `request.json`
- `agent_response.json`
- `validation_result.json`
- `report.txt`
- `agent_stdout.txt`
- `agent_stderr.txt`

## Adding A New Case

Create a new JSON file in `cases/`.

Example:

```json
{
  "name": "my_case",
  "description": "What this case validates.",
  "prompt": "The natural language task to give the agent...",
  "source_project": "MY_PROJECT",
  "sources": ["Source_Dataset_Name"],
  "source_renames": {
    "Ugly_Long_Dataset_Name": "Clean_Name"
  },
  "expected_outputs": {
    "final_output": {
      "schema": [
        {"name": "column_name", "type": "bigint"}
      ],
      "row_count": 42,
      "data": [
        {"column_name": "expected_value"}
      ]
    }
  },
  "evals": [
    {"name": "output_datasets"},
    {
      "name": "recipe_type_counts",
      "expected": [
        {"type": "shaker", "count": 1},
        {"type": "grouping", "count": 1}
      ]
    },
    {"name": "forbid_recipe_types", "types": ["python"]}
  ]
}
```

Key fields:

- `source_project`: Dataiku project containing the source datasets
- `prompt`: the task the agent sees
- `sources`: datasets copied into the generated project before the agent runs
- `source_renames`: optional source dataset renames for cleaner prompts and flows
- `expected_outputs`: final datasets used by the default `output_datasets` evaluator
- `evals`: optional evaluator list; if omitted, the harness runs the default `output_datasets` evaluator only

Built-in evaluator names:

- `output_datasets`: validates dataset existence, schema, row counts, and sampled values
- `recipe_type_counts`: checks exact recipe counts by type
- `forbid_recipe_types`: fails if forbidden recipe types are present

Custom evaluators:

- Use `module_name:function_name` in `evals[].name`
- The function should accept `(client, project_key, case, spec)` and return a list of check dicts
- This lets you add local Python evaluators without changing the harness core

Then run it:

```bash
python run_test.py my_case --agent codex --keep
```
