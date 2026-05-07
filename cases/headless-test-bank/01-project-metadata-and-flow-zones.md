# Project Metadata and Flow Zones

* **Scenario Name:** Churn Modeling Project Setup and Flow Zone Organization
* **Target Function:** `projects` skill using project metadata updates, project variables, and flow zone creation/population
* **Natural Language Instruction:** "Set up project `SOL_CHURN_PREDICTION` for our customer churn initiative. Rename the project label to `FY26 Churn Early Warning`, add tags for `retention`, `ml`, and `priority`, add a short description, create flow zones for `Raw Inputs`, `Feature Prep`, and `Modeling`, and place the existing datasets and recipes into the right zones."
* **Expected Dataiku Action/Output:** Applies to the `Churn Prediction for Administrator` solution. Reads current project metadata and flow structure, updates project label/description/tags through a metadata round-trip, optionally updates project variables if needed, creates three flow zones, and assigns discovered datasets and recipes into the target zones using flow item refs.

