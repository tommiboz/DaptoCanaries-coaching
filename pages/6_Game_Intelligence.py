"""Game Intelligence — automatic pattern detection and competitive edges."""
from pathlib import Path
import io

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from database import init_db, get_match_stats_full, get_teams, get_matches

init_db()

# ── Page config & logo ───────────────────────────────────────────────────────
_LOGO_PATH = Path(__file__).parent.parent / "assets" / "logo.png"
_logo_bytes = _LOGO_PATH.read_bytes() if _LOGO_PATH.is_file() else None
try:
    from PIL import Image as _PILImage
    _page_icon = _PILImage.open(io.BytesIO(_logo_bytes)) if _logo_bytes else "🧠"
except Exception:
    _page_icon = "🧠"

st.set_page_config(page_title="Game Intelligence", page_icon=_page_icon, layout="wide")

_tc, _lc = st.columns([5, 1])
with _tc:
    st.title("Game Intelligence")
    st.caption("Automatic pattern detection — edges to exploit, weaknesses to fix.")
with _lc:
    if _logo_bytes:
        st.image(_logo_bytes, width=110)

# ── Load data ────────────────────────────────────────────────────────────────
stats = get_match_stats_full()
matches = get_matches()
teams_df = get_teams()

if len(stats) == 0:
    st.info("No match data yet. Import or enter matches first.")
    st.stop()

# Derived stats helper
def _add_derived(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["completion_rate"] = (
        df["sets_completed"] / df["sets_received"].replace(0, pd.NA) * 100
    ).fillna(0).round(1)
    df["tackle_efficiency"] = (
        df["tackles_made"] / (df["tackles_made"] + df["missed_tackles"]).replace(0, pd.NA) * 100
    ).fillna(0).round(1)
    df["conversion_rate"] = (
        df["conversions_made"] / df["conversions_attempted"].replace(0, pd.NA) * 100
    ).fillna(0).round(1)
    return df

stats = _add_derived(stats)
dapto = stats[stats["is_dapto"] == 1].copy()
opposition = stats[stats["is_dapto"] == 0].copy()

# Trend helper: +1 improving, -1 declining, 0 stable
def _trend(series: pd.Series, higher_is_better: bool = True) -> str:
    if len(series) < 2:
        return "—"
    recent = series.iloc[-1]
    earlier = series.iloc[:-1].mean()
    delta = recent - earlier
    threshold = series.std() * 0.3 if series.std() > 0 else 0.5
    if abs(delta) < threshold:
        return "→ Stable"
    if (delta > 0) == higher_is_better:
        return "↑ Improving"
    return "↓ Declining"

# ── Mode selector ────────────────────────────────────────────────────────────
mode = st.radio(
    "Select mode",
    ["Pre-Game Prep", "Post-Game Review", "Season Trends", "Competition Edges"],
    horizontal=True,
)

st.divider()

# ════════════════════════════════════════════════════════════════════════════
# PRE-GAME PREP
# ════════════════════════════════════════════════════════════════════════════
if mode == "Pre-Game Prep":
    st.header("Pre-Game Prep")

    opp_names = sorted(teams_df[teams_df["is_dapto"] == 0]["name"].tolist())
    if not opp_names:
        st.info("No opponents in the database yet.")
        st.stop()

    opponent = st.selectbox("Upcoming opponent", opp_names)
    opp_stats = opposition[opposition["team_name"] == opponent].sort_values("round")

    if len(opp_stats) == 0:
        st.warning(f"No stats recorded for {opponent} yet. Enter their matches first.")
        st.stop()

    avgs = opp_stats.mean(numeric_only=True)
    dapto_avgs = dapto.mean(numeric_only=True) if len(dapto) > 0 else pd.Series(dtype=float)

    st.subheader(f"vs {opponent} — {len(opp_stats)} game(s) on record")

    # Key metrics bar
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Their Completion %", f"{avgs.get('completion_rate', 0):.1f}%")
    c2.metric("Their Errors/Game", f"{avgs.get('errors', 0):.1f}")
    c3.metric("Their Missed Tackles", f"{avgs.get('missed_tackles', 0):.1f}")
    c4.metric("Their Penalties/Game", f"{avgs.get('penalties_conceded', 0):.1f}")
    c5.metric("Their Linebreaks/Game", f"{avgs.get('linebreaks', 0):.1f}")

    st.divider()

    col_attack, col_defend = st.columns(2)

    # ── ATTACK PLAN (their weaknesses = our opportunities)
    with col_attack:
        st.subheader("Attack Plan — Target These")
        bullets = []

        if avgs.get("missed_tackles", 0) > 8:
            bullets.append(
                f"Run at their edges — they miss **{avgs['missed_tackles']:.0f} tackles/game**. "
                "Second-phase play and quick play-the-balls will expose their D-line."
            )
        if avgs.get("completion_rate", 100) < 75:
            bullets.append(
                f"Force a kicking battle — their completion is only **{avgs['completion_rate']:.1f}%**. "
                "Field position wins here; make them play long sets."
            )
        if avgs.get("errors", 0) > 5:
            bullets.append(
                f"High defensive line speed — they handle **{avgs['errors']:.0f} errors/game**. "
                "Rush up off the line and force early decisions."
            )
        if avgs.get("penalties_conceded", 0) > 6:
            bullets.append(
                f"Contest at every ruck — they concede **{avgs['penalties_conceded']:.0f} penalties/game**. "
                "Make them play a man down; penalty goals are free points."
            )
        if avgs.get("set_restarts_conceded", 0) > 4:
            bullets.append(
                f"Push hard on completion sets — they give away **{avgs['set_restarts_conceded']:.0f} "
                "set restarts/game**. Extra sets = extra tries."
            )
        if avgs.get("tackle_efficiency", 100) < 86:
            bullets.append(
                f"Use offloads — their tackle efficiency is **{avgs['tackle_efficiency']:.1f}%**. "
                "Wrap-around plays and late balls will create line breaks."
            )

        if not bullets:
            st.info("No clear weaknesses yet — need more games on record for this opponent.")
        else:
            for b in bullets:
                st.success(b)

    # ── DEFENCE PLAN (their strengths = our threats)
    with col_defend:
        st.subheader("Defence Plan — Watch Out For")
        threats = []

        if avgs.get("linebreaks", 0) > 3:
            threats.append(
                f"Tighten the defensive line — they break **{avgs['linebreaks']:.0f} lines/game**. "
                "No gaps on the edges; communicate early."
            )
        if avgs.get("completion_rate", 0) > 82:
            threats.append(
                f"Expect long sets — their completion is **{avgs['completion_rate']:.1f}%**. "
                "Discipline in defence; don't give away penalties under pressure."
            )
        if avgs.get("offloads", 0) > 10:
            threats.append(
                f"Wrap up the ball carrier — they offload **{avgs['offloads']:.0f} times/game**. "
                "No lazy arm tackles; kill the ball."
            )
        if avgs.get("metres_gained", 0) > 1500:
            threats.append(
                f"Hard running side — **{avgs['metres_gained']:.0f}m/game**. "
                "Set the D-line from kick-off; don't let them build momentum."
            )
        if avgs.get("tries", 0) > 4:
            threats.append(
                f"Clinical finishers — **{avgs['tries']:.0f} tries/game**. "
                "No lazy D near the line; scramble defence must be sharp."
            )
        if avgs.get("kick_metres", 0) > 1200:
            threats.append(
                f"Strong kicking game — **{avgs['kick_metres']:.0f} kick metres/game**. "
                "Full-back needs clean hands under the high ball."
            )

        if not threats:
            st.info("No standout threats flagged — limited data for this opponent.")
        else:
            for t in threats:
                st.warning(t)

    st.divider()

    # ── Dapto vs opponent matchup table
    if len(dapto) > 0:
        st.subheader(f"Dapto vs {opponent} — Head to Head Stats")
        metrics = {
            "Completion %": "completion_rate",
            "Errors / Game": "errors",
            "Missed Tackles": "missed_tackles",
            "Penalties": "penalties_conceded",
            "Metres / Game": "metres_gained",
            "Linebreaks": "linebreaks",
            "Tries / Game": "tries",
            "Tackle Efficiency %": "tackle_efficiency",
        }
        rows = []
        for label, col in metrics.items():
            d_val = round(dapto_avgs.get(col, 0), 1)
            o_val = round(avgs.get(col, 0), 1)
            rows.append({"Metric": label, "Dapto": d_val, opponent: o_val})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ── Opponent recent trend chart
    st.divider()
    st.subheader(f"{opponent} — Recent Form")
    if len(opp_stats) >= 2:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=opp_stats["round"], y=opp_stats["completion_rate"],
            mode="lines+markers", name="Completion %"
        ))
        fig.add_trace(go.Scatter(
            x=opp_stats["round"], y=opp_stats["errors"],
            mode="lines+markers", name="Errors", yaxis="y2"
        ))
        fig.update_layout(
            xaxis_title="Round",
            yaxis=dict(title="Completion %", range=[0, 100]),
            yaxis2=dict(title="Errors", overlaying="y", side="right"),
            legend=dict(orientation="h"),
            height=320,
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Need at least 2 games to show trends.")


# ════════════════════════════════════════════════════════════════════════════
# POST-GAME REVIEW
# ════════════════════════════════════════════════════════════════════════════
elif mode == "Post-Game Review":
    st.header("Post-Game Review")

    if len(dapto) == 0:
        st.info("No Dapto stats recorded yet.")
        st.stop()

    dapto_sorted = dapto.sort_values("round", ascending=False)
    match_labels = [
        f"Round {int(r['round'])} — {r['home_team']} vs {r['away_team']}"
        for _, r in dapto_sorted.iterrows()
    ]

    selected_label = st.selectbox("Select match to review", match_labels)
    idx = match_labels.index(selected_label)
    match_row = dapto_sorted.iloc[idx]

    st.subheader(selected_label)

    # Result
    is_home = match_row["home_team"] == "Dapto Canaries"
    pts_for = match_row["home_score"] if is_home else match_row["away_score"]
    pts_against = match_row["away_score"] if is_home else match_row["home_score"]
    result = "WIN" if pts_for > pts_against else ("LOSS" if pts_for < pts_against else "DRAW")
    result_color = {"WIN": "green", "LOSS": "red", "DRAW": "orange"}[result]

    r1, r2, r3 = st.columns(3)
    r1.metric("Result", result)
    r2.metric("Score", f"{int(pts_for)} – {int(pts_against)}")
    r3.metric("Margin", f"{abs(int(pts_for) - int(pts_against))} pts")

    st.divider()

    # Season averages for comparison
    season_avgs = dapto.mean(numeric_only=True)

    st.subheader("This Game vs Season Average")

    key_stats = [
        ("Completion %", "completion_rate", True),
        ("Errors", "errors", False),
        ("Missed Tackles", "missed_tackles", False),
        ("Penalties", "penalties_conceded", False),
        ("Linebreaks", "linebreaks", True),
        ("Metres Gained", "metres_gained", True),
        ("Tries", "tries", True),
        ("Tackle Efficiency %", "tackle_efficiency", True),
    ]

    cols = st.columns(4)
    for i, (label, col, higher_better) in enumerate(key_stats):
        game_val = round(match_row.get(col, 0), 1)
        avg_val = round(season_avgs.get(col, 0), 1)
        delta = round(game_val - avg_val, 1)
        delta_str = f"{delta:+.1f} vs avg"
        cols[i % 4].metric(label, game_val, delta_str)

    st.divider()

    # Plain English verdict
    st.subheader("What the Stats Say")
    positives = []
    concerns = []

    cr = match_row.get("completion_rate", 0)
    avg_cr = season_avgs.get("completion_rate", 0)
    if cr >= 80:
        positives.append(f"Strong ball control — **{cr:.1f}% completion** rate.")
    elif cr < 72:
        concerns.append(f"Poor completion — only **{cr:.1f}%** (season avg {avg_cr:.1f}%). Fix the basics in training.")

    mt = match_row.get("missed_tackles", 0)
    avg_mt = season_avgs.get("missed_tackles", 0)
    if mt <= 5:
        positives.append(f"Excellent defence — only **{int(mt)} missed tackles**.")
    elif mt > 10:
        concerns.append(f"Defensive breakdown — **{int(mt)} missed tackles** (avg {avg_mt:.1f}). Tackle technique session needed.")

    err = match_row.get("errors", 0)
    if err <= 3:
        positives.append(f"Great discipline with the ball — only **{int(err)} errors**.")
    elif err > 6:
        concerns.append(f"Costly errors — **{int(err)}** in this game. Work on catch-and-pass under pressure.")

    pen = match_row.get("penalties_conceded", 0)
    if pen <= 4:
        positives.append(f"Very disciplined — only **{int(pen)} penalties** conceded.")
    elif pen > 7:
        concerns.append(f"Penalty count hurt the team — **{int(pen)} penalties**. Ruck discipline focus.")

    lb = match_row.get("linebreaks", 0)
    if lb >= 4:
        positives.append(f"Dangerous attacking side — **{int(lb)} linebreaks** created.")
    elif lb == 0 and result == "LOSS":
        concerns.append("No linebreaks created — struggled to break the defensive line. Work on edge plays.")

    if result == "WIN" and pts_for - pts_against >= 12:
        positives.append(f"Dominant performance — won by **{int(pts_for - pts_against)} points**.")
    elif result == "LOSS" and pts_against - pts_for >= 12:
        concerns.append(f"Heavy defeat by **{int(pts_against - pts_for)} points** — needs a full review.")

    c_pos, c_con = st.columns(2)
    with c_pos:
        st.markdown("**What worked**")
        if positives:
            for p in positives:
                st.success(p)
        else:
            st.info("No standout positives flagged.")
    with c_con:
        st.markdown("**Areas to fix**")
        if concerns:
            for c in concerns:
                st.warning(c)
        else:
            st.info("No major concerns flagged.")

    # Week on week comparison (if previous game exists)
    st.divider()
    if len(dapto_sorted) > 1:
        st.subheader("vs Previous Game")
        current_round = match_row["round"]
        prev_games = dapto_sorted[dapto_sorted["round"] < current_round]
        if len(prev_games) > 0:
            prev = prev_games.iloc[0]
            compare_rows = []
            for label, col, higher_better in key_stats:
                cur_val = round(match_row.get(col, 0), 1)
                prv_val = round(prev.get(col, 0), 1)
                delta = round(cur_val - prv_val, 1)
                direction = ""
                if delta != 0:
                    improved = (delta > 0) == higher_better
                    direction = "↑" if improved else "↓"
                compare_rows.append({
                    "Metric": label,
                    f"Round {int(current_round)}": cur_val,
                    f"Round {int(prev['round'])}": prv_val,
                    "Change": f"{direction} {delta:+.1f}",
                })
            st.dataframe(pd.DataFrame(compare_rows), use_container_width=True, hide_index=True)


# ════════════════════════════════════════════════════════════════════════════
# SEASON TRENDS
# ════════════════════════════════════════════════════════════════════════════
elif mode == "Season Trends":
    st.header("Dapto — Season Trends")

    if len(dapto) == 0:
        st.info("No Dapto stats recorded yet.")
        st.stop()

    dapto_sorted = dapto.sort_values("round")

    # Trend summary cards
    st.subheader("Where Dapto is Heading")
    trend_metrics = [
        ("Completion %", "completion_rate", True),
        ("Errors/Game", "errors", False),
        ("Missed Tackles", "missed_tackles", False),
        ("Penalties", "penalties_conceded", False),
        ("Linebreaks", "linebreaks", True),
        ("Tackle Efficiency %", "tackle_efficiency", True),
        ("Metres/Game", "metres_gained", True),
        ("Tries/Game", "tries", True),
    ]

    cols = st.columns(4)
    for i, (label, col, higher_better) in enumerate(trend_metrics):
        trend = _trend(dapto_sorted[col], higher_better)
        latest = round(dapto_sorted[col].iloc[-1], 1)
        avg = round(dapto_sorted[col].mean(), 1)
        color = "green" if "Improving" in trend else ("red" if "Declining" in trend else "gray")
        cols[i % 4].metric(
            label,
            f"{latest}",
            trend,
            delta_color="normal" if "Improving" in trend else ("inverse" if "Declining" in trend else "off"),
        )

    st.divider()

    # Rolling trend charts
    st.subheader("Key Metrics by Round")

    tab1, tab2, tab3 = st.tabs(["Ball Control", "Attack", "Defence"])

    with tab1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dapto_sorted["round"], y=dapto_sorted["completion_rate"],
            mode="lines+markers", name="Completion %", line=dict(color="green")
        ))
        fig.add_trace(go.Scatter(
            x=dapto_sorted["round"], y=dapto_sorted["errors"],
            mode="lines+markers", name="Errors", yaxis="y2", line=dict(color="red")
        ))
        fig.update_layout(
            xaxis_title="Round",
            yaxis=dict(title="Completion %", range=[0, 100]),
            yaxis2=dict(title="Errors", overlaying="y", side="right"),
            legend=dict(orientation="h"), height=350,
        )
        st.plotly_chart(fig, use_container_width=True)

        fig2 = px.bar(dapto_sorted, x="round", y="possession_pct",
                      title="Possession % by Round",
                      labels={"possession_pct": "Possession %", "round": "Round"})
        fig2.add_hline(y=50, line_dash="dash", line_color="gray", annotation_text="50%")
        st.plotly_chart(fig2, use_container_width=True)

    with tab2:
        col1, col2 = st.columns(2)
        with col1:
            fig = px.bar(dapto_sorted, x="round", y="tries", title="Tries Scored",
                         labels={"tries": "Tries", "round": "Round"})
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            fig = px.bar(dapto_sorted, x="round", y="linebreaks", title="Linebreaks",
                         labels={"linebreaks": "Linebreaks", "round": "Round"})
            st.plotly_chart(fig, use_container_width=True)
        col3, col4 = st.columns(2)
        with col3:
            fig = px.bar(dapto_sorted, x="round", y="metres_gained", title="Metres Gained",
                         labels={"metres_gained": "Metres", "round": "Round"})
            st.plotly_chart(fig, use_container_width=True)
        with col4:
            fig = px.bar(dapto_sorted, x="round", y="offloads", title="Offloads",
                         labels={"offloads": "Offloads", "round": "Round"})
            st.plotly_chart(fig, use_container_width=True)

    with tab3:
        col1, col2 = st.columns(2)
        with col1:
            fig = px.bar(dapto_sorted, x="round", y="missed_tackles", title="Missed Tackles",
                         labels={"missed_tackles": "Missed Tackles", "round": "Round"})
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            fig = px.line(dapto_sorted, x="round", y="tackle_efficiency",
                          title="Tackle Efficiency %", markers=True,
                          labels={"tackle_efficiency": "Efficiency %", "round": "Round"})
            fig.update_yaxes(range=[0, 100])
            st.plotly_chart(fig, use_container_width=True)
        col3, col4 = st.columns(2)
        with col3:
            fig = px.bar(dapto_sorted, x="round", y="penalties_conceded", title="Penalties Conceded",
                         labels={"penalties_conceded": "Penalties", "round": "Round"})
            st.plotly_chart(fig, use_container_width=True)
        with col4:
            fig = px.bar(dapto_sorted, x="round", y="linebreaks_conceded", title="Linebreaks Conceded",
                         labels={"linebreaks_conceded": "Linebreaks", "round": "Round"})
            st.plotly_chart(fig, use_container_width=True)

    # Points trend
    st.divider()
    st.subheader("Points For vs Against")
    pts_for = dapto_sorted.apply(
        lambda r: r["home_score"] if r["home_team"] == "Dapto Canaries" else r["away_score"], axis=1
    )
    pts_against = dapto_sorted.apply(
        lambda r: r["away_score"] if r["home_team"] == "Dapto Canaries" else r["home_score"], axis=1
    )
    fig = go.Figure()
    fig.add_trace(go.Bar(x=dapto_sorted["round"], y=pts_for, name="Points For", marker_color="green"))
    fig.add_trace(go.Bar(x=dapto_sorted["round"], y=pts_against, name="Points Against", marker_color="red"))
    fig.update_layout(barmode="group", xaxis_title="Round", yaxis_title="Points",
                      legend=dict(orientation="h"), height=320)
    st.plotly_chart(fig, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# COMPETITION EDGES
# ════════════════════════════════════════════════════════════════════════════
elif mode == "Competition Edges":
    st.header("Competition Edges")
    st.caption("How every team in the competition stacks up — find the easiest targets.")

    if len(opposition) == 0:
        st.info("No opposition stats yet. Import match data to see competition analysis.")
        st.stop()

    # Build team summary table
    team_rows = []
    for team_name, grp in opposition.groupby("team_name"):
        grp = _add_derived(grp)
        avgs = grp.mean(numeric_only=True)
        team_rows.append({
            "Team": team_name,
            "Games": len(grp),
            "Completion %": round(avgs.get("completion_rate", 0), 1),
            "Errors/Game": round(avgs.get("errors", 0), 1),
            "Missed Tackles": round(avgs.get("missed_tackles", 0), 1),
            "Penalties/Game": round(avgs.get("penalties_conceded", 0), 1),
            "Linebreaks/Game": round(avgs.get("linebreaks", 0), 1),
            "Metres/Game": round(avgs.get("metres_gained", 0), 0),
            "Tries/Game": round(avgs.get("tries", 0), 1),
        })

    comp_df = pd.DataFrame(team_rows).sort_values("Missed Tackles", ascending=False)

    # Vulnerability score (higher = more vulnerable / easier to attack)
    comp_df["Vuln. Score"] = (
        (comp_df["Missed Tackles"] / comp_df["Missed Tackles"].max() * 30) +
        (comp_df["Errors/Game"] / comp_df["Errors/Game"].max() * 25) +
        (comp_df["Penalties/Game"] / comp_df["Penalties/Game"].max() * 25) +
        ((100 - comp_df["Completion %"]) / 100 * 20)
    ).round(1)

    comp_df = comp_df.sort_values("Vuln. Score", ascending=False)

    st.subheader("Team Vulnerability Ranking")
    st.caption("Higher score = more exploitable weaknesses. Target the top of this list.")
    st.dataframe(comp_df, use_container_width=True, hide_index=True)

    st.divider()

    # Most vulnerable in each category
    st.subheader("Easiest Targets by Category")

    cats = st.columns(3)

    with cats[0]:
        st.markdown("**Worst Completion %**")
        worst_comp = comp_df.nsmallest(3, "Completion %")[["Team", "Completion %"]]
        for _, r in worst_comp.iterrows():
            st.warning(f"{r['Team']} — {r['Completion %']}%")

    with cats[1]:
        st.markdown("**Most Missed Tackles**")
        worst_mt = comp_df.nlargest(3, "Missed Tackles")[["Team", "Missed Tackles"]]
        for _, r in worst_mt.iterrows():
            st.warning(f"{r['Team']} — {r['Missed Tackles']}/game")

    with cats[2]:
        st.markdown("**Most Penalty-Prone**")
        worst_pen = comp_df.nlargest(3, "Penalties/Game")[["Team", "Penalties/Game"]]
        for _, r in worst_pen.iterrows():
            st.warning(f"{r['Team']} — {r['Penalties/Game']}/game")

    st.divider()

    # Competition radar — how Dapto compares to comp average
    if len(dapto) > 0:
        st.subheader("Dapto vs Competition Average")
        comp_avg = comp_df.mean(numeric_only=True)
        dapto_avgs = dapto.mean(numeric_only=True)

        radar_metrics = ["Completion %", "Errors/Game", "Missed Tackles",
                         "Penalties/Game", "Linebreaks/Game", "Tries/Game"]
        dapto_vals = [
            round(dapto_avgs.get("completion_rate", 0), 1),
            round(dapto_avgs.get("errors", 0), 1),
            round(dapto_avgs.get("missed_tackles", 0), 1),
            round(dapto_avgs.get("penalties_conceded", 0), 1),
            round(dapto_avgs.get("linebreaks", 0), 1),
            round(dapto_avgs.get("tries", 0), 1),
        ]
        comp_vals = [
            round(comp_avg.get("Completion %", 0), 1),
            round(comp_avg.get("Errors/Game", 0), 1),
            round(comp_avg.get("Missed Tackles", 0), 1),
            round(comp_avg.get("Penalties/Game", 0), 1),
            round(comp_avg.get("Linebreaks/Game", 0), 1),
            round(comp_avg.get("Tries/Game", 0), 1),
        ]

        compare_rows = [
            {"Metric": m, "Dapto": d, "Comp Avg": c}
            for m, d, c in zip(radar_metrics, dapto_vals, comp_vals)
        ]
        st.dataframe(pd.DataFrame(compare_rows), use_container_width=True, hide_index=True)

        # Plain English edge summary
        st.divider()
        st.subheader("Dapto's Competitive Edges")
        edges = []
        gaps = []

        if dapto_avgs.get("completion_rate", 0) > comp_avg.get("Completion %", 0) + 3:
            edges.append(f"Better ball control than the competition — {dapto_avgs['completion_rate']:.1f}% vs comp avg {comp_avg['Completion %']:.1f}%.")
        elif dapto_avgs.get("completion_rate", 0) < comp_avg.get("Completion %", 0) - 3:
            gaps.append(f"Completion rate below comp average — {dapto_avgs['completion_rate']:.1f}% vs {comp_avg['Completion %']:.1f}%.")

        if dapto_avgs.get("missed_tackles", 0) < comp_avg.get("Missed Tackles", 0) - 1:
            edges.append(f"Stronger defence than competition — {dapto_avgs['missed_tackles']:.1f} missed tackles vs comp avg {comp_avg['Missed Tackles']:.1f}.")
        elif dapto_avgs.get("missed_tackles", 0) > comp_avg.get("Missed Tackles", 0) + 1:
            gaps.append(f"Defensive liability — {dapto_avgs['missed_tackles']:.1f} missed tackles vs comp avg {comp_avg['Missed Tackles']:.1f}.")

        if dapto_avgs.get("linebreaks", 0) > comp_avg.get("Linebreaks/Game", 0) + 0.5:
            edges.append(f"More threatening attack — {dapto_avgs['linebreaks']:.1f} linebreaks/game vs comp avg {comp_avg['Linebreaks/Game']:.1f}.")

        if dapto_avgs.get("penalties_conceded", 0) < comp_avg.get("Penalties/Game", 0) - 1:
            edges.append(f"More disciplined than the competition — {dapto_avgs['penalties_conceded']:.1f} penalties vs comp avg {comp_avg['Penalties/Game']:.1f}.")
        elif dapto_avgs.get("penalties_conceded", 0) > comp_avg.get("Penalties/Game", 0) + 1:
            gaps.append(f"Penalty count is costing the team — {dapto_avgs['penalties_conceded']:.1f}/game vs comp avg {comp_avg['Penalties/Game']:.1f}.")

        c_edge, c_gap = st.columns(2)
        with c_edge:
            st.markdown("**Dapto advantages**")
            if edges:
                for e in edges:
                    st.success(e)
            else:
                st.info("No clear edges vs competition yet.")
        with c_gap:
            st.markdown("**Areas behind the competition**")
            if gaps:
                for g in gaps:
                    st.error(g)
            else:
                st.info("No major gaps vs competition.")
