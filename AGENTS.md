# Repository Intent

This repository is a test harness, not the agent being tested.

When making changes here, optimize for this goal:
- Let arbitrary agents or agentic systems, with arbitrary execution logic and tooling, run a test case that asks them to build a Dataiku flow or part of a flow.
- Let the harness evaluate the result using selected evaluators or the default evaluator set for that case.
- Let the final success or failure of the run be determined by those evaluators, plus basic harness-level execution checks.

# What To Preserve

- Keep the harness neutral with respect to agent implementation details.
- Do not assume the tested agent lives inside this repo.
- Do not bias the harness toward a specific workflow, tool stack, or orchestration style unless a case explicitly requires it.
- Keep `run_test.py` as the main CLI entrypoint for running cases against an external agent command.
- Preserve the ability for users to run one case, multiple cases in the future, or all cases through the CLI.
- Preserve clear reporting of results after completion.
- Preserve the option to keep generated DSS projects so users can inspect the resulting flow and artifacts.

# Expected User Model

Assume the user will usually:
- build or own their agentic system outside this repo
- invoke this repo through the CLI
- choose one or more cases to test
- let the harness create fresh DSS projects, run the agent, and evaluate the result
- inspect reports and optionally retained DSS projects afterward

# Change Guidance

- Prefer modular evaluators over hard-coded policy rules.
- Prefer explicit case and evaluator validation over implicit assumptions.
- Treat cases as scenario definitions and evaluators as pluggable judges.
- Keep the default path minimal and easy to use.
- Add stricter or more opinionated behavior as opt-in evaluator logic, not as global harness behavior.
- If a change makes the harness more coupled to one agent, one environment, or one methodology, assume that change is probably wrong unless the repo’s purpose clearly requires it.
- Don't worry about backwards compatibility with any changes you make.

# Repo Knowledge

If you need details about current commands, file layout, or runtime behavior, read `README.md` and the code. `AGENTS.md` is for repository intent and change philosophy, not for duplicating operating instructions.
