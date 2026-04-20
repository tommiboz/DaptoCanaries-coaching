from pathlib import Path
import io
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from database import init_db, get_match_stats_full

init_db()

_LOGO_PATH = Path(__file__).parent.parent / "assets" / "logo.png"
_logo_bytes = _LOGO_PATH.read_bytes() if _LOGO_PATH.is_file() else None
try:
    from PIL import Image as _PILImage
    _page_icon = _PILImage.open(io.BytesIO(_logo_bytes)) if _logo_bytes else "🐤"
except Exception:
    _page_icon = "🐤"

st.set_page_config(page_title="Dapto Analysis", page_icon=_page_icon, layout="wide")

_tc, _lc = st.columns([5, 1])
with _tc:
    st.title("Dapto Canaries — Performance Analysis")
with _lc:
    if _logo_bytes:
        st.image(_logo_bytes, width=110)

stats = get_match_stats_full()
dapto = stats[stats["is_dapto"] == 1].copy()

if len(dapto) == 0:
    st.info("No Dapto stats yet. Enter some matches first.")
    st.stop()

dapto["completion_rate"] = (
    dapto["sets_completed"] / dapto["sets_received"].replace(0, pd.NA) * 100
).fillna(0).round(1)

dapto["tackle_efficiency"] = (
    dapto["tackles_made"] / (dapto["tackles_made"] + dapto["missed_tackles"]).replace(0, pd.NA) * 100
).fillna(0).round(1)

dapto["conversion_rate"] = (
    dapto["conversions_made"] / dapto["conversions_attempted"].replace(0, pd.NA) * 100
).fillna(0).round(1)

st.subheader("Season Averages")
col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("Completion Rate", f"{dapto['completion_rate'].mean():.1f}%")
col2.metric("Tackle Efficiency", f"{dapto['tackle_efficiency'].mean():.1f}%")
col3.metric("Errors / Game", f"{dapto['errors'].mean():.1f}")
col4.metric("Penalties / Game", f"{dapto['penalties_conceded'].mean():.1f}")
col5.metric("Linebreaks / Game", f"{dapto['linebreaks'].mean():.1f}")
col6.metric("Missed Tackles / Game", f"{dapto['missed_tackles'].mean():.1f}")

st.divider()

st.subheader("Trends by Round")
dapto_sorted = dapto.sort_values("round")

tab1, tab2, tab3, tab4 = st.tabs(["Ball Control", "Attack", "Defence", "Discipline"])

with tab1:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dapto_sorted["round"], y=dapto_sorted["completion_rate"],
                             mode="lines+markers", name="Completion Rate %"))
    fig.add_trace(go.Scatter(x=dapto_sorted["round"], y=dapto_sorted["errors"],
                             mode="lines+markers", name="Errors", yaxis="y2"))
    fig.update_layout(
        title="Completion Rate & Errors",
        xaxis_title="Round",
        yaxis=dict(title="Completion Rate %", range=[0, 100]),
        yaxis2=dict(title="Errors", overlaying="y", side="right"),
        legend=dict(orientation="h"),
    )
    st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        fig2 = px.bar(dapto_sorted, x="round", y="possession_pct",
                      title="Possession % by Round", labels={"possession_pct": "Possession %", "round": "Round"})
        fig2.add_hline(y=50, line_dash="dash", line_color="gray")
        st.plotly_chart(fig2, use_container_width=True)
    with col2:
        fig3 = px.bar(dapto_sorted, x="round", y="metres_gained",
                      title="Metres Gained by Round", labels={"metres_gained": "Metres", "round": "Round"})
        st.plotly_chart(fig3, use_container_width=True)

with tab2:
    col1, col2 = st.columns(2)
    with col1:
        fig = px.bar(dapto_sorted, x="round", y="tries",
                     title="Tries Scored by Round", labels={"tries": "Tries", "round": "Round"})
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = px.bar(dapto_sorted, x="round", y="linebreaks",
                     title="Linebreaks by Round", labels={"linebreaks": "Linebreaks", "round": "Round"})
        st.plotly_chart(fig, use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        fig = px.bar(dapto_sorted, x="round", y="offloads",
                     title="Offloads by Round", labels={"offloads": "Offloads", "round": "Round"})
        st.plotly_chart(fig, use_container_width=True)
    with col4:
        fig = px.line(dapto_sorted, x="round", y="conversion_rate",
                      title="Conversion Rate %", markers=True,
                      labels={"conversion_rate": "Conv %", "round": "Round"})
        fig.update_yaxes(range=[0, 100])
        st.plotly_chart(fig, use_container_width=True)

with tab3:
    col1, col2 = st.columns(2)
    with col1:
        fig = px.bar(dapto_sorted, x="round", y="missed_tackles",
                     title="Missed Tackles by Round", labels={"missed_tackles": "Missed Tackles", "round": "Round"})
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = px.line(dapto_sorted, x="round", y="tackle_efficiency",
                      title="Tackle Efficiency %", markers=True,
                      labels={"tackle_efficiency": "Efficiency %", "round": "Round"})
        fig.update_yaxes(range=[0, 100])
        st.plotly_chart(fig, use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        fig = px.bar(dapto_sorted, x="round", y="linebreaks_conceded",
                     title="Linebreaks Conceded by Round")
        st.plotly_chart(fig, use_container_width=True)
    with col4:
        pts_for = dapto_sorted.apply(
            lambda r: r["home_score"] if r["home_team"] == "Dapto Canaries" else r["away_score"], axis=1)
        pts_against = dapto_sorted.apply(
            lambda r: r["away_score"] if r["home_team"] == "Dapto Canaries" else r["home_score"], axis=1)
        fig = go.Figure()
        fig.add_trace(go.Bar(x=dapto_sorted["round"], y=pts_for, name="Points For"))
        fig.add_trace(go.Bar(x=dapto_sorted["round"], y=pts_against, name="Points Against"))
        fig.update_layout(title="Points For vs Against", barmode="group",
                          xaxis_title="Round", yaxis_title="Points")
        st.plotly_chart(fig, use_container_width=True)

with tab4:
    col1, col2 = st.columns(2)
    with col1:
        fig = px.bar(dapto_sorted, x="round", y="penalties_conceded",
                     title="Penalties Conceded by Round")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = px.bar(dapto_sorted, x="round", y="set_restarts_conceded",
                     title="Set Restarts (6-again) Conceded by Round")
        st.plotly_chart(fig, use_container_width=True)

st.divider()

st.subheader("⚠️ Identified Weaknesses")
weaknesses = []
avgs = dapto.mean(numeric_only=True)

if avgs.get("completion_rate", 100) < 75:
    weaknesses.append(f"Low completion rate: **{avgs['completion_rate']:.1f}%** (target >75%)")
if avgs.get("missed_tackles", 0) > 8:
    weaknesses.append(f"High missed tackles: **{avgs['missed_tackles']:.1f}/game** (target <8)")
if avgs.get("errors", 0) > 5:
    weaknesses.append(f"High errors: **{avgs['errors']:.1f}/game** (target <5)")
if avgs.get("penalties_conceded", 0) > 6:
    weaknesses.append(f"High penalty count: **{avgs['penalties_conceded']:.1f}/game** (target <6)")
if avgs.get("tackle_efficiency", 100) < 88:
    weaknesses.append(f"Low tackle efficiency: **{avgs['tackle_efficiency']:.1f}%** (target >88%)")

if weaknesses:
    for w in weaknesses:
        st.warning(w)
else:
    st.success("No major weaknesses flagged based on current data.")

st.divider()
st.subheader("Raw Data")
st.dataframe(dapto.drop(columns=["is_dapto"]), use_container_width=True, hide_index=True)
