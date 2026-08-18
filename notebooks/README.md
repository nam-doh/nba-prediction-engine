# Notebook Reports

Analysis notebooks for the NBA Prediction Engine, organized by project phase. Each notebook has a **Table of Contents** at the top for quick navigation.

## Quick View (HTML)

Open these reports directly in a browser — no Jupyter environment required.

| Phase | Report                                                               | Description                                                                                  |
| ----- | -------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| 1     | [01_data_exploration.html](01_data_exploration.html)                 | NBA API data acquisition, cleaning, validation, and exploratory analysis                     |
| 2     | [02_feature_analysis.html](02_feature_analysis.html)                 | Rolling feature engineering, opponent features, correlations, and multicollinearity analysis |
| 3     | [03_predictive_modeling.html](03_predictive_modeling.html)           | Logistic Regression, Decision Tree, Random Forest, XGBoost, tuning, and model comparison     |
| 4     | [04_model_explainability.html](04_model_explainability.html)         | SHAP global/local explanations, confidence analysis, and probability calibration             |
| 5     | [05_game_simulation.html](05_game_simulation.html)                   | Monte Carlo game, playoff-series, conference, and full-season simulations                    |
| 6     | [06_live_prediction_pipeline.html](06_live_prediction_pipeline.html) | Production-model training and future-facing game prediction pipeline                         |

---

## Source Notebooks

| Phase | Notebook                                                               | Primary Input Data                                                 |
| ----- | ---------------------------------------------------------------------- | ------------------------------------------------------------------ |
| 1     | [01_data_exploration.ipynb](01_data_exploration.ipynb)                 | NBA API                                                            |
| 2     | [02_feature_analysis.ipynb](02_feature_analysis.ipynb)                 | `data/processed/team_stats_clean.csv`                              |
| 3     | [03_predictive_modeling.ipynb](03_predictive_modeling.ipynb)           | `data/processed/team_game_logs_clean.csv`                          |
| 4     | [04_model_explainability.ipynb](04_model_explainability.ipynb)         | `data/processed/team_game_modeling.csv`                            |
| 5     | [05_game_simulation.ipynb](05_game_simulation.ipynb)                   | `data/processed/team_game_modeling.csv`                            |
| 6     | [06_live_prediction_pipeline.ipynb](06_live_prediction_pipeline.ipynb) | `data/processed/team_game_modeling.csv` + manual upcoming schedule |

---

## Phase 1 — Data Exploration

This notebook establishes the historical dataset used by the project.

Work includes:

* NBA API data acquisition
* Data cleaning
* Data validation
* Statistical summaries
* Missing-value analysis
* Exploratory visualization
* Initial analysis of relationships between team statistics and winning

Outputs include cleaned team-level and game-level datasets used by later phases.

---

## Phase 2 — Feature Engineering & Analysis

This notebook transforms historical game data into pregame predictive features.

Features include:

* Rolling five-game statistics
* Season win percentage
* Home-court indicator
* Rest days
* Opponent statistics
* Team-vs-opponent differential variables

Feature relationships are evaluated using:

* Correlation analysis
* Distribution analysis
* Multicollinearity diagnostics
* Variance Inflation Factor analysis

The resulting features form the modeling dataset used by subsequent notebooks.

---

## Phase 3 — Predictive Modeling

This notebook develops and compares four classification approaches:

* Logistic Regression
* Decision Tree
* Random Forest
* XGBoost

Models are evaluated using:

* Accuracy
* Precision
* Recall
* F1 Score
* ROC AUC
* Confusion matrices
* Feature importance

Hyperparameter tuning is used to reduce overfitting in the Decision Tree and Random Forest models.

### Final Results

| Model                         |  Accuracy |  F1 Score |   ROC AUC |
| ----------------------------- | --------: | --------: | --------: |
| Logistic Regression           |     0.644 |     0.645 | **0.711** |
| Decision Tree (`max_depth=5`) |     0.637 |     0.624 |     0.691 |
| Tuned Random Forest           | **0.647** |     0.646 |     0.710 |
| XGBoost                       | **0.647** | **0.650** |     0.699 |

Logistic Regression was retained as the primary probability model because of its strong ROC AUC, competitive classification performance, and later calibration results.

---

## Phase 4 — Model Explainability

This notebook explains how the predictive models generate their outputs.

SHAP analysis includes:

* Global feature importance
* Beeswarm feature-effect analysis
* Local waterfall plots
* High-confidence correct prediction example
* High-confidence incorrect prediction example

The strongest global predictors included:

* `SEASON_WIN_PCT`
* `PLUS_MINUS_ROLL5_DIFF`
* `HOME_GAME`
* `OPP_PLUS_MINUS_ROLL5`

Probability calibration is also evaluated.

### Brier Score

| Model               | Brier Score |
| ------------------- | ----------: |
| Logistic Regression |  **0.2172** |
| Random Forest       |      0.2185 |

The results indicate that Logistic Regression produced marginally better probability estimates while Random Forest remained useful for nonlinear SHAP analysis.

---

## Phase 5 — Monte Carlo Simulation

This notebook extends game-level probabilities into larger probabilistic outcomes.

The simulation framework progresses through:

```text
Single Game
    ↓
Repeated Game Simulation
    ↓
Best-of-Seven Series
    ↓
Home/Away Series
    ↓
Model-Generated Matchups
    ↓
Conference Simulation
    ↓
Full Regular-Season Simulation
    ↓
Repeated Season Simulation
```

Repeated full-season simulations estimate:

* Average wins
* Standard deviation
* 10th-percentile win totals
* 90th-percentile win totals

The simulation uses historical pregame model probabilities. Simulated results change simulated standings but do not currently alter the historical rolling features used in subsequent games.

---

## Phase 6 — Live Prediction Pipeline

This notebook converts the historical prediction system into a future-facing production workflow.

Key components include:

* Retraining Logistic Regression using all available historical data
* Creating a latest-team-state table
* Building future matchup features
* Manual upcoming-schedule input
* Team-name validation
* Rest-day calculation
* Future team game-number calculation
* Upcoming-game prediction
* Schedule-level prediction
* Prediction confidence ranking
* Probability validation
* Saving prediction output
* Saving the trained production model

Primary outputs:

```text
data/processed/latest_predictions.csv
models/logistic_regression_production.pkl
```

The schedule-input component is intentionally separate from the prediction logic so automated NBA API ingestion can be added later without redesigning the prediction pipeline.

---

## Pipeline Flow

```text
Phase 1: Data Exploration
    │
    └── Clean historical datasets
            │
            ▼
Phase 2: Feature Engineering & Analysis
            │
            └── Pregame team/opponent features
                    │
                    ▼
Phase 3: Predictive Modeling
            │
            └── Model evaluation and selection
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
Phase 4: Explainability   Phase 5: Simulation
          │                   │
          │                   └── probabilistic game/season outcomes
          │
          └────────┬──────────┘
                   ▼
Phase 6: Live Prediction Pipeline
                   │
          ┌────────┴────────┐
          ▼                 ▼
Production Model      latest_predictions.csv
          │                 │
          └────────┬────────┘
                   ▼
          Future Dashboard / API
```

---

## Running Locally

From the project root with the virtual environment activated:

```bash
jupyter lab notebooks/
```

To regenerate an HTML report after changing a notebook:

```bash
jupyter nbconvert --to html notebooks/NN_notebook_name.ipynb
```

For example:

```bash
jupyter nbconvert --to html notebooks/06_live_prediction_pipeline.ipynb
```

---

## Notebook Status

| Phase                        | Status   |
| ---------------------------- | -------- |
| 1 — Data Exploration         | Complete |
| 2 — Feature Engineering      | Complete |
| 3 — Predictive Modeling      | Complete |
| 4 — Model Explainability     | Complete |
| 5 — Monte Carlo Simulation   | Complete |
| 6 — Live Prediction Pipeline | Complete |

All six core notebooks are complete and can be viewed either through their `.ipynb` source files or exported HTML reports.
