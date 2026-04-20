import os
from pathlib import Path
import streamlit as st
from database import init_db, get_matches, get_match_stats_full, get_teams, get_video_session_count
import pandas as pd

_LOGO_PATH = Path(__file__).parent / "assets" / "logo.png"
_logo_bytes = _LOGO_PATH.read_bytes() if _LOGO_PATH.is_file() else None

try:
    from PIL import Image as _PILImage
    import io
    _page_icon = _PILImage.open(io.BytesIO(_logo_bytes)) if _logo_bytes else "🐤"
except Exception:
    _page_icon = "🐤"

st.set_page_config(
    page_title="Dapto Canaries Coaching Hub",
    page_icon=_page_icon,
    layout="wide",
)

init_db()

_title_col, _logo_col = st.columns([5, 1])
with _title_col:
    st.title("Dapto Canaries — Coaching Hub")
    st.caption("Illawarra District Rugby League | Season 2026")
with _logo_col:
    if _logo_bytes:
        st.image(_logo_bytes, width=110)

matches = get_matches()
stats = get_match_stats_full()

dapto_stats = stats[stats["is_dapto"] == 1]

video_sessions = get_video_session_count()

col1, col2, col3, col4, col5, col6 = st.columns(6)

col6.metric("Video Sessions", video_sessions, help="Match videos processed by the Video Analysis tool")

if len(matches) == 0:
    col1.metric("Rounds Played", 0)
    col2.metric("Wins", 0)
    col3.metric("Losses", 0)
    col4.metric("Avg Points For", "—")
    col5.metric("Avg Points Against", "—")
else:
    dapto_id = get_teams().loc[get_teams()["is_dapto"] == 1, "id"].values[0]
    wins = 0
    losses = 0
    draws = 0
    for _, row in matches.iterrows():
        if row["home_team"] == "Dapto Canaries":
            pts_for = row["home_score"]
            pts_against = row["away_score"]
        elif row["away_team"] == "Dapto Canaries":
            pts_for = row["away_score"]
            pts_against = row["home_score"]
        else:
            continue
        if pts_for > pts_against:
            wins += 1
        elif pts_for < pts_against:
            losses += 1
        else:
            draws += 1

    rounds_played = wins + losses + draws
    col1.metric("Rounds Played", rounds_played)
    col2.metric("Wins", wins)
    col3.metric("Losses", losses)
    avg_for = (matches.apply(
        lambda r: r["home_score"] if r["home_team"] == "Dapto Canaries" else r["away_score"], axis=1
    ).mean())
    avg_against = (matches.apply(
        lambda r: r["away_score"] if r["home_team"] == "Dapto Canaries" else r["home_score"], axis=1
    ).mean())
    col4.metric("Avg Pts For", f"{avg_for:.1f}" if rounds_played else "—")
    col5.metric("Avg Pts Against", f"{avg_against:.1f}" if rounds_played else "—")

st.divider()

st.subheader("Recent Results")
if len(matches) == 0:
    st.info("No matches recorded yet. Head to **Enter Match** to add your first game.")
else:
    display = matches[["round", "match_date", "home_team", "home_score",
                        "away_score", "away_team"]].copy()
    display.columns = ["Round", "Date", "Home", "Home Score", "Away Score", "Away"]
    st.dataframe(display, use_container_width=True, hide_index=True)

st.divider()
st.caption("Navigate using the sidebar → Enter Match | Dapto Analysis | Competition Analysis | Scout Report")
