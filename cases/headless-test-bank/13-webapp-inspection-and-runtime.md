# WebApp Inspection and Runtime

* **Scenario Name:** Update and Restart an Executive KPI Streamlit App
* **Target Function:** `webapps` skill using WebApp discovery, settings round-trip update, state inspection, and backend restart
* **Sample Data (Schema & Mock Data):** Downstream app dataset `executive_kpi_snapshot` with `snapshot_date` (date), `region` (string), `pipeline_value` (double), `won_revenue` (double), `forecast_gap_pct` (double)

| snapshot_date | region | pipeline_value | won_revenue | forecast_gap_pct |
| --- | --- | ---: | ---: | ---: |
| 2026-02-15 | West | 1425000.00 | 418000.00 | -4.5 |
| 2026-02-15 | Central | 895000.00 | 277500.00 | 2.1 |
| 2026-02-15 | East | 1652000.00 | 503000.00 | -1.0 |
| 2026-02-15 | South | 734000.00 | 241000.00 | 3.8 |

* **Natural Language Instruction:** "Find the executive KPI WebApp, update its title and default date to the latest snapshot, then restart the backend so the changes are live."
* **Expected Dataiku Action/Output:** Lists WebApps, inspects the target WebApp's full settings and current backend state, updates only the necessary settings fields through a full-settings round-trip, restarts the backend, and validates the post-restart state without disturbing unrelated config.
