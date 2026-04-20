from pathlib import Path
import io
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from database import init_db, get_match_stats_full, get_matches

init_db()

_LOGO_PATH = Path(__file__).parent.parent / "assets" / "logo.png"
_logo_bytes = _LOGO_PATH.read_bytes() if _LOGO_PATH.is_file() else None
try:
    from PIL import Image as _PILImage
    _page_icon = _PILImage.open(io.BytesIO(_logo_bytes)) if _logo_bytes else "🐤"
except Exception:
    _page_icon = "🐤"

st.set_page_config(page_title="Competition Analysis", page_icon=_page_icon, layout="wide")

_tc, _lc = st.columns([5, 1])
with _tc:
    st.title("Competition Analysis — Find the Edges")
with _lc:
    if _logo_bytes:
        st.image(_logo_bytes, width=110)

stats = get_match_stats_full()
matches = get_matches()

if len(stats) == 0:
    st.info("No match data yet. Enter some matches first.")
    st.stop()

stats["completion_rate"] = (
    stats["sets_completed"] / stats["sets_received"].replace(0, pd.NA) * 100
).fillna(0).round(1)

stats["tackle_efficiency"] = (
    stats["tackles_made"] / (stats["tackles_made"] + stats["missed_tackles"]).replace(0, pd.NA) * 100
).fillna(0).round(1)

stats["conversion_rate"] = (
    stats["conversions_made"] / stats["conversions_attempted"].replace(0, pd.NA) * 100
).fillna(0).round(1)

st.subheader("Team Averages — All Competition")

team_avg = stats.groupby("team_name").agg(
    games=("match_id", "count"),
    completion_rate=("completion_rate", "mean"),
    errors=("errors", "mean"),
    missed_tackles=("missed_tackles", "mean"),
    tackle_efficiency=("tackle_efficiency", "mean"),
    penalties=("penalties_conceded", "mean"),
    linebreaks_for=("linebreaks", "mean"),
    linebreaks_against=("linebreaks_conceded", "mean"),
    metres=("metres_gained", "mean"),
    possession=("possession_pct", "mean"),
    set_restarts=("set_restarts_conceded", "mean"),
).round(1).reset_index()

def highlight_dapto(row):
    if row["team_name"] == "Dapto Canaries":
        return ["background-color: #FFD700; color: black"] * len(row)
    return [""] * len(row)

styled = team_avg.style.apply(highlight_dapto, axis=1).format(precision=1)
st.dataframe(styled, use_container_width=True, hide_index=True)

st.divider()

st.subheader("Head-to-Head Results")
if len(matches) > 0:
    h2h = matches[["round", "match_date", "home_team", "home_score", "away_score", "away_team"]].copy()
    h2h.columns = ["Round", "Date", "Home", "Home Score", "Away Score", "Away"]
    st.dataframe(h2h, use_container_width=True, hide_index=True)

st.divider()

st.subheader("Stat Comparisons Across the Competition")

metric_options = {
    "Completion Rate %": "completion_rate",
    "Errors per Game": "errors",
    "Missed Tackles per Game": "missed_tackles",
    "Tackle Efficiency %": "tackle_efficiency",
    "Penalties per Game": "penalties",
    "Linebreaks For per Game": "linebreaks_for",
    "Linebreaks Against per Game": "linebreaks_against",
    "Metres Gained per Game": "metres",
    "Possession %": "possession",
    "Set Restarts Conceded": "set_restarts",
}

selected = st.selectbox("Select metric", list(metric_options.keys()))
col = metric_options[selected]

team_avg_sorted = team_avg.sort_values(col, ascending=False)
colours = ["#FFD700" if t == "Dapto Canaries" else "#636EFA" for t in team_avg_sorted["team_name"]]

fig = go.Figure(go.Bar(
    x=team_avg_sorted["team_name"],
    y=team_avg_sorted[col],
    marker_color=colours,
    text=team_avg_sorted[col].round(1),
    textposition="outside",
))
fig.update_layout(
    title=f"{selected} — All Teams",
    xaxis_title="Team",
    yaxis_title=selected,
    showlegend=False,
)
st.plotly_chart(fig, use_container_width=True)
st.caption("🟡 Gold = Dapto Canaries")

st.divider()

st.subheader("🔍 Edge Finder — Where Dapto Ranks")

if "Dapto Canaries" in team_avg["team_name"].values:
    n_teams = len(team_avg)
    dapto_row = team_avg[team_avg["team_name"] == "Dapto Canaries"].iloc[0]

    edges = []
    for label, col in metric_options.items():
        if col not in team_avg.columns:
            continue
        val = dapto_row[col]
        if col in ["errors", "missed_tackles", "penalties", "linebreaks_against", "set_restarts"]:
            rank = (team_avg[col] > val).sum() + 1
        else:
            rank = (team_avg[col] > val).sum() + 1
        edges.append({"Metric": label, "Dapto Value": round(val, 1), "Rank": f"{rank}/{n_teams}"})

    edges_df = pd.DataFrame(edges)
    st.dataframe(edges_df, use_container_width=True, hide_index=True)
else:
    st.info("Dapto Canaries data not found in competition stats.")
