"""Referee Tagger — log referee decisions while watching match video."""
from pathlib import Path
import io
import streamlit as st
from database import (
    init_db, get_matches, get_referees, add_referee,
    insert_referee_event, get_referee_events, delete_referee_event,
)

init_db()

_LOGO_PATH = Path(__file__).parent.parent / "assets" / "logo.png"
_logo_bytes = _LOGO_PATH.read_bytes() if _LOGO_PATH.is_file() else None
try:
    from PIL import Image as _PILImage
    _page_icon = _PILImage.open(io.BytesIO(_logo_bytes)) if _logo_bytes else "🟡"
except Exception:
    _page_icon = "🟡"

st.set_page_config(page_title="Referee Tagger", page_icon=_page_icon, layout="wide")

_tc, _lc = st.columns([5, 1])
with _tc:
    st.title("Referee Tagger")
    st.caption("Log referee decisions while watching match video. Build a profile over the season.")
with _lc:
    if _logo_bytes:
        st.image(_logo_bytes, width=110)

# ── Constants ────────────────────────────────────────────────────────────────
PENALTY_TYPES = [
    "10m — not back far enough",
    "10m — encroaching early",
    "Holding down",
    "Ruck infringement",
    "Obstruction",
    "Late hit / crusher tackle",
    "Professional foul",
    "Offside — marker",
    "Offside — general",
    "Incorrect play-the-ball",
    "Dissent",
    "Sin bin",
    "Send off",
    "Other",
]

FIELD_ZONES = [
    "Own in-goal / 0-10m",
    "Own 10-20m",
    "Own 20-40m",
    "Midfield (40-60m)",
    "Opp 40-20m",
    "Opp 20-10m",
    "Opp 10m / in-goal",
]

TEAMS = ["Dapto Canaries", "Opponent", "Both / Neither"]

# ── Setup: referee + match selection ─────────────────────────────────────────
st.subheader("Setup")

col_ref, col_match = st.columns(2)

with col_ref:
    refs_df = get_referees()
    ref_names = refs_df["name"].tolist() if len(refs_df) > 0 else []

    with st.expander("Add new referee"):
        new_ref = st.text_input("Referee name", key="new_ref_name")
        if st.button("Add referee") and new_ref.strip():
            add_referee(new_ref.strip())
            st.success(f"Added {new_ref.strip()}")
            st.rerun()

    if not ref_names:
        st.warning("Add a referee above to start tagging.")
        st.stop()

    selected_ref = st.selectbox("Referee", ref_names)
    refs_df2 = get_referees()
    ref_id_map = dict(zip(refs_df2["name"], refs_df2["id"]))
    referee_id = ref_id_map[selected_ref]

with col_match:
    matches = get_matches()
    if len(matches) == 0:
        st.warning("No matches in the database. Enter matches first.")
        match_id = None
        match_label = "No match"
    else:
        match_labels = [
            f"Round {int(r['round'])} — {r['home_team']} vs {r['away_team']}"
            for _, r in matches.iterrows()
        ]
        selected_match = st.selectbox("Match", match_labels)
        midx = match_labels.index(selected_match)
        match_id = int(matches.iloc[midx]["id"])
        match_label = selected_match

st.divider()

# ── Event logger ─────────────────────────────────────────────────────────────
st.subheader("Log an Event")

tab_penalty, tab_letgo = st.tabs(["🟡 Penalty Called", "👁️ Let Go (should've been called)"])

def _log_form(key_prefix: str, was_called: int):
    with st.form(key=f"form_{key_prefix}"):
        c1, c2, c3 = st.columns(3)

        with c1:
            penalty_type = st.selectbox("Type", PENALTY_TYPES, key=f"{key_prefix}_type")
            team_penalised = st.selectbox(
                "Against which team" if was_called else "Which team benefited",
                TEAMS, key=f"{key_prefix}_team"
            )

        with c2:
            field_zone = st.selectbox("Field zone", FIELD_ZONES, key=f"{key_prefix}_zone")
            tackle_number = st.select_slider(
                "Tackle number", options=[1, 2, 3, 4, 5, 6, 0],
                value=0, key=f"{key_prefix}_tackle",
                help="0 = unknown / not applicable"
            )

        with c3:
            half = st.radio("Half", [1, 2], horizontal=True, key=f"{key_prefix}_half")
            game_minute = st.number_input(
                "Game minute", min_value=0, max_value=100, value=0,
                key=f"{key_prefix}_minute"
            )
            notes = st.text_input("Notes (optional)", key=f"{key_prefix}_notes")

        submitted = st.form_submit_button(
            "✅ Log Penalty" if was_called else "✅ Log Let Go",
            type="primary"
        )
        if submitted:
            if match_id is None:
                st.error("Select a match first.")
            else:
                insert_referee_event(
                    match_id=match_id,
                    referee_id=referee_id,
                    event_type="penalty" if was_called else "let_go",
                    penalty_type=penalty_type,
                    team_penalised=team_penalised,
                    field_zone=field_zone,
                    tackle_number=int(tackle_number),
                    game_minute=int(game_minute),
                    half=int(half),
                    was_called=was_called,
                    notes=notes,
                )
                st.success("Logged.")
                st.rerun()

with tab_penalty:
    st.caption("Use this every time the referee blows his whistle.")
    _log_form("penalty", was_called=1)

with tab_letgo:
    st.caption("Use this when you see an infringement the ref misses or ignores.")
    _log_form("letgo", was_called=0)

st.divider()

# ── Recent events for this match + referee ───────────────────────────────────
st.subheader(f"Events Logged — {selected_ref} | {match_label}")

events = get_referee_events(referee_id=referee_id)
if match_id:
    events = events[events["match_id"] == match_id]

if len(events) == 0:
    st.info("No events logged yet for this referee / match combination.")
else:
    display = events[[
        "id", "half", "game_minute", "event_type", "penalty_type",
        "team_penalised", "field_zone", "tackle_number", "notes"
    ]].copy()
    display.columns = [
        "ID", "Half", "Min", "Type", "Penalty Type",
        "Against", "Zone", "Tackle #", "Notes"
    ]
    display["Type"] = display["Type"].map({"penalty": "🟡 Penalty", "let_go": "👁️ Let Go"})
    st.dataframe(display, use_container_width=True, hide_index=True)

    st.caption("Delete a wrong entry:")
    del_id = st.number_input("Event ID to delete", min_value=0, value=0, step=1)
    if st.button("Delete event") and del_id > 0:
        delete_referee_event(int(del_id))
        st.success(f"Deleted event {del_id}.")
        st.rerun()
