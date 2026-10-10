"""Offline Streamlit interface for historical NBA matchup probabilities."""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import sys

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.modeling.inference import InferenceEngine, InferenceError
from dashboards.player_panels import render_player_panels


st.set_page_config(
    page_title="NBA Matchup Lab",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource(show_spinner=False)
def load_engine() -> InferenceEngine:
    """Load the read-only production model and feature export once per app process."""
    return InferenceEngine.from_paths()


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root { --navy: #101a36; --orange: #f47c20; --cream: #fff8ef; }
        .stApp { background: linear-gradient(135deg, #fffaf4 0%, #f4f6fb 55%, #edf2ff 100%); }
        .block-container { max-width: 1180px; padding-top: 2.5rem; }
        .hero { background: var(--navy); border-radius: 22px; padding: 2rem 2.25rem 1.8rem;
                color: white; box-shadow: 0 14px 36px rgba(16, 26, 54, .16); }
        .hero-kicker { color: #ffc27d; font-size: .78rem; font-weight: 800; letter-spacing: .16em;
                       text-transform: uppercase; margin-bottom: .6rem; }
        .hero h1 { margin: 0; font-size: clamp(2rem, 5vw, 3.6rem); line-height: 1.02; }
        .hero p { color: #dfe6ff; font-size: 1.05rem; margin: .9rem 0 0; max-width: 720px; }
        .section-card { background: rgba(255,255,255,.78); border: 1px solid rgba(16,26,54,.09);
                        border-radius: 18px; padding: 1.35rem 1.4rem; }
        .prob-card { background: white; border: 1px solid rgba(16,26,54,.1); border-radius: 18px;
                     padding: 1.3rem 1.4rem; box-shadow: 0 8px 22px rgba(16,26,54,.07); }
        .prob-label { color: #59627b; font-size: .82rem; font-weight: 800; letter-spacing: .08em;
                      text-transform: uppercase; }
        .prob-name { color: var(--navy); font-size: 1.2rem; font-weight: 800; margin-top: .3rem; }
        .prob-value { color: var(--orange); font-size: 2.7rem; font-weight: 900; line-height: 1.1; }
        .meta-pill { background: var(--cream); border-left: 4px solid var(--orange); border-radius: 8px;
                     padding: .7rem .9rem; margin: .35rem 0; color: var(--navy); }
        div[data-testid="stProgress"] > div > div { background-color: var(--orange); }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_prediction(result) -> None:
    st.markdown("### Model outlook")
    st.info(
        "Historical-data prediction · the model uses completed team-game statistics only. "
        "It is not a live injury or lineup projection."
    )
    left, right = st.columns(2)
    for column, team, role, probability in (
        (left, result.home_team, "Home team", result.home_win_probability),
        (right, result.away_team, "Away team", result.away_win_probability),
    ):
        with column:
            st.markdown('<div class="prob-card">', unsafe_allow_html=True)
            st.markdown(f'<div class="prob-label">{role}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="prob-name">{team}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="prob-value">{probability:.1%}</div>', unsafe_allow_html=True)
            st.progress(probability, text="Estimated win probability")
            rest_days = result.home_rest_days if role == "Home team" else result.away_rest_days
            state_date = result.home_state_date if role == "Home team" else result.away_state_date
            st.caption(f"{rest_days} rest day(s) · state through {state_date.date().isoformat()}")
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("### Prediction details")
    detail_left, detail_right = st.columns(2)
    with detail_left:
        st.markdown(
            f'<div class="meta-pill"><strong>Hypothetical game date</strong><br>{result.game_date.date().isoformat()}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="meta-pill"><strong>Source last-available date used</strong><br>{result.source_last_available_date.date().isoformat()}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="meta-pill"><strong>Static team-statistics cutoff</strong><br>{result.data_cutoff.date().isoformat()}</div>',
            unsafe_allow_html=True,
        )
    with detail_right:
        st.markdown(
            f'<div class="meta-pill"><strong>Model</strong><br>{result.model_name} · {result.feature_count} features</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="meta-pill"><strong>Artifact</strong><br>{result.model_artifact}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="meta-pill"><strong>Rest calculation assumption</strong><br>Explicit hypothetical elapsed-calendar-day overrides; no live schedule is fetched.</div>',
            unsafe_allow_html=True,
        )

    st.warning(
        "Injuries, lineups, trades, and player availability are not modeled in these probabilities. "
        "Player snapshots and conditional scenarios are displayed separately and never adjust this model."
    )


def main() -> None:
    _inject_styles()
    st.markdown(
        """
        <div class="hero">
          <div class="hero-kicker">NBA Prediction Engine · Offline model lab</div>
          <h1>Read the matchup.</h1>
          <p>Set the court, account for rest, and get a transparent probability split from the persisted production model.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")

    try:
        engine = load_engine()
    except InferenceError as exc:
        st.error(f"Prediction engine unavailable: {exc}")
        st.info("Check that the repository data and production model are present, then reload the app.")
        return

    with st.sidebar:
        st.markdown("## Matchup setup")
        st.caption("All inputs are local. No network calls or prediction files are written.")
        teams = engine.available_teams
        team_a = st.selectbox("Team A", teams, index=0, key="team_a")
        team_b = st.selectbox("Team B", teams, index=min(1, len(teams) - 1), key="team_b")
        home_team = st.radio("Home team", (team_a, team_b), index=0, key="home_team")
        away_team = team_b if home_team == team_a else team_a
        st.caption(f"Away team: **{away_team}**")
        st.markdown("#### Rest inputs")
        home_rest_days = st.number_input(
            "Home rest days",
            min_value=0,
            max_value=14,
            value=2,
            step=1,
            help="Hypothetical elapsed calendar days between games, matching the model's training convention.",
        )
        away_rest_days = st.number_input(
            "Away rest days",
            min_value=0,
            max_value=14,
            value=2,
            step=1,
            help="Hypothetical elapsed calendar days between games, matching the model's training convention.",
        )
        cutoff_date = engine.data_cutoff.date()
        game_date = st.date_input(
            "Hypothetical game date",
            value=cutoff_date + timedelta(days=1),
            min_value=cutoff_date + timedelta(days=1),
            help="The date must be after the static source cutoff. The wall clock is never used.",
        )
        predict_clicked = st.button("Predict matchup", type="primary", use_container_width=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown("### What this model knows")
    st.write(
        f"Team states are read from historical games through **{engine.data_cutoff.date().isoformat()}**. "
        "The selected hypothetical date and rest inputs are passed to the persisted scaler/classifier pipeline."
    )
    st.markdown("</div>", unsafe_allow_html=True)

    with st.expander("Player data and conditional scenarios", expanded=True):
        render_player_panels(engine, (home_team, away_team))

    if not predict_clicked:
        st.markdown("### Ready when you are")
        st.caption("Choose two different teams, select the home team, set rest days, and run the prediction.")
        return

    if team_a == team_b:
        st.error("Choose two different teams before predicting.")
        return
    if pd.Timestamp(game_date) <= engine.data_cutoff:
        st.error(
            f"Choose a hypothetical date after the static data cutoff ({engine.data_cutoff.date().isoformat()})."
        )
        return

    with st.spinner("Running the persisted model on as-of team states…"):
        try:
            result = engine.predict_matchup(
                home_team=home_team,
                away_team=away_team,
                game_date=game_date,
                home_rest_days=home_rest_days,
                away_rest_days=away_rest_days,
            )
        except InferenceError as exc:
            st.error(f"Prediction unavailable: {exc}")
            st.info("Adjust the matchup inputs or verify the historical source and model artifact.")
            return

    _render_prediction(result)


if __name__ == "__main__":
    main()
