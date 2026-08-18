# Notebook Reports

Analysis notebooks for the NBA Prediction Engine, organized by project phase. Each notebook has a **Table of Contents** at the top for quick navigation.

## Quick View (HTML)

Open these in any browser — no Jupyter required:

| Phase | Report | Description |
|-------|--------|-------------|
| 1 | [01_data_exploration.html](01_data_exploration.html) | NBA API data acquisition and cleaning |
| 2 | [02_feature_analysis.html](02_feature_analysis.html) | Correlations, distributions, and outlier analysis |
| 3 | [03_predictive_modeling.html](03_predictive_modeling.html) | Baseline classifiers and model comparison |
| 4 | [04_model_explainability.html](04_model_explainability.html) | SHAP analysis and probability calibration |
| 5 | [05_game_simulation.html](05_game_simulation.html) | Monte Carlo game and playoff simulations |

## Source Notebooks

| Phase | Notebook | Input Data |
|-------|----------|------------|
| 1 | [01_data_exploration.ipynb](01_data_exploration.ipynb) | NBA API |
| 2 | [02_feature_analysis.ipynb](02_feature_analysis.ipynb) | `data/processed/team_stats_clean.csv` |
| 3 | [03_predictive_modeling.ipynb](03_predictive_modeling.ipynb) | `data/processed/team_game_logs_clean.csv` |
| 4 | [04_model_explainability.ipynb](04_model_explainability.ipynb) | `data/processed/team_game_modeling.csv` |
| 5 | [05_game_simulation.ipynb](05_game_simulation.ipynb) | `data/processed/team_game_modeling.csv` |

## Running Locally

From the project root with the virtual environment activated:

```bash
jupyter lab notebooks/
```

To regenerate HTML exports after editing a notebook:

```bash
jupyter nbconvert --to html notebooks/NN_notebook_name.ipynb
```

## Pipeline Flow

```
Phase 1: Data Exploration
    └── team_stats_clean.csv, team_game_logs_clean.csv
            │
Phase 2: Feature Analysis
            │
Phase 3: Predictive Modeling
    └── team_game_modeling.csv
            │
Phase 4: Explainability ──► Phase 5: Simulation
```
