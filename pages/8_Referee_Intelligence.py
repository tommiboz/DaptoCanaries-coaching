"""Referee Intelligence — profiles, tendencies and pre-game briefings."""
from pathlib import Path
import io
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from database import init_db, get_referees, get_referee_events

init_db()

_LOGO_PATH = Path(__file__).parent.parent / "assets" / "logo.png"
_logo_bytes = _LOGO_PATH.read_bytes() if _LOGO_PATH.is_file() else None
try:
    from PIL import Image as _PILImage
    _page_icon = _PILImage.open(io.BytesIO(_logo_bytes)) if _logo_bytes else "🟡"
except Exception:
    _page_icon = "🟡"

st.set_page_config(page_title="Referee Intelligence", page_icon=_page_icon, layout="wide")

_tc, _lc = st.columns([5, 1])
with _tc:
    st.title("Referee Intelligence")
    st.caption("Patterns, tendencies and pre-game briefings for every referee.")
with _lc:
    if _logo_bytes:
        st.image(_logo_bytes, width=110)

# ── Load data ────────────────────────────────────────────────────────────────
refs_df = get_referees()
if len(refs_df) == 0:
    st.info("No referees added yet. Go to Referee Tagger to add referees and log events.")
    st.stop()

ref_names = refs_df["name"].tolist()
selected_ref = st.selectbox("Select referee", ref_names)
ref_id = dict(zip(refs_df["name"], refs_df["id"]))[selected_ref]

all_events = get_referee_events(referee_id=ref_id)

if len(all_events) == 0:
    st.info(f"No events logged for {selected_ref} yet. Use the Referee Tagger page to log decisions.")
    st.stop()

penalties = all_events[all_events["event_type"] == "penalty"].copy()
let_go    = all_events[all_events["event_type"] == "let_go"].copy()
games_ref = all_events["match_id"].nunique()

st.divider()

# ── Summary metrics ──────────────────────────────────────────────────────────
st.subheader(f"{selected_ref} — {games_ref} game(s) on record")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Penalties Called", len(penalties))
c2.metric("Penalties / Game", f"{len(penalties)/games_ref:.1f}" if games_ref else "—")
c3.metric("Let Go (missed/ignored)", len(let_go))
c4.metric("Against Dapto", len(penalties[penalties["team_penalised"] == "Dapto Canaries"]) if len(penalties) else 0)
c5.metric("Against Opponent", len(penalties[penalties["team_penalised"] == "Opponent"]) if len(penalties) else 0)

st.divider()

# ── Pre-game briefing bullets ─────────────────────────────────────────────────
st.subheader("Pre-Game Briefing")
st.caption("What Paul needs to know before the game.")

bullets = []
warnings_ref = []

if len(penalties) > 0:
    # Most penalised type
    top_type = penalties["penalty_type"].value_counts()
    if len(top_type) > 0:
        top = top_type.index[0]
        count = top_type.iloc[0]
        pct = round(count / len(penalties) * 100)
        bullets.append(
            f"**Nitpicks most on '{top}'** — {count} of {len(penalties)} penalties ({pct}%). "
            "Make sure players know before kick-off."
        )

    # Penalty split Dapto vs opponent
    dapto_pen = len(penalties[penalties["team_penalised"] == "Dapto Canaries"])
    opp_pen   = len(penalties[penalties["team_penalised"] == "Opponent"])
    total_pen = dapto_pen + opp_pen
    if total_pen > 0:
        dapto_pct = round(dapto_pen / total_pen * 100)
        if dapto_pct > 60:
            warnings_ref.append(
                f"This ref penalises Dapto **{dapto_pct}% of the time** — stay disciplined, "
                "don't give him easy decisions."
            )
        elif dapto_pct < 40:
            bullets.append(
                f"This ref has penalised opponents **{100-dapto_pct}% of the time** — "
                "contest the ruck, force him to make calls."
            )

    # 10m enforcement
    ten_m = penalties[penalties["penalty_type"].str.contains("10m", na=False)]
    if len(ten_m) > 0:
        ten_m_pct = round(len(ten_m) / len(penalties) * 100)
        if ten_m_pct >= 20:
            bullets.append(
                f"**Strict on 10 metres** — {len(ten_m)} penalties for 10m issues ({ten_m_pct}%). "
                "Defenders must be disciplined getting back."
            )

    # Second half crackdown
    if "half" in penalties.columns:
        h2 = penalties[penalties["half"] == 2]
        h1 = penalties[penalties["half"] == 1]
        if len(h2) > len(h1) * 1.4:
            bullets.append(
                f"Gets stricter in the **second half** — {len(h2)} penalties vs {len(h1)} in first half. "
                "Discipline is critical when the game is on the line."
            )

    # Hotspot field zone
    if len(penalties) >= 3:
        top_zone = penalties["field_zone"].value_counts().index[0]
        zone_count = penalties["field_zone"].value_counts().iloc[0]
        bullets.append(
            f"Most active in **{top_zone}** — {zone_count} penalties there. "
            "Be extra careful in that zone."
        )

    # Tackle number hotspot
    tackle_pen = penalties[penalties["tackle_number"] > 0]
    if len(tackle_pen) >= 3:
        top_tackle = tackle_pen["tackle_number"].value_counts().index[0]
        t_count = tackle_pen["tackle_number"].value_counts().iloc[0]
        bullets.append(
            f"Penalises most on **tackle {top_tackle}** — {t_count} times. "
            "Defenders need to be square and onside at that point in the set."
        )

# Let-go patterns
if len(let_go) >= 2:
    top_letgo = let_go["penalty_type"].value_counts()
    if len(top_letgo) > 0:
        lg_type = top_letgo.index[0]
        lg_count = top_letgo.iloc[0]
        bullets.append(
            f"**Lets '{lg_type}' go** — seen {lg_count} times without a call. "
            "You can get away with this against him."
        )

b_col, w_col = st.columns(2)
with b_col:
    st.markdown("**Exploit / use to your advantage**")
    if bullets:
        for b in bullets:
            st.success(b)
    else:
        st.info("Not enough data yet — log more games.")
with w_col:
    st.markdown("**Watch out — stay disciplined**")
    if warnings_ref:
        for w in warnings_ref:
            st.warning(w)
    else:
        st.info("No specific warnings flagged yet.")

st.divider()

# ── Penalty type breakdown ────────────────────────────────────────────────────
if len(penalties) > 0:
    st.subheader("What He Penalises")
    col1, col2 = st.columns(2)

    with col1:
        type_counts = penalties["penalty_type"].value_counts().reset_index()
        type_counts.columns = ["Penalty Type", "Count"]
        fig = px.bar(
            type_counts, x="Count", y="Penalty Type", orientation="h",
            title="Penalties by Type", color="Count",
            color_continuous_scale="Reds",
        )
        fig.update_layout(showlegend=False, yaxis=dict(autorange="reversed"), height=400)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        if len(let_go) > 0:
            lg_counts = let_go["penalty_type"].value_counts().reset_index()
            lg_counts.columns = ["Infringement Type", "Count"]
            fig2 = px.bar(
                lg_counts, x="Count", y="Infringement Type", orientation="h",
                title="What He Lets Slide", color="Count",
                color_continuous_scale="Greens",
            )
            fig2.update_layout(showlegend=False, yaxis=dict(autorange="reversed"), height=400)
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No let-go events logged yet.")

    st.divider()

    # ── By field zone ─────────────────────────────────────────────────────────
    st.subheader("Where on the Field")
    zone_order = [
        "Own in-goal / 0-10m", "Own 10-20m", "Own 20-40m",
        "Midfield (40-60m)", "Opp 40-20m", "Opp 20-10m", "Opp 10m / in-goal",
    ]
    zone_counts = penalties["field_zone"].value_counts().reindex(zone_order, fill_value=0).reset_index()
    zone_counts.columns = ["Zone", "Penalties"]
    fig = px.bar(
        zone_counts, x="Zone", y="Penalties",
        title="Penalties by Field Zone",
        color="Penalties", color_continuous_scale="Oranges",
    )
    fig.update_layout(showlegend=False, height=320)
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── By tackle number ──────────────────────────────────────────────────────
    st.subheader("Which Tackle He Acts On")
    col3, col4 = st.columns(2)

    with col3:
        tackle_data = penalties[penalties["tackle_number"] > 0]
        if len(tackle_data) > 0:
            t_counts = tackle_data["tackle_number"].value_counts().sort_index().reset_index()
            t_counts.columns = ["Tackle #", "Penalties"]
            fig = px.bar(
                t_counts, x="Tackle #", y="Penalties",
                title="Penalties by Tackle Number",
                color="Penalties", color_continuous_scale="Blues",
            )
            fig.update_layout(showlegend=False, height=300)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Tackle number not recorded for penalties yet.")

    with col4:
        # By half
        if "half" in penalties.columns:
            half_counts = penalties["half"].value_counts().sort_index().reset_index()
            half_counts.columns = ["Half", "Penalties"]
            half_counts["Half"] = half_counts["Half"].map({1: "1st Half", 2: "2nd Half"})
            fig = px.pie(
                half_counts, names="Half", values="Penalties",
                title="Penalties by Half",
                color_discrete_sequence=["#636EFA", "#EF553B"],
            )
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── By game minute ────────────────────────────────────────────────────────
    st.subheader("When in the Game He Acts")
    min_data = penalties[penalties["game_minute"] > 0]
    if len(min_data) >= 3:
        fig = px.histogram(
            min_data, x="game_minute", nbins=16,
            title="Penalties by Game Minute",
            labels={"game_minute": "Game Minute", "count": "Penalties"},
            color_discrete_sequence=["#FF7F0E"],
        )
        fig.add_vline(x=40, line_dash="dash", line_color="gray", annotation_text="Half time")
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Log game minutes to see when in the match he is most active.")

    st.divider()

    # ── By team ───────────────────────────────────────────────────────────────
    st.subheader("Who He Penalises")
    team_counts = penalties["team_penalised"].value_counts().reset_index()
    team_counts.columns = ["Team", "Penalties"]
    fig = px.pie(
        team_counts, names="Team", values="Penalties",
        title="Penalty Split by Team",
        color_discrete_sequence=["#00CC96", "#EF553B", "#636EFA"],
    )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── 10m auto-measurement placeholder ─────────────────────────────────────
    st.subheader("10m Enforcement (Video Analysis)")
    st.info(
        "Automatic 10m measurements will appear here once match video has been processed "
        "through the video analysis tool with 10m tracking enabled. "
        "This will show exactly how far back each team gets and whether the referee "
        "is enforcing the 10 metres consistently."
    )

    st.divider()

    # ── Raw event log ─────────────────────────────────────────────────────────
    st.subheader("Full Event Log")
    display = all_events[[
        "round", "home_team", "away_team", "half", "game_minute",
        "event_type", "penalty_type", "team_penalised", "field_zone",
        "tackle_number", "notes"
    ]].copy()
    display.columns = [
        "Round", "Home", "Away", "Half", "Min",
        "Type", "Penalty Type", "Against", "Zone", "Tackle #", "Notes"
    ]
    display["Type"] = display["Type"].map({"penalty": "🟡 Penalty", "let_go": "👁️ Let Go"})
    st.dataframe(display, use_container_width=True, hide_index=True)
