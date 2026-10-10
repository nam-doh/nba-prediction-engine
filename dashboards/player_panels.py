"""Local player-input panels. Scenarios never alter model probabilities."""
from datetime import datetime, time, timedelta, timezone
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from src.data_collection.player_data.snapshots import SnapshotStore, redact_source_url
from src.modeling.player_inference import PlayerContextError


def utc_now():
    return datetime.now(timezone.utc)


def render_context(context):
    st.caption(f"Input mode: {context['mode']} · Observed at: {context['observed_at']} · Scenario game: {context['game_time']}")
    for warning in dict.fromkeys(context['warnings']):
        st.warning(warning)
    if context['players']:
        st.markdown('#### Roster and official availability')
        table = pd.DataFrame(context['players'])
        st.dataframe(table[['player_id','player_name','position','reported_status','availability','reason']], hide_index=True, width='stretch')
    contribution = context['contribution']
    if contribution:
        st.markdown('#### Conditional rotation contributions')
        st.dataframe(pd.DataFrame(contribution['players'])[['player_name','baseline_minutes','expected_minutes','strength',
                     'weighted_sample_minutes','official_status','scenario_override','availability_uncertain']], hide_index=True, width='stretch')
        st.caption(f"Observed rotation coverage: {contribution['rotation_coverage_minutes']:.1f}/240 minutes · "
                   f"Unallocated: {contribution['unallocated_minutes']:.1f} · Unknown-availability minutes: {contribution['unknown_minutes']:.1f}")
        st.json(contribution['features'], expanded=False)
    st.markdown('#### Source provenance')
    for source in context['sources']:
        st.caption(f"{source['provider']} / {source['dataset']} · Retrieved: {source['retrieved_at']} · "
                   f"Source-as-of: {source['source_as_of'] or 'not supplied'}")
        st.link_button(f"Open {source['dataset']} source", redact_source_url(source['source_url']))
    st.markdown('#### Unconfirmed player news')
    if not context['news']:
        st.caption('No eligible cached news. Absence of news does not confirm availability.')
    for article in context['news']:
        st.write(article['headline'])
        st.caption(f"UNCONFIRMED · {'STALE' if article['stale'] else 'recent article, not official status'} · "
                   f"Published: {article['published_at']} · Retrieved: {article['retrieved_at']}")
        st.write(f"Reported claim: {article['reported_availability'] or 'unknown'}")
        st.write(article['supporting_text'])
        st.link_button('Article source', redact_source_url(article['source_url']))


def render_team_panel(engine, team, *, store, game_time, observed_at, key):
    st.markdown(f'### {team}')
    try:
        context = engine.player_context(team, store=store, game_time=game_time, observed_at=observed_at)
        if context['contribution']:
            names = {p['player_id']:p['player_name'] for p in context['players']}
            selected = st.selectbox('Conditional player override', [None, *names],
                                    format_func=lambda p: 'No override' if p is None else names[p], key=f'{key}_player')
            if selected is not None:
                fraction = st.number_input('Fraction of observed rotation minutes', min_value=0., max_value=1.,
                                           value=1., step=.1, key=f'{key}_fraction')
                context = engine.player_context(team, store=store, game_time=game_time, observed_at=observed_at,
                                                scenarios={selected:fraction})
        render_context(context)
    except (PlayerContextError, ValueError, OSError) as exc:
        st.error(f'Player inputs unavailable: {exc}')
        st.warning('Source failure: availability remains unknown. No fallback player projection is shown.')


def render_player_panels(engine, teams):
    st.markdown('## Player inputs and scenarios')
    st.info('Scenario analysis only — not validated player-adjusted predictions. These inputs do not change the production probabilities.')
    st.caption('NBA.com source attribution · Private noncommercial local use only. No live network lookup occurs in this app.')
    observed = utc_now()
    scenario_date = st.date_input('Player scenario date (separate from model date)', value=observed.date()+timedelta(days=1), key='player_scenario_date')
    scenario_time = datetime.combine(scenario_date, time(23), tzinfo=timezone.utc).isoformat()
    st.caption('Scenario time is 23:00 UTC on the selected date; all same-date performance is excluded. Select an explicit date; this is not a scheduled matchup.')
    root = os.environ.get('NBA_PLAYER_SNAPSHOT_DIR', str(Path(__file__).resolve().parents[1] / 'data/snapshots/player_data'))
    store = SnapshotStore(root)
    st.caption(f'Local snapshot directory: {store.root}')
    for index, (column, team) in enumerate(zip(st.columns(len(teams)), teams)):
        with column:
            render_team_panel(engine, team, store=store, game_time=scenario_time,
                              observed_at=observed.isoformat(), key=f'player_team_{index}')
