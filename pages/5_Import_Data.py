"""Import historical match stats from Hudl / PlayHQ CSV or Excel exports."""
from pathlib import Path
import io
import datetime

import pandas as pd
import streamlit as st

from database import (
    init_db,
    get_teams,
    insert_match,
    insert_match_stats,
    add_team,
    get_existing_match_keys,
)

init_db()

# ── Page config & logo ──────────────────────────────────────────────────────
_LOGO_PATH = Path(__file__).parent.parent / "assets" / "logo.png"
_logo_bytes = _LOGO_PATH.read_bytes() if _LOGO_PATH.is_file() else None
try:
    from PIL import Image as _PILImage
    _page_icon = _PILImage.open(io.BytesIO(_logo_bytes)) if _logo_bytes else "📥"
except Exception:
    _page_icon = "📥"

st.set_page_config(page_title="Import Data", page_icon=_page_icon, layout="wide")

_tc, _lc = st.columns([5, 1])
with _tc:
    st.title("Import Match Data")
    st.caption("Upload a CSV or Excel export from Hudl, PlayHQ, or NRL and bulk-import historical stats.")
with _lc:
    if _logo_bytes:
        st.image(_logo_bytes, width=110)

# ── Alias dictionary ─────────────────────────────────────────────────────────
# Maps common column names (lower-stripped) → schema field name
ALIASES: dict[str, str] = {
    # Match identity
    "round": "round",
    "round number": "round",
    "rd": "round",
    "week": "round",
    "date": "match_date",
    "match date": "match_date",
    "game date": "match_date",
    "home": "home_team",
    "home team": "home_team",
    "home side": "home_team",
    "away": "away_team",
    "away team": "away_team",
    "away side": "away_team",
    "opponent": "away_team",
    "opposition": "away_team",
    "team": "home_team",
    "home score": "home_score",
    "home points": "home_score",
    "pts for": "home_score",
    "points for": "home_score",
    "away score": "away_score",
    "away points": "away_score",
    "pts against": "away_score",
    "points against": "away_score",
    "home ht": "home_halftime",
    "home halftime": "home_halftime",
    "ht home": "home_halftime",
    "away ht": "away_halftime",
    "away halftime": "away_halftime",
    "ht away": "away_halftime",
    # Stats
    "possession": "possession_pct",
    "possession %": "possession_pct",
    "possession pct": "possession_pct",
    "poss %": "possession_pct",
    "poss": "possession_pct",
    "sets": "sets_received",
    "sets received": "sets_received",
    "total sets": "sets_received",
    "completed sets": "sets_completed",
    "sets completed": "sets_completed",
    "set completion": "sets_completed",
    "errors": "errors",
    "handling errors": "errors",
    "tries": "tries",
    "tries scored": "tries",
    "try": "tries",
    "conversions": "conversions_made",
    "conversions made": "conversions_made",
    "goals made": "conversions_made",
    "conversions attempted": "conversions_attempted",
    "goal attempts": "conversions_attempted",
    "penalty goals": "penalty_goals",
    "penalty goal": "penalty_goals",
    "penalties goals": "penalty_goals",
    "field goals": "field_goals",
    "field goal": "field_goals",
    "metres gained": "metres_gained",
    "meters gained": "metres_gained",
    "running metres": "metres_gained",
    "run metres": "metres_gained",
    "metres": "metres_gained",
    "line breaks": "linebreaks",
    "linebreaks": "linebreaks",
    "line break": "linebreaks",
    "offloads": "offloads",
    "offload": "offloads",
    "tackles made": "tackles_made",
    "tackles": "tackles_made",
    "tackle": "tackles_made",
    "missed tackles": "missed_tackles",
    "missed tackle": "missed_tackles",
    "tackle misses": "missed_tackles",
    "line breaks conceded": "linebreaks_conceded",
    "linebreaks conceded": "linebreaks_conceded",
    "penalties": "penalties_conceded",
    "penalties conceded": "penalties_conceded",
    "penalty": "penalties_conceded",
    "set restarts conceded": "set_restarts_conceded",
    "set restart": "set_restarts_conceded",
    "40/20": "kicks_general_play",
    "kicks": "kicks_general_play",
    "kicks in general play": "kicks_general_play",
    "kick metres": "kick_metres",
    "kick meters": "kick_metres",
    "notes": "notes",
    "comments": "notes",
}

SCHEMA_FIELDS = [
    "round", "match_date", "home_team", "away_team",
    "home_score", "away_score", "home_halftime", "away_halftime",
    "possession_pct", "sets_received", "sets_completed", "errors",
    "tries", "conversions_made", "conversions_attempted", "penalty_goals",
    "field_goals", "metres_gained", "linebreaks", "offloads",
    "tackles_made", "missed_tackles", "linebreaks_conceded",
    "penalties_conceded", "set_restarts_conceded",
    "kicks_general_play", "kick_metres", "notes",
]

MATCH_FIELDS = {"round", "match_date", "home_team", "away_team",
                "home_score", "away_score", "home_halftime", "away_halftime"}
STAT_FIELDS = set(SCHEMA_FIELDS) - MATCH_FIELDS


def _auto_map(columns: list[str]) -> dict[str, str]:
    """Return {original_col: schema_field} using alias dict; unmapped → ''."""
    mapping = {}
    for col in columns:
        key = col.strip().lower()
        mapping[col] = ALIASES.get(key, "")
    return mapping


def _fuzzy_match_team(name: str, known_names: list[str]) -> str | None:
    """Return best fuzzy match from known_names, or None if below threshold."""
    try:
        from difflib import get_close_matches
        matches = get_close_matches(name, known_names, n=1, cutoff=0.6)
        return matches[0] if matches else None
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 1 — Upload
# ══════════════════════════════════════════════════════════════════════════════
st.header("Phase 1 — Upload File")

uploaded = st.file_uploader(
    "Upload Hudl / PlayHQ export",
    type=["csv", "xlsx", "xls"],
    help="Export stats from Hudl or PlayHQ, then upload here.",
)

if uploaded is None:
    st.info("Upload a CSV or Excel file to begin.")
    st.stop()

# Parse file
try:
    if uploaded.name.endswith(".csv"):
        raw_df = pd.read_csv(uploaded)
    else:
        raw_df = pd.read_excel(uploaded)
except Exception as e:
    st.error(f"Could not parse file: {e}")
    st.stop()

raw_df.columns = [str(c).strip() for c in raw_df.columns]

st.success(f"Loaded **{len(raw_df)} rows** and **{len(raw_df.columns)} columns**.")
st.subheader("Raw preview (first 5 rows)")
st.dataframe(raw_df.head(5), use_container_width=True)

fmt = st.radio(
    "File format",
    ["Wide — one row per match", "Long — one row per team per match"],
    help=(
        "**Wide**: each row has home AND away stats side-by-side.\n\n"
        "**Long**: each row has stats for one team; two rows per match."
    ),
)
is_wide = fmt.startswith("Wide")

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — Column Mapping
# ══════════════════════════════════════════════════════════════════════════════
st.divider()
st.header("Phase 2 — Column Mapping")

auto_map = _auto_map(raw_df.columns.tolist())
unmapped_cols = [c for c, v in auto_map.items() if v == ""]

if unmapped_cols:
    st.warning(
        f"{len(unmapped_cols)} column(s) weren't recognised automatically. "
        "Assign each to a schema field or leave as **Ignore**."
    )

OPTIONS = ["Ignore"] + SCHEMA_FIELDS

final_map: dict[str, str] = {}  # original_col → schema_field (or "" to ignore)

cols_per_row = 3
all_cols = raw_df.columns.tolist()

with st.expander("Column mapping (expand to review / edit)", expanded=bool(unmapped_cols)):
    grid_cols = st.columns(cols_per_row)
    for i, col in enumerate(all_cols):
        suggested = auto_map[col]
        default_idx = OPTIONS.index(suggested) if suggested in OPTIONS else 0
        with grid_cols[i % cols_per_row]:
            chosen = st.selectbox(
                label=f"`{col}`",
                options=OPTIONS,
                index=default_idx,
                key=f"map_{col}",
            )
            final_map[col] = "" if chosen == "Ignore" else chosen

# Check required fields
mapped_schema = set(final_map.values()) - {""}
missing_required = {"round", "home_team", "away_team"} - mapped_schema

if missing_required:
    st.error(
        f"Required fields not mapped: **{', '.join(sorted(missing_required))}**. "
        "Please fix the column mapping above before continuing."
    )
    st.stop()

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 3 — Preview & Import
# ══════════════════════════════════════════════════════════════════════════════
st.divider()
st.header("Phase 3 — Preview & Import")

# Build normalised DataFrame using the mapping
inv_map: dict[str, str] = {}  # schema_field → original_col (last wins for dupes)
for orig, schema in final_map.items():
    if schema:
        inv_map[schema] = orig

def _get(row, field):
    col = inv_map.get(field)
    if col is None:
        return None
    val = row.get(col)
    if pd.isna(val) if not isinstance(val, str) else (val.strip() == ""):
        return None
    return val


def _int(val, default=0):
    try:
        return int(float(val))
    except Exception:
        return default


def _float(val, default=50.0):
    try:
        return float(val)
    except Exception:
        return default


def _str(val, default=""):
    return str(val).strip() if val is not None else default


# Resolve teams
teams_df = get_teams()
known_names = teams_df["name"].tolist()
team_id_map = dict(zip(teams_df["name"], teams_df["id"]))

# Collect all team names seen in file
file_teams: set[str] = set()
for _, row in raw_df.iterrows():
    ht = _str(_get(row, "home_team"))
    at = _str(_get(row, "away_team"))
    if ht:
        file_teams.add(ht)
    if at:
        file_teams.add(at)

# Fuzzy-match unknowns
unknown_teams = [t for t in sorted(file_teams) if t not in team_id_map]
team_resolution: dict[str, str] = {}  # file_name → resolved_name

if unknown_teams:
    st.subheader("Unknown teams found in file")
    st.caption("These team names weren't found in the database. Select the correct match or keep the new name to auto-add.")
    res_cols = st.columns(min(len(unknown_teams), 3))
    for i, unk in enumerate(unknown_teams):
        fuzzy = _fuzzy_match_team(unk, known_names)
        opts = known_names + [f"Add as new: {unk}"]
        default_opt = fuzzy if fuzzy else f"Add as new: {unk}"
        default_idx = opts.index(default_opt) if default_opt in opts else len(opts) - 1
        with res_cols[i % len(res_cols)]:
            chosen = st.selectbox(
                f'"{unk}"',
                opts,
                index=default_idx,
                key=f"team_res_{unk}",
            )
            team_resolution[unk] = chosen
else:
    team_resolution = {}


def _resolve_team(name: str) -> str:
    if not name:
        return name
    if name in team_id_map:
        return name
    resolved = team_resolution.get(name, f"Add as new: {name}")
    if resolved.startswith("Add as new:"):
        return name  # will be added on import
    return resolved


# Build preview rows
existing_keys = get_existing_match_keys()
preview_rows = []

for _, row in raw_df.iterrows():
    round_val = _int(_get(row, "round"), 0)
    date_raw = _get(row, "match_date")
    try:
        match_date = str(pd.to_datetime(date_raw).date()) if date_raw else ""
    except Exception:
        match_date = _str(date_raw)

    home_raw = _str(_get(row, "home_team"))
    away_raw = _str(_get(row, "away_team"))
    home_name = _resolve_team(home_raw)
    away_name = _resolve_team(away_raw)

    # For duplicate check we need IDs; if team doesn't exist yet treat as 0
    home_id_check = team_id_map.get(home_name, 0)
    away_id_check = team_id_map.get(away_name, 0)
    is_duplicate = (round_val, home_id_check, away_id_check) in existing_keys

    preview_rows.append({
        "Round": round_val,
        "Date": match_date,
        "Home": home_name,
        "Away": away_name,
        "Home Score": _int(_get(row, "home_score")),
        "Away Score": _int(_get(row, "away_score")),
        "Duplicate?": "⚠️ Yes" if is_duplicate else "✅ No",
        # store originals for import
        "_home_raw": home_raw,
        "_away_raw": away_raw,
        "_row_data": row,
        "_duplicate": is_duplicate,
    })

display_df = pd.DataFrame([
    {k: v for k, v in r.items() if not k.startswith("_")}
    for r in preview_rows
])

st.subheader("Import preview")
st.dataframe(display_df, use_container_width=True)

dup_count = sum(1 for r in preview_rows if r["_duplicate"])
new_count = len(preview_rows) - dup_count

if dup_count:
    st.warning(
        f"**{dup_count} duplicate match(es)** detected (same round + teams already in DB). "
        "They will be **skipped** during import."
    )

if new_count == 0:
    st.info("No new matches to import.")
    st.stop()

st.info(f"**{new_count} new match(es)** ready to import.")

if st.button(f"Import {new_count} match(es)", type="primary"):
    # Refresh team_id_map (may have changed due to selectbox choices above)
    teams_df2 = get_teams()
    team_id_map2 = dict(zip(teams_df2["name"], teams_df2["id"]))

    def _get_or_add_team_id(name: str) -> int | None:
        if not name:
            return None
        if name in team_id_map2:
            return team_id_map2[name]
        # auto-add
        add_team(name)
        teams_df3 = get_teams()
        id_map3 = dict(zip(teams_df3["name"], teams_df3["id"]))
        team_id_map2.update(id_map3)
        return team_id_map2.get(name)

    success = 0
    errors = 0
    skipped = 0

    for r in preview_rows:
        if r["_duplicate"]:
            skipped += 1
            continue

        row = r["_row_data"]
        home_name = _resolve_team(r["_home_raw"])
        away_name = _resolve_team(r["_away_raw"])

        home_id = _get_or_add_team_id(home_name)
        away_id = _get_or_add_team_id(away_name)

        if home_id is None or away_id is None:
            errors += 1
            continue

        round_val = _int(_get(row, "round"), 0)
        date_raw = _get(row, "match_date")
        try:
            match_date = str(pd.to_datetime(date_raw).date()) if date_raw else ""
        except Exception:
            match_date = _str(date_raw)

        try:
            match_id = insert_match(
                round_num=round_val,
                match_date=match_date,
                home_team_id=home_id,
                away_team_id=away_id,
                home_score=_int(_get(row, "home_score")),
                away_score=_int(_get(row, "away_score")),
                home_halftime=_int(_get(row, "home_halftime")),
                away_halftime=_int(_get(row, "away_halftime")),
            )

            if is_wide:
                # Wide: one stats row per team — we have home stats directly
                home_stats = {f: _float(_get(row, f)) if f == "possession_pct"
                              else _int(_get(row, f)) if f != "notes"
                              else _str(_get(row, f))
                              for f in STAT_FIELDS}
                insert_match_stats(match_id, home_id, home_stats)
                # Away possession is complement if only one mapped
                away_stats = {f: (100.0 - home_stats.get("possession_pct", 50.0))
                              if f == "possession_pct" else 0
                              for f in STAT_FIELDS}
                away_stats["notes"] = ""
                insert_match_stats(match_id, away_id, away_stats)
            else:
                # Long: this row is for one team — use home_team as the team for stats
                stats = {f: _float(_get(row, f)) if f == "possession_pct"
                         else _int(_get(row, f)) if f != "notes"
                         else _str(_get(row, f))
                         for f in STAT_FIELDS}
                insert_match_stats(match_id, home_id, stats)

            success += 1
        except Exception as e:
            st.error(f"Row error (Round {round_val}): {e}")
            errors += 1

    # Summary
    if success:
        st.success(f"Imported **{success} match(es)** successfully.")
    if skipped:
        st.info(f"Skipped **{skipped} duplicate(s)**.")
    if errors:
        st.error(f"**{errors} row(s)** failed — see errors above.")
