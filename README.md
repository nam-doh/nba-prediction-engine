# NBA Prediction Engine

## Project Overview

The NBA Prediction Engine is an end-to-end sports analytics and machine learning project that uses historical NBA team data to predict game outcomes, explain model behavior, simulate games and seasons, and generate future-facing win probabilities.

The project demonstrates a complete applied data science workflow:

```text
NBA Data
    ↓
Data Cleaning
    ↓
Feature Engineering
    ↓
Predictive Modeling
    ↓
Explainable AI
    ↓
Monte Carlo Simulation
    ↓
Live Prediction Pipeline
```

The broader goal is to develop a reusable framework for probabilistic forecasting and decision-support systems that can eventually be extended beyond sports analytics.

---

## Project Phases

### Phase 1 — Data Exploration

Historical NBA team and game data were collected and prepared for analysis.

Key work included:

* NBA data acquisition using `nba_api`
* Data cleaning and validation
* Dataset construction
* Missing-value analysis
* Exploratory visualization
* Statistical summaries of team performance

---

### Phase 2 — Feature Engineering & Analysis

Historical game data were transformed into pregame predictive features.

Features include:

* Home-court indicator
* Rest days
* Season win percentage
* Team game number
* Rolling five-game scoring statistics
* Rolling shooting percentages
* Rolling rebounds, assists, steals, blocks, and turnovers
* Rolling plus-minus
* Rolling win percentage
* Opponent rolling statistics
* Team-vs-opponent differential features

Examples:

```text
PLUS_MINUS_ROLL5_DIFF
WIN_PCT_ROLL5_DIFF
FG_PCT_ROLL5_DIFF
FG3_PCT_ROLL5_DIFF
REB_ROLL5_DIFF
AST_ROLL5_DIFF
TOV_ROLL5_DIFF
REST_DAYS_DIFF
```

Correlation and Variance Inflation Factor analysis were also used to evaluate feature redundancy and multicollinearity.

---

### Phase 3 — Predictive Modeling

Four classification algorithms were trained and evaluated using a chronological train-test split:

* Logistic Regression
* Decision Tree
* Random Forest
* XGBoost

#### Final Model Performance

| Model                         |  Accuracy | Precision |    Recall |  F1 Score |   ROC AUC |
| ----------------------------- | --------: | --------: | --------: | --------: | --------: |
| Logistic Regression           |     0.644 |     0.643 |     0.647 |     0.645 | **0.711** |
| Decision Tree                 |     0.550 |     0.550 |     0.547 |     0.549 |     0.550 |
| Decision Tree (`max_depth=5`) |     0.637 |     0.647 |     0.603 |     0.624 |     0.691 |
| Random Forest                 |     0.637 |     0.640 |     0.627 |     0.633 |     0.699 |
| Tuned Random Forest           | **0.647** | **0.648** |     0.643 |     0.646 |     0.710 |
| XGBoost                       | **0.647** |     0.645 | **0.656** | **0.650** |     0.699 |

The tuned Random Forest and XGBoost achieved the highest accuracy, while Logistic Regression achieved the strongest ROC AUC.

The results suggest that feature engineering captured much of the predictive signal, allowing the simpler Logistic Regression model to remain competitive with more complex ensemble methods.

---

### Phase 4 — Model Explainability

SHAP was used to understand both global model behavior and individual game predictions.

Analysis included:

* Global SHAP feature importance
* SHAP beeswarm plots
* Local waterfall explanations
* High-confidence correct prediction analysis
* High-confidence incorrect prediction analysis
* Prediction confidence analysis
* Probability calibration
* Brier Score comparison

The most influential features consistently included:

* `SEASON_WIN_PCT`
* `PLUS_MINUS_ROLL5_DIFF`
* `HOME_GAME`
* `OPP_PLUS_MINUS_ROLL5`
* Recent win-percentage differential

#### Probability Calibration

| Model               | Brier Score |
| ------------------- | ----------: |
| Logistic Regression |  **0.2172** |
| Random Forest       |      0.2185 |

Logistic Regression produced slightly better calibrated probabilities, supporting its use as the production probability model.

---

### Phase 5 — Monte Carlo Simulation

The prediction engine was extended from individual game predictions into repeated probabilistic simulations.

Simulation work included:

* Single-game Monte Carlo simulation
* Best-of-seven playoff series simulation
* Home/away-adjusted series simulation
* Model-generated matchup probabilities
* Common-date team snapshots
* Conference playoff simulation
* Full historical regular-season simulation
* Repeated full-season simulation

Repeated season simulations estimate:

* Average team wins
* Win-total standard deviation
* 10th-percentile outcomes
* 90th-percentile outcomes

The current season simulator replays the historical schedule using precomputed game-level probabilities. Simulated results affect simulated standings but do not dynamically update future rolling statistics.

---

### Phase 6 — Live Prediction Pipeline

The final core phase converts the historical analytics workflow into a future-facing prediction pipeline.

The pipeline includes:

* Retraining Logistic Regression using all completed historical data
* Maintaining the latest team-state information
* Constructing future matchup feature rows
* Calculating schedule-based rest days
* Tracking future team game numbers
* Generating home and away win probabilities
* Predicting multiple upcoming games
* Ranking predictions by model confidence
* Validating probability outputs
* Saving predictions for downstream applications
* Persisting the production model

Current outputs include:

```text
data/processed/latest_predictions.csv
models/logistic_regression_production.pkl
```

The pipeline currently uses manual schedule input so that API automation can be added later without changing the underlying prediction architecture.

---

## Notebook Reports

See [`notebooks/README.md`](notebooks/README.md) for the complete notebook index and pipeline details.

| Phase                        | Notebook                                                                         | HTML Report                                        |
| ---------------------------- | -------------------------------------------------------------------------------- | -------------------------------------------------- |
| 1 — Data Exploration         | [01_data_exploration.ipynb](notebooks/01_data_exploration.ipynb)                 | [View](notebooks/01_data_exploration.html)         |
| 2 — Feature Analysis         | [02_feature_analysis.ipynb](notebooks/02_feature_analysis.ipynb)                 | [View](notebooks/02_feature_analysis.html)         |
| 3 — Predictive Modeling      | [03_predictive_modeling.ipynb](notebooks/03_predictive_modeling.ipynb)           | [View](notebooks/03_predictive_modeling.html)      |
| 4 — Model Explainability     | [04_model_explainability.ipynb](notebooks/04_model_explainability.ipynb)         | [View](notebooks/04_model_explainability.html)     |
| 5 — Game Simulation          | [05_game_simulation.ipynb](notebooks/05_game_simulation.ipynb)                   | [View](notebooks/05_game_simulation.html)          |
| 6 — Live Prediction Pipeline | [06_live_prediction_pipeline.ipynb](notebooks/06_live_prediction_pipeline.ipynb) | [View](notebooks/06_live_prediction_pipeline.html) |

---

## Repository Structure

```text
nba-prediction-engine/
│
├── data/
│   ├── raw/
│   └── processed/
│
├── models/
│   └── logistic_regression_production.pkl
│
├── notebooks/
│   ├── 01_data_exploration.ipynb
│   ├── 02_feature_analysis.ipynb
│   ├── 03_predictive_modeling.ipynb
│   ├── 04_model_explainability.ipynb
│   ├── 05_game_simulation.ipynb
│   └── 06_live_prediction_pipeline.ipynb
│
├── src/
│   ├── data_collection/
│   └── data_processing/
│
├── docs/
│   └── roadmap/
│
├── dashboards/
│
├── .gitignore
├── README.md
└── requirements.txt
```

---

## Key Findings

* Season win percentage is one of the strongest indicators of future game outcomes.
* Recent team-vs-opponent point differential is consistently one of the most predictive engineered features.
* Home-court advantage produces a clear positive effect on win probability.
* Recent opponent strength materially affects predictions.
* Logistic Regression remained competitive with Random Forest and XGBoost despite being substantially simpler.
* Increasing model complexity did not automatically improve predictive performance.
* Probability calibration is important when predictions are presented as win probabilities rather than only binary classifications.
* Monte Carlo simulation allows game-level probabilities to be converted into distributions of season and playoff outcomes.
* High-confidence predictions can still fail, reinforcing the need to interpret model outputs probabilistically rather than deterministically.

---

## Technologies

### Data & Analysis

* Python
* Pandas
* NumPy
* Jupyter Notebook
* `nba_api`

### Machine Learning

* Scikit-learn
* Logistic Regression
* Decision Trees
* Random Forest
* XGBoost

### Explainability

* SHAP
* Probability calibration
* Brier Score analysis

### Visualization

* Matplotlib

### Simulation

* Monte Carlo simulation
* NumPy random number generation

### Development

* Git
* GitHub
* Cursor / VS Code
* Python virtual environment

---

## Running Locally

Clone the repository and activate a Python environment.

Install dependencies:

```bash
pip install -r requirements.txt
```

Launch the notebooks:

```bash
jupyter lab notebooks/
```

HTML notebook reports can also be opened directly without running Jupyter.

---

## Current Limitations

The current system does not yet include:

* Automated upcoming-schedule ingestion
* Automatic postgame feature updates
* Injuries and player availability
* Starting lineups
* Player-level predictive features
* Dynamic simulated team-state updates
* Live model retraining
* Automated deployment

The full-season simulator uses historical pregame feature states, so simulated outcomes do not currently modify the rolling features used in later simulated games.

---

## Future Development

Potential future extensions include:

* Automated NBA API data updates
* Daily upcoming-game prediction generation
* Injury and player availability integration
* Player-level modeling
* Elo or power-rating features
* Dynamic season simulation
* Score prediction
* Automated model retraining
* Interactive matchup dashboard
* SHAP explanations for live predictions
* Cloud deployment
* Prediction API

---

## Project Status

The core NBA Prediction Engine is complete.

The project currently supports:

**historical analysis → feature engineering → game prediction → model explainability → Monte Carlo simulation → future-facing prediction**

Remaining work primarily involves automation, richer data sources, and application deployment.
