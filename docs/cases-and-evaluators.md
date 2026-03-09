# Cases And Evaluators

## Writing A Case

Create a JSON file in `cases/`.

Minimum required top-level fields:

- `name`
- `description`
- `prompt`
- `source_project`
- `sources`

If `evals` is omitted, the harness uses:

```json
[
  {"name": "output_datasets"}
]
```

A compact example:

```json
{
  "name": "my_case",
  "description": "Parse a source column and build a final dataset.",
  "prompt": "Create a pipeline that transforms the source data into final_output.",
  "source_project": "MY_PROJECT",
  "sources": ["source_dataset"],
  "expected_outputs": {
    "final_output": {
      "schema": [
        {"name": "column_name", "type": "bigint"}
      ],
      "row_count": 42,
      "data": [
        {"column_name": 123}
      ]
    }
  },
  "evals": [
    {"name": "output_datasets"}
  ]
}
```

Key fields:

- `source_project`: DSS project containing the source datasets
- `sources`: datasets copied into the generated project before the agent runs
- `prompt`: natural-language task the agent sees
- `expected_outputs`: final datasets used by the default `output_datasets` evaluator
- `evals`: optional evaluator list; if omitted, only `output_datasets` runs

Case validation happens before setup starts. The harness validates both the base case structure and each configured evaluator spec and fails early when required fields are missing.

## Built-In Evaluators

Available built-in evaluator names:

- `output_datasets`: validates dataset existence, schema, row counts, and sampled values
- `flow_shape_match`: compares an anonymous flow graph using dataset schemas, recipe types, and connectivity
- `recipe_config_match`: compares recipe payload or params for matched recipes in an anonymous flow graph
- `recipe_type_counts`: checks exact recipe counts by type
- `forbid_recipe_types`: fails if forbidden recipe types are present

### `output_datasets`

`output_datasets` reads from `expected_outputs` unless you override it in the evaluator spec.

Options:

- `sample_mode`: `unordered` (default), `ordered`, or `by_key`
- `key_columns`: required when `sample_mode` is `by_key`

Behavior:

- `ordered` compares expected sample rows against the first `N` output rows by position
- `unordered` checks that each expected sample row appears somewhere in the dataset
- `by_key` matches expected rows to actual rows using the provided key columns

### `flow_shape_match` And `recipe_config_match`

These evaluators use an anonymous flow graph:

- `nodes`: a map of user-defined aliases to dataset schemas
- `recipes`: a list of recipe specs using those aliases in `inputs` and `outputs`

Alias names are placeholders inside the case file. They are not compared to the actual DSS dataset names.

Example:

```json
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
}
```

`recipe_config_match` adds:

- `mode`: `raw` or `normalized`
- `compare`: `subset` or `exact`
- `config`: expected fragment shaped like `{"payload": ..., "params": ...}`

In `subset` mode, dicts are matched by key subset and lists by ordered prefix.

### `recipe_type_counts`

Use `expected` to declare exact counts by recipe type.

Example:

```json
{
  "name": "recipe_type_counts",
  "expected": [
    {"type": "shaker", "count": 1},
    {"type": "join", "count": 0}
  ]
}
```

### `forbid_recipe_types`

Use `types` to declare recipe types that must not appear.

Example:

```json
{
  "name": "forbid_recipe_types",
  "types": ["python", "sql_query"]
}
```

## Custom Evaluators

You can add a local Python evaluator without changing the harness core.

In `evals[].name`, use:

```text
module_name:function_name
```

The evaluator function should accept:

```python
(client, project_key, case, spec)
```

and return a list of check dicts.

Optional:

- expose `validate_spec(spec, case)` on the evaluator function for early spec validation
