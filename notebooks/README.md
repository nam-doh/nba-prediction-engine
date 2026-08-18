# Notebook Reports

Analysis notebooks for the NBA Prediction Engine, organized by project phase. Each notebook has a **Table of Contents** at the top for quick navigation.

## Quick View (HTML)

Open these reports in any browser — no Jupyter environment required:

| Phase | Report                                                       | Description                                                                                  |
| ----- | ------------------------------------------------------------ | -------------------------------------------------------------------------------------------- |
| 1     | [01_data_exploration.html](01_data_exploration.html)         | NBA API data acquisition, cleaning, validation, and exploratory analysis                     |
| 2     | [02_feature_analysis.html](02_feature_analysis.html)         | Rolling feature engineering, opponent features, correlations, and multicollinearity analysis |
| 3     | [03_predictive_modeling.html](03_predictive_modeling.html)   | Logistic Regression, Decision Tree, Random Forest, XGBoost, tuning, and model comparison     |
| 4     | [04_model_explainability.html](04_model_explainability.html) | SHAP global/local explanations and probability calibration                                   |
| 5     | [05_game_simulation.html](05_game_simulation.html)           | Monte Carlo game, series, playoff, and repeated full-season simulations                      |

> **Phase 6 — Live Prediction Pipeline:** In Progress

## Source Notebooks

| Phase | Notebook                                                       | Primary Input Data                                          |
| ----- | -------------------------------------------------------------- | ----------------------------------------------------------- |
| 1     | [01_data_exploration.ipynb](01_data_exploration.ipynb)         | NBA API                                                     |
| 2     | [02_feature_analysis.ipynb](02_feature_analysis.ipynb)         | `data/processed/team_stats_clean.csv`                       |
| 3     | [03_predictive_modeling.ipynb](03_predictive_modeling.ipynb)   | `data/processed/team_game_logs_clean.csv`                   |
| 4     | [04_model_explainability.ipynb](04_model_explainability.ipynb) | `data/processed/team_game_modeling.csv`                     |
| 5     | [05_game_simulation.ipynb](05_game_simulation.ipynb)           | `data/processed/team_game_modeling.csv`                     |
| 6     | `06_live_prediction_pipeline.ipynb` *(In Progress)*            | `data/processed/team_game_modeling.csv` + upcoming schedule |

## Phase Summary

### Phase 1 — Data Exploration

Collects NBA data through `nba_api`, performs cleaning and validation, and explores the distributions and relationships of core team performance statistics.

### Phase 2 — Feature Analysis

Transforms historical team data into predictive pregame features, including rolling five-game statistics, opponent metrics, home-court context, rest days, and team-vs-opponent differentials.

Correlation and VIF analysis are also used to examine feature redundancy and multicollinearity.

### Phase 3 — Predictive Modeling

Develops and compares four classification approaches:

* Logistic Regression
* Decision Tree
* Random Forest
* XGBoost

Models are evaluated using Accuracy, Precision, Recall, F1 Score, and ROC AUC.

Key results:

| Model                         |  Accuracy |  F1 Score |   ROC AUC |
| ----------------------------- | --------: | --------: | --------: |
| Logistic Regression           |     0.644 |     0.645 | **0.711** |
| Decision Tree (`max_depth=5`) |     0.637 |     0.624 |     0.691 |
| Tuned Random Forest           | **0.647** |     0.646 |     0.710 |
| XGBoost                       | **0.647** | **0.650** |     0.699 |

Logistic Regression produced the strongest ROC AUC, while tuned Random Forest and XGBoost achieved the highest classification accuracy.

### Phase 4 — Model Explainability

Uses SHAP to analyze both global model behavior and individual predictions.

Key analyses include:

* Global SHAP feature importance
* SHAP beeswarm feature-effect analysis
* Local waterfall explanations
* High-confidence correct and incorrect prediction case studies
* Probability calibration curves
* Brier Score comparison

The strongest predictors consistently included:

* `SEASON_WIN_PCT`
* `PLUS_MINUS_ROLL5_DIFF`
* `HOME_GAME`
* Recent team and opponent plus-minus
* Recent win-percentage differential

Logistic Regression produced a slightly better Brier Score (**0.2172**) than Random Forest (**0.2185**), supporting its use when calibrated win probabilities are prioritized.

### Phase 5 — Monte Carlo Simulation

Extends individual game probabilities into repeated probabilistic simulations.

The simulation framework includes:

* Repeated single-game simulation
* Best-of-seven series simulation
* Home/away-adjusted playoff series
* Model-generated matchup probabilities
* Common-date team snapshots
* Conference simulations
* Full historical regular-season simulation
* Repeated season simulations

Full-season simulations repeatedly replay the historical schedule using model-generated pregame win probabilities.

Instead of predicting one exact win total, the simulator produces distributions containing:

* Average simulated wins
* Win-total standard deviation
* 10th-percentile outcomes
* 90th-percentile outcomes

The current season simulation uses historical pregame feature states, meaning simulated outcomes affect simulated standings but do not dynamically alter future rolling statistics.

### Phase 6 — Live Prediction Pipeline *(In Progress)*

Converts the historical modeling framework into a future-facing prediction system.

Current development focuses on:

* Retraining the production model using all completed historical seasons
* Maintaining latest team-state information
* Building feature rows for future matchups
* Handling early-season feature initialization
* Calculating schedule-based rest days
* Generating future game win probabilities
* Predicting multiple upcoming games
* Saving prediction outputs for future dashboard use

## Running Locally

From the project root with the virtual environment activated:

```bash
jupyter lab notebooks/
```

To regenerate an HTML export after editing a notebook:

```bash
jupyter nbconvert --to html notebooks/NN_notebook_name.ipynb
```

## Pipeline Flow

```text
Phase 1: Data Exploration
    │
    └── team_stats_clean.csv
        team_game_logs_clean.csv
            │
            ▼
Phase 2: Feature Engineering & Analysis
            │
            └── engineered team / opponent features
                    │
                    ▼
Phase 3: Predictive Modeling
            │
            └── team_game_modeling.csv
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
Phase 4: Explainability   Phase 5: Simulation
          │                   │
          │                   └── game / series / season forecasts
          │
          └───────┬───────────┘
                  ▼
Phase 6: Live Prediction Pipeline
                  │
                  ▼
        Upcoming Game Predictions
                  │
                  ▼
         Future Dashboard / Deployment
```
