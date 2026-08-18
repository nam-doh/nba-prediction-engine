# NBA Prediction Engine

## Project Overview

This project explores the relationship between NBA team statistics and team success through data analysis, visualization, and predictive modeling. The long-term objective is to build an explainable sports analytics platform capable of predicting team performance and eventually extending similar techniques to financial and market data.

## Project Phases

### Phase 1: Data Exploration

* Data acquisition using the NBA API
* Data cleaning and validation
* Dataset construction

### Phase 2: Feature Analysis

* Correlation analysis
* Scatter plot analysis
* Distribution analysis
* Outlier identification
* Feature selection

### Phase 3: Predictive Modeling

* Baseline predictive models (Logistic Regression, Decision Tree, Random Forest, XGBoost)
* Rolling feature engineering
* Train/test evaluation and model comparison

### Phase 4: Model Explainability

* SHAP global and local explanations
* Prediction confidence analysis
* Probability calibration

### Phase 5: Game Simulation

* Monte Carlo single-game simulation
* Best-of-seven series simulation
* Full playoff bracket forecasting

## Notebook Reports

See [`notebooks/README.md`](notebooks/README.md) for the full index.

| Phase | Notebook | HTML Report |
|-------|----------|-------------|
| 1 — Data Exploration | [01_data_exploration.ipynb](notebooks/01_data_exploration.ipynb) | [View](notebooks/01_data_exploration.html) |
| 2 — Feature Analysis | [02_feature_analysis.ipynb](notebooks/02_feature_analysis.ipynb) | [View](notebooks/02_feature_analysis.html) |
| 3 — Predictive Modeling | [03_predictive_modeling.ipynb](notebooks/03_predictive_modeling.ipynb) | [View](notebooks/03_predictive_modeling.html) |
| 4 — Model Explainability | [04_model_explainability.ipynb](notebooks/04_model_explainability.ipynb) | [View](notebooks/04_model_explainability.html) |
| 5 — Game Simulation | [05_game_simulation.ipynb](notebooks/05_game_simulation.ipynb) | [View](notebooks/05_game_simulation.html) |

## Key Findings

* Plus/minus exhibits the strongest relationship with winning percentage.
* Field goal percentage is more strongly associated with winning than three-point percentage.
* Rebounding and turnover management contribute meaningfully to team success.
* Several teams exhibit outlier behavior that cannot be explained by a single statistic.

## Future Development

* Reinforcement learning for strategy optimization
* Real-time prediction dashboard
* Integration of additional data sources (injuries, player-level stats)
