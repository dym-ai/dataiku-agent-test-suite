# Join and Grouping KPI Analysis

* **Scenario Name:** Compare Regional Sales Against Quarterly Quota
* **Target Function:** `recipes` skill with `join` and `grouping` child skills using a multi-step transformation flow
* **Sample Data (Schema & Mock Data):** Two input datasets: `sales_actuals_q3` with `region` (string), `rep_id` (string), `quarter` (string), `booked_revenue` (double), `closed_deals` (int); and `sales_quota_q3` with `region` (string), `quarter` (string), `quota_revenue` (double)

| region | rep_id | quarter | booked_revenue | closed_deals |
| --- | --- | --- | ---: | ---: |
| West | SR-01 | Q3-2026 | 185000.00 | 14 |
| West | SR-02 | Q3-2026 | 162500.00 | 11 |
| Central | SR-03 | Q3-2026 | 133000.00 | 10 |
| East | SR-04 | Q3-2026 | 201500.00 | 16 |
| South | SR-05 | Q3-2026 | 118250.00 | 9 |

| region | quarter | quota_revenue |
| --- | --- | ---: |
| West | Q3-2026 | 330000.00 |
| Central | Q3-2026 | 145000.00 |
| East | Q3-2026 | 190000.00 |
| South | Q3-2026 | 125000.00 |

* **Natural Language Instruction:** "I want to compare Q3 2026 booked revenue to Q3 quota by region and show which regions are above or below plan. Build whatever flow steps are needed so I get a regional variance dataset."
* **Expected Dataiku Action/Output:** Creates a join recipe between actuals and quota on region and quarter, then a grouping recipe to aggregate revenue and deal counts by region, computes variance-to-plan fields in the appropriate flow step, and produces an output dataset showing total actuals, quota, and over-or-under performance by region.
