from pathlib import Path
import io
import streamlit as st
from database import init_db, get_teams, insert_match, insert_match_stats, add_team, get_matches, delete_match
import datetime

init_db()

_LOGO_PATH = Path(__file__).parent.parent / "assets" / "logo.png"
_logo_bytes = _LOGO_PATH.read_bytes() if _LOGO_PATH.is_file() else None
try:
    from PIL import Image as _PILImage
    _page_icon = _PILImage.open(io.BytesIO(_logo_bytes)) if _logo_bytes else "🐤"
except Exception:
    _page_icon = "🐤"

st.set_page_config(page_title="Enter Match", page_icon=_page_icon, layout="wide")

_tc, _lc = st.columns([5, 1])
with _tc:
    st.title("Enter Match Stats")
with _lc:
    if _logo_bytes:
        st.image(_logo_bytes, width=110)

teams_df = get_teams()
team_names = teams_df["name"].tolist()
team_id_map = dict(zip(teams_df["name"], teams_df["id"]))

with st.expander("➕ Add a new team to the competition"):
    new_team = st.text_input("Team name")
    if st.button("Add Team") and new_team.strip():
        add_team(new_team.strip())
        st.success(f"{new_team} added!")
        st.rerun()

st.divider()

st.subheader("Match Details")
col1, col2, col3 = st.columns(3)
with col1:
    round_num = st.number_input("Round", min_value=1, max_value=30, value=1)
with col2:
    match_date = st.date_input("Date", value=datetime.date.today())
with col3:
    st.write("")

col_h, col_score, col_a = st.columns([2, 1, 2])
with col_h:
    home_team = st.selectbox("Home Team", team_names, index=0)
with col_score:
    st.write("")
    st.markdown("**vs**")
with col_a:
    away_team = st.selectbox("Away Team", team_names, index=1 if len(team_names) > 1 else 0)

col1, col2, col3, col4 = st.columns(4)
with col1:
    home_ht = st.number_input("Home Half-time", min_value=0, value=0)
with col2:
    away_ht = st.number_input("Away Half-time", min_value=0, value=0)
with col3:
    home_ft = st.number_input("Home Full-time", min_value=0, value=0)
with col4:
    away_ft = st.number_input("Away Full-time", min_value=0, value=0)

st.divider()


def stats_form(team_label):
    st.subheader(f"📊 {team_label} Stats")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Ball Control**")
        possession = st.slider(f"Possession %", 0, 100, 50, key=f"{team_label}_poss")
        sets_received = st.number_input("Sets Received", 0, 200, 0, key=f"{team_label}_sets_rx")
        sets_completed = st.number_input("Sets Completed", 0, 200, 0, key=f"{team_label}_sets_comp")
        errors = st.number_input("Errors", 0, 50, 0, key=f"{team_label}_errors")

        st.markdown("**Kick Game**")
        kicks_gp = st.number_input("Kicks in General Play", 0, 100, 0, key=f"{team_label}_kicks")
        kick_metres = st.number_input("Kick Metres", 0, 5000, 0, key=f"{team_label}_kick_m")

    with col2:
        st.markdown("**Attack**")
        tries = st.number_input("Tries", 0, 30, 0, key=f"{team_label}_tries")
        conv_att = st.number_input("Conversion Attempts", 0, 30, 0, key=f"{team_label}_conv_att")
        conv_made = st.number_input("Conversions Made", 0, 30, 0, key=f"{team_label}_conv_made")
        pen_goals = st.number_input("Penalty Goals", 0, 20, 0, key=f"{team_label}_pen_goals")
        field_goals = st.number_input("Field Goals", 0, 10, 0, key=f"{team_label}_fg")
        metres = st.number_input("Metres Gained", 0, 5000, 0, key=f"{team_label}_metres")
        linebreaks = st.number_input("Linebreaks", 0, 30, 0, key=f"{team_label}_lb")
        offloads = st.number_input("Offloads", 0, 50, 0, key=f"{team_label}_offloads")

        st.markdown("**Defence**")
        tackles = st.number_input("Tackles Made", 0, 500, 0, key=f"{team_label}_tackles")
        missed = st.number_input("Missed Tackles", 0, 100, 0, key=f"{team_label}_missed")
        lb_conc = st.number_input("Linebreaks Conceded", 0, 30, 0, key=f"{team_label}_lb_conc")

        st.markdown("**Discipline**")
        pens = st.number_input("Penalties Conceded", 0, 30, 0, key=f"{team_label}_pens")
        set_restarts = st.number_input("Set Restarts (6-again) Conceded", 0, 30, 0, key=f"{team_label}_sr")

    notes = st.text_area("Notes", key=f"{team_label}_notes", placeholder="Any tactical notes...")

    return {
        "possession_pct": possession,
        "sets_received": sets_received,
        "sets_completed": sets_completed,
        "errors": errors,
        "tries": tries,
        "conversions_made": conv_made,
        "conversions_attempted": conv_att,
        "penalty_goals": pen_goals,
        "field_goals": field_goals,
        "metres_gained": metres,
        "linebreaks": linebreaks,
        "offloads": offloads,
        "tackles_made": tackles,
        "missed_tackles": missed,
        "linebreaks_conceded": lb_conc,
        "penalties_conceded": pens,
        "set_restarts_conceded": set_restarts,
        "kicks_general_play": kicks_gp,
        "kick_metres": kick_metres,
        "notes": notes,
    }


tab1, tab2 = st.tabs([f"🏠 {home_team}", f"✈️ {away_team}"])
with tab1:
    home_stats = stats_form(home_team)
with tab2:
    away_stats = stats_form(away_team)

st.divider()

if st.button("💾 Save Match", type="primary", use_container_width=True):
    if home_team == away_team:
        st.error("Home and Away teams cannot be the same.")
    else:
        match_id = insert_match(
            round_num, str(match_date),
            team_id_map[home_team], team_id_map[away_team],
            home_ft, away_ft, home_ht, away_ht
        )
        insert_match_stats(match_id, team_id_map[home_team], home_stats)
        insert_match_stats(match_id, team_id_map[away_team], away_stats)
        st.success(f"✅ Round {round_num}: {home_team} {home_ft} – {away_ft} {away_team} saved!")

st.divider()
st.subheader("Delete a Match")
matches_df = get_matches()
if len(matches_df) > 0:
    match_options = {
        f"Round {r['round']} — {r['home_team']} {r['home_score']} vs {r['away_score']} {r['away_team']}": r["id"]
        for _, r in matches_df.iterrows()
    }
    to_delete = st.selectbox("Select match to delete", list(match_options.keys()))
    if st.button("🗑️ Delete Match", type="secondary"):
        delete_match(match_options[to_delete])
        st.success("Match deleted.")
        st.rerun()
else:
    st.info("No matches to delete.")
