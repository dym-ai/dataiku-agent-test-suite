# Binary Classification Prediction Analysis

* **Scenario Name:** Predict Subscription Churn Risk
* **Target Function:** `machine-learning` skill with `prediction` child skill using prediction analysis creation, tuning, training, and deployment
* **Sample Data (Schema & Mock Data):** Training dataset `subscriber_churn_features` with `customer_id` (string), `monthly_fee` (double), `support_cases_90d` (int), `tenure_months` (int), `auto_pay` (boolean), `usage_drop_pct_30d` (double), `churned` (boolean)

| customer_id | monthly_fee | support_cases_90d | tenure_months | auto_pay | usage_drop_pct_30d | churned |
| --- | ---: | ---: | ---: | --- | ---: | --- |
| S001 | 129.00 | 4 | 6 | false | 37.5 | true |
| S002 | 89.00 | 0 | 24 | true | 4.2 | false |
| S003 | 59.00 | 2 | 11 | false | 22.0 | true |
| S004 | 149.00 | 1 | 31 | true | 3.0 | false |
| S005 | 99.00 | 3 | 8 | false | 28.4 | true |

* **Natural Language Instruction:** "Build me a churn prediction model from this subscriber feature table, optimize for finding likely churners instead of just raw accuracy, and deploy the best model into the flow so we can score new customers."
* **Expected Dataiku Action/Output:** Creates a prediction analysis on the training dataset, sets the binary target column, chooses an appropriate metric such as ROC AUC or a churn-sensitive metric, tunes feature roles and algorithms, trains the analysis, compares trained models, deploys the selected model as a saved model in the flow, and leaves the project ready for a downstream scoring recipe.
