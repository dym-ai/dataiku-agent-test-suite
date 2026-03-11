# Agent Contract

This harness talks to agents through a small file-based protocol.

Your agent command must:

1. Accept `--request <path>` and `--response <path>`.
2. Read the request JSON from disk.
3. Perform the task in the target DSS project.
4. Write a response JSON to the response path.

The harness owns setup, validation, reporting, cleanup, and artifact writing. The agent only needs to do the task in the prompt.

## Invocation Model

When you run:

```bash
python run_test.py dates --agent "python /path/to/my_agent.py"
```

the harness invokes:

```bash
python /path/to/my_agent.py --request /tmp/request.json --response /tmp/response.json
```

`--agent-workspace` is not forwarded on the command line. The resolved workspace path is included in the request JSON instead, and the agent can decide whether to use it as its working directory.

If no `agent_workspace` is configured, the harness creates a temporary isolated workspace for the run.

Avoid pointing `agent_workspace` at the harness repository itself, because that can expose case definitions and evaluator logic to the agent.

Bundled wrappers:

- `agents/codex.py`
- `agents/claude.py`

Those wrappers are convenience adapters. They work if the underlying `codex` or `claude` CLI is already installed.

You can also use your own command instead of the bundled wrappers, for example:

```bash
python run_test.py dates --agent "python /path/to/my_agent.py"
```

or a repo-local config like:

```json
{
  "agent_command": "python /path/to/my_agent.py"
}
```

## Request JSON

The harness currently sends:

```json
{
  "version": 1,
  "case_name": "dates",
  "project_key": "COBUILD_DATES_1772835245_A1B2C3D4",
  "prompt": "The natural language task...",
  "sources": ["Dates"],
  "workspace": "/path/to/agent/workspace"
}
```

Fields:

- `version`: protocol version
- `case_name`: the case being run
- `project_key`: generated DSS project key the agent should work in
- `prompt`: natural-language task for the agent
- `sources`: source datasets already copied into the generated project
- `workspace`: local directory the agent may use for tooling, scripts, or scaffolding; this is either the configured `agent_workspace` or a temporary isolated workspace

## Response JSON

Your agent should write something like:

```json
{
  "version": 1,
  "status": "completed",
  "summary": "Short human-readable summary",
  "stdout": "Optional agent stdout",
  "stderr": "Optional agent stderr",
  "stats": {
    "duration_ms": 12345,
    "input_tokens": 1000,
    "cached_input_tokens": 200,
    "output_tokens": 234,
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

Notes:

- `duration_ms`, `total_tokens`, and `tool_uses` are optional
- `input_tokens`, `cached_input_tokens`, and `output_tokens` are also supported when the agent or wrapper can report them directly
- `tool_uses` is most reliable when the agent writes it directly into `response.stats`
- The bundled wrappers also attempt best-effort stats extraction from CLI output
