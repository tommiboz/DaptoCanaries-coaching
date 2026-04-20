from pathlib import Path
import io
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from database import init_db, get_match_stats_full, get_teams

init_db()

_LOGO_PATH = Path(__file__).parent.parent / "assets" / "logo.png"
_logo_bytes = _LOGO_PATH.read_bytes() if _LOGO_PATH.is_file() else None
try:
    from PIL import Image as _PILImage
    _page_icon = _PILImage.open(io.BytesIO(_logo_bytes)) if _logo_bytes else "🐤"
except Exception:
    _page_icon = "🐤"

st.set_page_config(page_title="Scout Report", page_icon=_page_icon, layout="wide")

_tc, _lc = st.columns([5, 1])
with _tc:
    st.title("Opponent Scout Report")
with _lc:
    if _logo_bytes:
        st.image(_logo_bytes, width=110)

stats = get_match_stats_full()
teams_df = get_teams()
opp_teams = teams_df[teams_df["is_dapto"] == 0]["name"].tolist()

if len(stats) == 0:
    st.info("No match data yet. Enter some matches first.")
    st.stop()

if not opp_teams:
    st.info("No opponents found.")
    st.stop()

opponent = st.selectbox("Select Opponent", opp_teams)
opp_stats = stats[stats["team_name"] == opponent].copy()

if len(opp_stats) == 0:
    st.warning(f"No stats recorded for {opponent} yet.")
    st.stop()

opp_stats["completion_rate"] = (
    opp_stats["sets_completed"] / opp_stats["sets_received"].replace(0, pd.NA) * 100
).fillna(0).round(1)
opp_stats["tackle_efficiency"] = (
    opp_stats["tackles_made"] / (opp_stats["tackles_made"] + opp_stats["missed_tackles"]).replace(0, pd.NA) * 100
).fillna(0).round(1)

avgs = opp_stats.mean(numeric_only=True)

st.subheader(f"{opponent} — {len(opp_stats)} game(s) analysed")

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Completion Rate", f"{avgs.get('completion_rate', 0):.1f}%")
col2.metric("Errors / Game", f"{avgs.get('errors', 0):.1f}")
col3.metric("Missed Tackles / Game", f"{avgs.get('missed_tackles', 0):.1f}")
col4.metric("Penalties / Game", f"{avgs.get('penalties_conceded', 0):.1f}")
col5.metric("Linebreaks / Game", f"{avgs.get('linebreaks', 0):.1f}")

st.divider()

st.subheader("🎯 Exploit Opportunities (Their Weaknesses)")
exploits = []
if avgs.get("completion_rate", 100) < 75:
    exploits.append(f"**Poor completion rate** ({avgs['completion_rate']:.1f}%) — force errors with defensive pressure, chase kicks hard")
if avgs.get("missed_tackles", 0) > 8:
    exploits.append(f"**High missed tackles** ({avgs['missed_tackles']:.1f}/game) — run at their edges, use second-phase play")
if avgs.get("errors", 0) > 5:
    exploits.append(f"**Error-prone with ball** ({avgs['errors']:.1f}/game) — high defensive line speed to force mistakes")
if avgs.get("penalties_conceded", 0) > 6:
    exploits.append(f"**Penalty-prone** ({avgs['penalties_conceded']:.1f}/game) — contest at the ruck, force discipline issues")
if avgs.get("tackle_efficiency", 100) < 88:
    exploits.append(f"**Weak tackle efficiency** ({avgs.get('tackle_efficiency', 0):.1f}%) — target their D-line with offloads and late balls")
if avgs.get("set_restarts_conceded", 0) > 4:
    exploits.append(f"**Concedes set restarts** ({avgs['set_restarts_conceded']:.1f}/game) — draw 6-agains, maintain pressure with each set")

if exploits:
    for e in exploits:
        st.success(e)
else:
    st.info("Not enough data to flag specific weaknesses yet.")

st.divider()

st.subheader("⚠️ Watch Out For (Their Strengths)")
threats = []
if avgs.get("linebreaks", 0) > 3:
    threats.append(f"**Strong linebreak threat** ({avgs['linebreaks']:.1f}/game) — tighten defensive line, no gaps on edges")
if avgs.get("completion_rate", 0) > 80:
    threats.append(f"**High completion rate** ({avgs['completion_rate']:.1f}%) — strong ball control, they'll grind sets")
if avgs.get("offloads", 0) > 10:
    threats.append(f"**Heavy offload game** ({avgs['offloads']:.1f}/game) — wrap up the ball carrier, no lazy arm tackles")
if avgs.get("metres_gained", 0) > 1500:
    threats.append(f"**Big metres** ({avgs['metres_gained']:.0f}/game) — strong running side, set D from kick-off")

if threats:
    for t in threats:
        st.warning(t)
else:
    st.info("No standout threats flagged yet.")

st.divider()

st.subheader(f"{opponent} — Stats by Round")
opp_sorted = opp_stats.sort_values("round")

col1, col2 = st.columns(2)
with col1:
    fig = px.line(opp_sorted, x="round", y="completion_rate",
                  title="Completion Rate %", markers=True)
    fig.update_yaxes(range=[0, 100])
    st.plotly_chart(fig, use_container_width=True)
with col2:
    fig = px.bar(opp_sorted, x="round", y="errors", title="Errors by Round")
    st.plotly_chart(fig, use_container_width=True)

col3, col4 = st.columns(2)
with col3:
    fig = px.bar(opp_sorted, x="round", y="missed_tackles", title="Missed Tackles by Round")
    st.plotly_chart(fig, use_container_width=True)
with col4:
    fig = px.bar(opp_sorted, x="round", y="penalties_conceded", title="Penalties Conceded by Round")
    st.plotly_chart(fig, use_container_width=True)

st.divider()
st.subheader("Matchup — Dapto vs " + opponent)

dapto_stats = stats[stats["is_dapto"] == 1]
if len(dapto_stats) > 0:
    metrics_compare = {
        "Completion Rate %": "completion_rate",
        "Errors / Game": "errors",
        "Missed Tackles / Game": "missed_tackles",
        "Penalties / Game": "penalties_conceded",
        "Metres / Game": "metres_gained",
        "Linebreaks / Game": "linebreaks",
    }

    dapto_stats = dapto_stats.copy()
    dapto_stats["completion_rate"] = (
        dapto_stats["sets_completed"] / dapto_stats["sets_received"].replace(0, pd.NA) * 100
    ).fillna(0)

    d_avg = dapto_stats.mean(numeric_only=True)
    o_avg = opp_stats.mean(numeric_only=True)

    compare_rows = []
    for label, col in metrics_compare.items():
        compare_rows.append({
            "Metric": label,
            "Dapto": round(d_avg.get(col, 0), 1),
            opponent: round(o_avg.get(col, 0), 1),
        })
    compare_df = pd.DataFrame(compare_rows)
    st.dataframe(compare_df, use_container_width=True, hide_index=True)
else:
    st.info("Enter Dapto stats to see the matchup comparison.")

st.divider()
st.subheader("Notes on " + opponent)
for _, row in opp_sorted.iterrows():
    if row.get("notes"):
        st.markdown(f"**Round {int(row['round'])}:** {row['notes']}")
