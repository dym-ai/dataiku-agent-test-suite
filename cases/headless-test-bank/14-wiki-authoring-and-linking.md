# Wiki Authoring and Linking

* **Scenario Name:** Publish an Operations Runbook with DSS Object Links
* **Target Function:** `wikis` skill using wiki article creation, update, and DSS object reference linking
* **Sample Data (Schema & Mock Data):** Documentation source dataset `pipeline_runbook_sources` with `section_name` (string), `owner_team` (string), `referenced_object_type` (string), `referenced_object_id` (string), `notes` (string)

| section_name | owner_team | referenced_object_type | referenced_object_id | notes |
| --- | --- | --- | --- | --- |
| Daily Revenue Build | Revenue Ops | dataset | daily_revenue_summary | Primary output checked every morning |
| Churn Scoring | Retention Analytics | recipe | score_churn_accounts | Refresh after model updates |
| Saved Model | Data Science | saved_model | AB12cd34 | Active churn model for production scoring |
| Automation | Platform Ops | scenario | daily_revenue_refresh | Weekday scheduled rebuild and alerts |

* **Natural Language Instruction:** "Create a project wiki article called `Revenue Pipeline Runbook` that explains the daily build, links to the key dataset, scoring recipe, model, and automation scenario, and puts it under our Operations section."
* **Expected Dataiku Action/Output:** Lists existing wiki articles to resolve placement, creates or updates the requested article under the correct parent, writes markdown content with DSS object references for datasets, recipes, saved models, and scenarios using discovered IDs or names, and validates the article by reading it back or re-listing the wiki tree.
