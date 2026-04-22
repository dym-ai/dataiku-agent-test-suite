# Dataiku Agent Test Suite

This repository is a benchmark harness for testing whether an AI agent or agentic system can complete Dataiku tasks successfully.

The harness is not the agent under test. You point it at:

- a `case`: the task and expected outcome
- a `profile`: the agent command and optional external workspace to benchmark

The harness then creates a fresh DSS project, runs the agent, validates the result, and writes reports and artifacts.

## What It Is

Use this repo when you want to answer questions like:

- can this agent build the expected Dataiku flow?
- does one setup perform better than another on the same case?
- which profiles pass or fail across a small benchmark set?

The harness stays neutral about how your agent is implemented. Your agent can live outside this repo and can be:

- the bundled `codex` or `claude` wrappers
- your own CLI wrapper
- a repo-backed agent setup with tools, MCP servers, skills, or scripts

## How It Works

For each `run`, the harness:

1. Validates the selected case.
2. Creates a fresh DSS project and copies the required source datasets into it.
3. Stages a fresh run workspace:
   - empty if the profile has no `agent_workspace`
   - copied from the profile’s source workspace if `agent_workspace` is configured
4. Invokes the agent through the file-based request/response contract.
5. Validates the finished DSS project with the case’s evaluators.
6. Prints a report and optionally writes artifacts.

The main execution shapes are:

- `run`: one case against one profile
- `batch`: multiple runs across a case/profile matrix
- `compare`: artifact-based comparison of saved run bundles or batch directories

## Getting Started

### 1. Set up the environment

You need:

- `uv`
- a running Dataiku DSS instance
- `DATAIKU_URL` and `DATAIKU_API_KEY` exported
- an API key that can create and delete DSS projects
- a source DSS project and datasets that match the selected case
- an agent CLI or wrapper command to benchmark

Built-in cases assume the required source datasets already exist in DSS.

From the repo root, install the harness dependencies:

```bash
uv sync
```

Optional:

- `DATAIKU_SSL_VERIFY=true|false|/path/to/ca-bundle.pem`

### 2. Create a local profile config

Create a local `.dataiku-agent-suite.json` in the repo root:

```bash
cp .dataiku-agent-suite.example.json .dataiku-agent-suite.json
```

Then edit it to define the profiles you want to benchmark.

Each profile defines one setup to benchmark, such as a plain agent command or a repo-backed agent workspace.

Minimal example:

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

Notes:

- `agent_command` is the command the harness launches.
- `agent_workspace` is optional.
- If `agent_workspace` is set, the harness copies it into a temporary isolated run workspace for each run.

### 3. Inspect available cases and profiles

```bash
uv run python run_test.py list-cases
uv run python run_test.py describe-case dates
uv run python run_test.py list-profiles
```

### 4. Run one case

```bash
uv run python run_test.py run dates --profile codex-vanilla
```

A successful `run` creates a fresh DSS project, executes the selected profile against the case, validates the result, and prints a report.

Keep the generated DSS project so you can inspect it afterward:

```bash
uv run python run_test.py run dates --profile repo-codex --keep
```

Show agent stdout/stderr excerpts in the terminal report:

```bash
uv run python run_test.py run dates --profile codex-vanilla --verbose
```

Write the full run bundle to disk:

```bash
uv run python run_test.py run dates --profile codex-vanilla --artifacts-dir ./artifacts
```

### 5. Run a small batch

```bash
uv run python run_test.py batch --cases dates crane --profiles codex-vanilla repo-codex
```

Run more than one batch child at a time:

```bash
uv run python run_test.py batch --cases dates crane --profiles codex-vanilla repo-codex --max-parallel 2
```

`batch` orchestrates multiple normal runs. It writes one batch directory with nested child run bundles when artifacts are enabled. By default it runs sequentially; `--max-parallel` enables bounded parallelism.

### 6. Compare saved artifacts

```bash
uv run python run_test.py compare /path/to/run-a /path/to/run-b
uv run python run_test.py compare /path/to/batch__2026-04-20T...
```

`compare` reads saved artifact directories from earlier runs or batches. It does not rerun anything. In v1 it requires at least 2 run bundles and all selected runs must be from the same case.

## Reports And Artifacts

When artifact writing is enabled, the harness writes:

- run bundles containing:
  - `request.json`
  - `agent_response.json`
  - `validation_result.json`
  - `run_manifest.json`
  - `report.txt`
  - `agent_stdout.txt`
  - `agent_stderr.txt`
- batch bundles containing:
  - `batch_manifest.json`
  - `report.txt`
  - `runs/` with child run bundles
- single-case batch compare outputs:
  - `compare_summary.json`
  - `compare_report.txt`

The key separation is:

- `validation_result.json`: evaluator output only
- `agent_response.json`: sanitized agent-side response
- `run_manifest.json`: run metadata plus execution and validation summaries

Persisted agent output is sanitized to redact exact secret values and common auth patterns.

## Customizing The Harness

The built-in cases and evaluators are examples, not the limit of the harness.

- Add your own benchmark scenarios under `cases/`.
- Define the expected outcome for each scenario through built-in or custom evaluators.
- Keep scenario-specific judgment in evaluators rather than hard-coding it into the harness.

See [docs/cases-and-evaluators.md](docs/cases-and-evaluators.md) for case authoring and evaluator details.

## More Detail

Detailed reference material lives in `docs/`:

- [docs/agent-contract.md](docs/agent-contract.md): request/response protocol, bundled wrappers, and workspace behavior
- [docs/cases-and-evaluators.md](docs/cases-and-evaluators.md): case authoring, built-in evaluators, and custom evaluators

## Repository Layout

- `run_test.py`: main CLI entrypoint
- `cases/`: case definitions
- `agents/`: bundled agent wrappers
- `evals/`: setup, validation, teardown, and evaluator logic
- `suite/`: orchestration, artifacts, batch, compare, and report helpers
- `docs/`: reference documentation
