# TODO

## Benchmark Integrity

- Add a `doctor` command that verifies DSS credentials, configured profiles, agent commands, workspace paths, MCP availability, and artifact/test prerequisites before a run.
- Add an `init` command that writes a repo-local `.dataiku-agent-suite.json` for first-time setup, including a ready-to-edit `dataiku-agent-dev-kit` profile.
- Add profile-level MCP wiring so Codex/Claude runs can point at the staged `dataiku-agent-dev-kit` checkout, not a globally configured MCP server from another path.
- Add `run --all` support to run every case in `cases/`.
- Add `run --repeat N` support so performance comparisons use repeated runs instead of one-off samples.
- Add benchmark summaries with pass rate, median duration, median token usage, median tool usage, and variance across repeated runs.
- Record digests for all case fixtures, not only `case.json`, so artifacts fully identify the evaluated input set.
- Document and wire a reliable local test command, either by adding `pytest` as a dev dependency or documenting `uv run python -m unittest discover -s tests -p 'test_*.py'`.
