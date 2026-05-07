# Connection Discovery and Validation

* **Scenario Name:** Finance Warehouse Connection Discovery for Margin Reporting
* **Target Function:** `connections` skill using `list_connections`, `get_connection_info`, and `test_connection`
* **Natural Language Instruction:** "I need the right connection for a new finance reporting dataset. Find the warehouse connection that supports managed datasets and write access, confirm it can be used by this project, and test it before we build anything."
* **Expected Dataiku Action/Output:** Lists available DSS connections, inspects candidate connection capabilities in project context, identifies a write-capable warehouse connection that supports the task, runs a connection test if appropriate, and returns a recommended connection name with justification and any permission caveats.
