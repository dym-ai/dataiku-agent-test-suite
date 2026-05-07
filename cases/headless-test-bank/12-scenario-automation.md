# Scenario Automation

* **Scenario Name:** Daily Revenue Pipeline Rebuild and Alerting
* **Target Function:** `scenarios` skill using scenario creation, step/triggers configuration, and run-history oriented validation
* **Sample Data (Schema & Mock Data):** Target build set represented by `daily_revenue_summary` with `business_date` (date), `region` (string), `net_revenue` (double), `refunds` (double), `orders_count` (int), `pipeline_status` (string)

| business_date | region | net_revenue | refunds | orders_count | pipeline_status |
| --- | --- | ---: | ---: | ---: | --- |
| 2026-02-10 | West | 284500.00 | 11400.00 | 1380 | ready |
| 2026-02-10 | Central | 192250.00 | 7300.00 | 1012 | ready |
| 2026-02-10 | East | 309900.00 | 12880.00 | 1494 | ready |
| 2026-02-10 | South | 177440.00 | 6940.00 | 944 | ready |

* **Natural Language Instruction:** "Operationalize this revenue pipeline so it rebuilds every weekday at 6 AM, refreshes the downstream score outputs, and emails our ops mailbox if the run fails."
* **Expected Dataiku Action/Output:** Creates or updates a step-based scenario, loads the scenario step reference before constructing payloads, configures temporal triggers for weekday scheduling, adds build steps for the required datasets or models, optionally adds refresh or schema propagation steps, configures an email reporter when sender/recipient/channel details are available, and leaves the scenario active for scheduled execution.
