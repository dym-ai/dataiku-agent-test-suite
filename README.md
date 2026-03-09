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
- You have Python with `dataikuapi` installed.
- You have exported `DATAIKU_URL` and `DATAIKU_API_KEY`.
- Your Dataiku API key can create and delete projects.
- By default, local `input_data` is uploaded using the DSS connection `filesystem_managed`.
- Built-in cases use local input data CSVs and do not require a pre-existing DSS source project.
- Custom cases can still copy from an existing DSS `source_project` if you prefer that mode.
- Optional: set `DATAIKU_SSL_VERIFY=true|false|/path/to/ca-bundle.pem` if you need explicit TLS verification control.
- Optional: set `DATAIKU_INPUT_DATA_CONNECTION` if you need local `input_data` uploaded to a different DSS connection.

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
  --workspace /path/to/your/agent-workspace
```

Show transcript excerpts in the terminal report:

```bash
python run_test.py dates --agent codex --verbose
```

Write the full request/response/report/transcript bundle to disk:

```bash
python run_test.py dates \
  --agent codex \
  --agent-timeout-seconds 600 \
  --artifacts-dir /path/to/output-artifacts
```

## Layout

- `cases/<case_name>/case.json`: case definition
- `cases/<case_name>/input_data/*`: local input datasets for that case
- `evals/__init__.py`: setup, validate, teardown, and evaluator loading
- `evals/builtins.py`: built-in evaluators you can reuse or copy
- `agents/*.py`: bundled agent scripts for common CLIs
- `suite/*.py`: shared protocol, prompt, and report helpers
- `run_test.py`: main CLI entrypoint

## How A Run Works

Each run has three phases.

1. `setup()` creates a clean Dataiku project and prepares the source datasets listed by the case.
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

Use `--agent-timeout-seconds` to cap how long the harness waits for the agent process before marking the run as aborted.

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
  "project_key": "BOBTEST_DATES_1772835245_AB12CD34",
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

Notes on stats:

- `duration_ms`, `total_tokens`, and `tool_uses` are optional
- For arbitrary external agents, `tool_uses` is most reliable when the agent writes it directly into `response.stats`
- The bundled wrappers also attempt best-effort extraction from CLI output when possible

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

Create a new case directory in `cases/` with a `case.json` file.

Example:

```json
{
  "name": "my_case",
  "description": "What this case validates.",
  "prompt": "The natural language task to give the agent...",
  "sources": ["Source_Dataset_Name"],
  "input_data": {
    "Source_Dataset_Name": {
      "path": "input_data/Source_Dataset_Name.csv"
    }
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
      "name": "flow_shape_match",
      "nodes": {
        "source": {
          "schema": [
            {"name": "raw_date", "type": "string"}
          ]
        },
        "final": {
          "schema": [
            {"name": "column_name", "type": "bigint"}
          ]
        }
      },
      "recipes": [
        {"type": "shaker", "inputs": ["source"], "outputs": ["final"]}
      ]
    },
    {
      "name": "recipe_config_match",
      "mode": "raw",
      "compare": "subset",
      "nodes": {
        "source": {
          "schema": [
            {"name": "raw_date", "type": "string"}
          ]
        },
        "final": {
          "schema": [
            {"name": "column_name", "type": "bigint"}
          ]
        }
      },
      "recipes": [
        {
          "type": "shaker",
          "inputs": ["source"],
          "outputs": ["final"],
          "config": {
            "payload": {
              "steps": []
            }
          }
        }
      ]
    }
  ]
}
```

Key fields:

- `input_data`: optional map of source dataset names to local input data files stored with the case
  Paths are resolved relative to the case file directory.
- `source_project`: optional Dataiku project containing source datasets to copy from when input data is not provided
- `prompt`: the task the agent sees
- `sources`: datasets created or copied into the generated project before the agent runs
- `expected_outputs`: final datasets used by the default `output_datasets` evaluator
- `evals`: optional evaluator list; if omitted, the harness runs the default `output_datasets` evaluator only

Built-in evaluator names:

- `output_datasets`: validates dataset existence, schema, row counts, and sampled values
- `flow_shape_match`: compares an anonymous flow graph using dataset schemas, recipe types, and recipe connectivity
- `recipe_config_match`: compares recipe payload/params for matched recipes in an anonymous flow graph
- `recipe_type_counts`: checks exact recipe counts by type
- `forbid_recipe_types`: fails if forbidden recipe types are present

Case validation:

- The harness validates case files before setup starts
- Base case fields are always required: `name`, `description`, `prompt`, `sources`
- Each source dataset must be backed by either an `input_data` entry or a `source_project`
- Each configured evaluator also validates its own spec and fails early with a targeted error if required fields are missing

Anonymous flow graph format:

- `nodes`: a map of user-defined aliases to dataset schemas
- `recipes`: a list of recipe specs using those aliases in `inputs` and `outputs`
- Alias names are only placeholders inside the test case; they are not compared to actual DSS dataset names

`recipe_config_match` options:

- `mode`: `raw` or `normalized`
- `compare`: `subset` or `exact`
- `config`: expected recipe config fragment shaped like `{"payload": ..., "params": ...}`
- In `subset` mode, dicts are matched by key subset and lists are matched by ordered prefix

`output_datasets` options:

- `sample_mode`: `unordered` (default), `ordered`, or `by_key`
- `key_columns`: required when `sample_mode` is `by_key`
- `ordered` compares sample rows against the first `N` output rows by position
- `unordered` checks that each expected sample row appears somewhere in the dataset, regardless of order
- `by_key` matches expected sample rows to actual rows using the provided key columns

Custom evaluators:

- Use `module_name:function_name` in `evals[].name`
- The function should accept `(client, project_key, case, spec)` and return a list of check dicts
- A custom evaluator can optionally expose a callable `validate_spec(spec, case)` attribute for early validation
- This lets you add local Python evaluators without changing the harness core

Then run it:

```bash
python run_test.py my_case --agent codex --keep
```
