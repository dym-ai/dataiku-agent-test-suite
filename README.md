# Dataiku Agent Test Suite

A benchmark harness for testing whether an AI agent can complete Dataiku DSS tasks.

This repo is not the agent under test. It creates fresh DSS projects, runs an
external agent command, evaluates the result, and reports pass/fail.

## Quick Start

Install dependencies:

```bash
uv sync
```

Create a local config:

```bash
cp .dataiku-agent-suite.example.json .dataiku-agent-suite.json
```

Set your DSS credentials in your shell:

```bash
export DATAIKU_URL="https://your-dss.example.com"
export DATAIKU_API_KEY="..."
```

Edit `.dataiku-agent-suite.json` so `defaults.profile` points at the agent setup
you want to benchmark. Common profiles look like:

```json
{
  "defaults": {
    "profile": "dev-kit-codex",
    "artifacts_dir": "./artifacts",
    "keep": true,
    "env": {
      "DATAIKU_URL": "${DATAIKU_URL}",
      "DATAIKU_API_KEY": "${DATAIKU_API_KEY}"
    }
  },
  "profiles": {
    "dev-kit-codex": {
      "agent": "codex",
      "agent_workspace": "/path/to/dataiku-agent-dev-kit"
    },
    "dev-kit-claude": {
      "agent": "claude",
      "agent_workspace": "/path/to/dataiku-agent-dev-kit"
    }
  }
}
```

Run a case:

```bash
uv run python run_test.py run dates
```

Override the default profile for one run:

```bash
uv run python run_test.py run dates --profile dev-kit-claude
```

## Useful Commands

```bash
uv run python run_test.py list-cases
uv run python run_test.py describe-case dates
uv run python run_test.py list-profiles
uv run python run_test.py run dates --keep
uv run python run_test.py batch --cases dates crane --profiles dev-kit-codex dev-kit-claude
uv run python run_test.py compare /path/to/run-a /path/to/run-b
```

## How It Works

For each run, the harness:

1. Creates a fresh DSS project.
2. Uploads or copies the case source datasets.
3. Stages the configured agent workspace, if any.
4. Sends the task to the agent through a request/response JSON contract.
5. Runs the case evaluators against the finished DSS project.
6. Prints a report and optionally writes artifacts.

Artifacts include the request, agent response, validation result, run manifest,
stdout/stderr excerpts, and terminal report. Persisted agent output is sanitized
for common secret patterns.

## Adding Cases

Cases live under `cases/`. A typical case has:

```text
cases/my_case/
  case.json
  input_data/source.csv
```

The simplest evaluator checks final output datasets against expected schemas,
row counts, and sample values. More specific cases can add flow, recipe, tool
usage, or custom evaluators.

See [docs/cases-and-evaluators.md](docs/cases-and-evaluators.md).

## More Detail

- [docs/agent-contract.md](docs/agent-contract.md): agent request/response protocol and wrapper behavior
- [docs/cases-and-evaluators.md](docs/cases-and-evaluators.md): case and evaluator reference

## Layout

- `run_test.py`: CLI entrypoint
- `cases/`: runnable case definitions and fixtures
- `agents/`: bundled Codex and Claude wrappers
- `evals/`: case setup, validation, teardown, and evaluator logic
- `suite/`: orchestration, profiles, artifacts, batch, compare, and reports
