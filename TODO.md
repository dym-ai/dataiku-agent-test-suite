# TODO

## High Priority

- Redesign the CLI around explicit subcommands such as `run`, `list-cases`, `describe-case`, and `doctor`.
- Add an interactive `init` flow that writes a repo-local harness config file for first-time setup.
- Add CLI support for running multiple named cases in one invocation.
- Add CLI support for running all cases in the `cases/` directory.
- Decide how multi-case runs should report aggregate results and exit codes.
- Add example cases that use `flow_shape_match`.
- Add example cases that use `recipe_config_match`.

## Medium Priority

- Add better debugging artifacts for failed flow/config evals, such as matched alias mappings and recipe config diffs.
- Consider a dedicated snapshot/export helper for authoring `flow_shape_match` and `recipe_config_match` expectations.
- Decide how much normalization `recipe_config_match` should apply in `normalized` mode.
- Decide whether built-in cases should demonstrate stricter evals or remain minimal output-only examples.
- Consider making project key generation collision-resistant for rapid or parallel runs.

## Low Priority

- Improve `output_datasets` with an optional full-dataset comparison mode for small outputs.
- Decide whether `output_datasets` should support key-based full-row matching beyond sampled rows.
- Consider documenting a recommended structure for custom evaluator modules.
