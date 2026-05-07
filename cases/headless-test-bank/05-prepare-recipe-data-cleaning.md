# Prepare Recipe Data Cleaning

* **Scenario Name:** Standardize Support Ticket Priority and Contact Data
* **Target Function:** `recipes` skill with `prepare` child skill using a visual prepare recipe
* **Sample Data (Schema & Mock Data):** Input dataset `support_tickets_raw` with `ticket_id` (string), `opened_at` (string), `priority_text` (string), `customer_email` (string), `resolution_minutes` (int), `status` (string)

| ticket_id | opened_at | priority_text | customer_email | resolution_minutes | status |
| --- | --- | --- | --- | ---: | --- |
| T-1001 | 01/12/2026 08:14 AM | high  | ANA.SMITH@EXAMPLE.COM | 55 | closed |
| T-1002 | 2026-01-12 09:01:22 | med | bruno.lee@example.com | 240 | open |
| T-1003 | 12-Jan-2026 09:17 | urgent | carla+vip@example.com | 18 | closed |
| T-1004 | 2026/01/12 10:44 | low | d.patel@example.com | 510 | pending |
| T-1005 | 2026-01-12T11:02:00Z | High | emma.jones@example.com | 72 | closed |

* **Natural Language Instruction:** "Clean this support ticket dataset so the opened timestamp is parsed consistently, priority values are standardized, and customer emails are normalized to lowercase before we hand it to the ops team."
* **Expected Dataiku Action/Output:** Creates or updates a visual prepare recipe, uses appropriate processors such as date parsing, find/replace or normalization, and text simplification or lowercase normalization, builds the output dataset, and validates the resulting schema and sample rows.
