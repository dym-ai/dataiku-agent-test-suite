# Time Series Forecasting Analysis

* **Scenario Name:** Forecast Weekly Demand for High-Volume Products
* **Target Function:** `machine-learning` skill with `timeseries-forecasting` child skill using forecasting analysis create, update, train, and inspection
* **Sample Data (Schema & Mock Data):** Training dataset `weekly_product_demand` with `week_start` (date), `sku` (string), `region` (string), `units_sold` (int), `promo_flag` (boolean), `avg_discount_pct` (double), `inventory_on_hand` (int)

| week_start | sku | region | units_sold | promo_flag | avg_discount_pct | inventory_on_hand |
| --- | --- | --- | ---: | --- | ---: | ---: |
| 2025-12-29 | SKU-101 | West | 420 | true | 15.0 | 860 |
| 2026-01-05 | SKU-101 | West | 398 | false | 0.0 | 790 |
| 2026-01-12 | SKU-101 | West | 447 | true | 10.0 | 730 |
| 2026-01-19 | SKU-101 | West | 389 | false | 0.0 | 700 |
| 2026-01-26 | SKU-101 | West | 462 | true | 12.5 | 640 |

* **Natural Language Instruction:** "Create a weekly demand forecast for each product-region series so our supply team can see the next few periods of demand. Use the historical sales pattern plus promotions and inventory context if Dataiku supports it."
* **Expected Dataiku Action/Output:** Creates a time series forecasting analysis, configures the time column, target, identifiers, horizon, and candidate algorithms, trains the models, inspects forecast quality, and produces a forecasting analysis that can later be deployed or used for downstream planning workflows.
