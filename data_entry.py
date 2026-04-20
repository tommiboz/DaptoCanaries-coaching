"""
Interactive CLI for entering match stats, player stats, coaching notes, and Hudl links.
"""
import database as db

DAPTO = 'Dapto Canaries'


def _input_int(prompt, default=0, allow_blank=True):
    while True:
        val = input(f"  {prompt} [{default}]: ").strip()
        if val == '' and allow_blank:
            return default
        try:
            return int(val)
        except ValueError:
            print("  Enter a whole number.")


def _input_float(prompt, default=0.0):
    while True:
        val = input(f"  {prompt} [{default}]: ").strip()
        if val == '':
            return default
        try:
            return float(val)
        except ValueError:
            print("  Enter a number.")


def _pick_match(year=2026):
    matches = db.get_matches(year)
    if not matches:
        print("No matches in the draw. Add one first.")
        return None
    print("\n  Available matches:")
    for m in matches:
        played = '✓' if m['played'] else ' '
        score  = f"{m['home_score']}–{m['away_score']}" if m['played'] else 'not played'
        print(f"  [{m['id']}] Rnd {m['round']:2d}  {played}  {m['home_name']} vs {m['away_name']}  ({score})")
    while True:
        try:
            mid = int(input("  Enter match ID: ").strip())
            match = db.get_match_by_id(mid)
            if match:
                return match
            print("  Invalid ID.")
        except ValueError:
            print("  Enter a number.")


def _pick_team():
    teams = db.get_all_teams()
    print("\n  Teams:")
    for t in teams:
        print(f"  [{t['id']}] {t['name']}")
    while True:
        try:
            tid = int(input("  Enter team ID: ").strip())
            team = db.get_team_by_id(tid)
            if team:
                return team
            print("  Invalid ID.")
        except ValueError:
            print("  Enter a number.")


# ── Match result ──────────────────────────────────────────────────────────────

def enter_match_result():
    print("\n=== Enter Match Result ===")
    match = _pick_match()
    if not match:
        return

    print(f"\n  {match['home_name']} vs {match['away_name']}  (Round {match['round']})")
    home_score = _input_int(f"{match['home_name']} score", 0)
    away_score = _input_int(f"{match['away_name']} score", 0)

    db.save_match_result(match['id'], home_score, away_score)
    print(f"  Result saved: {match['home_name']} {home_score}–{away_score} {match['away_name']}")


# ── Team match stats ──────────────────────────────────────────────────────────

def enter_match_stats():
    print("\n=== Enter Team Match Stats ===")
    match = _pick_match()
    if not match:
        return

    print(f"\n  Match: {match['home_name']} vs {match['away_name']}  Round {match['round']}")
    print("  Enter stats for which team?")
    team = _pick_team()

    print(f"\n  --- {team['name']} stats ---")
    print("  (Press Enter to skip / use default 0)\n")

    stats = {
        'tries':              _input_int('Tries'),
        'conversions':        _input_int('Conversions'),
        'penalty_goals':      _input_int('Penalty goals'),
        'field_goals':        _input_int('Field goals'),
        'sets_played':        _input_int('Sets played', 35),
        'completions':        _input_int('Completed sets'),
        'errors':             _input_int('Errors (handling)'),
        'tackles':            _input_int('Tackles made'),
        'missed_tackles':     _input_int('Missed tackles'),
        'linebreaks':         _input_int('Linebreaks'),
        'kick_metres':        _input_int('Kick metres'),
        'forty_twenties':     _input_int('40/20s'),
        'penalties_conceded': _input_int('Penalties conceded'),
        'possession_pct':     _input_float('Possession %', 50.0),
    }

    db.save_match_stats(match['id'], team['id'], stats)
    print(f"  Stats saved for {team['name']}.")


# ── Player management ─────────────────────────────────────────────────────────

POSITIONS = ['1-FB', '2-RW', '3-RC', '4-LC', '5-LW', '6-5/8', '7-HB',
             '8-PR', '9-HK', '10-PR', '11-LRF', '12-RRF', '13-LK',
             '14-Res', '15-Res', '16-Res', '17-Res']

def manage_players():
    print("\n=== Manage Players ===")
    print("  1. View squad\n  2. Add player")
    choice = input("  Choice: ").strip()

    team = _pick_team()

    if choice == '1':
        players = db.get_players(team['id'])
        if not players:
            print(f"  No players recorded for {team['name']}.")
        for p in players:
            print(f"  #{p['jersey_num'] or '?'}  {p['name']}  ({p['position'] or '?'})")

    elif choice == '2':
        name = input("  Player name: ").strip()
        if not name:
            return
        print("  Positions: " + ', '.join(POSITIONS))
        position   = input("  Position (e.g. 9-HK): ").strip() or None
        jersey_num = _input_int('Jersey number', 0)
        db.add_player(team['id'], name, position, jersey_num if jersey_num else None)
        print(f"  Added {name} to {team['name']}.")


# ── Player match stats ────────────────────────────────────────────────────────

def enter_player_stats():
    print("\n=== Enter Player Match Stats ===")
    match = _pick_match()
    if not match:
        return

    print(f"\n  Match: {match['home_name']} vs {match['away_name']}  Round {match['round']}")
    team = _pick_team()
    players = db.get_players(team['id'])

    if not players:
        print(f"  No players in squad for {team['name']}. Add players first.")
        return

    print(f"\n  Entering player stats for {team['name']}")
    print("  (Press Enter to use default 0, type 'skip' to skip a player)\n")

    for p in players:
        label = f"#{p['jersey_num'] or '?'} {p['name']} ({p['position'] or '?'})"
        print(f"  --- {label} ---")
        skip = input("  Skip this player? (y/n) [n]: ").strip().lower()
        if skip == 'y':
            continue

        stats = {
            'tries':          _input_int('Tries'),
            'try_assists':    _input_int('Try assists'),
            'linebreaks':     _input_int('Linebreaks'),
            'offloads':       _input_int('Offloads'),
            'tackles':        _input_int('Tackles'),
            'missed_tackles': _input_int('Missed tackles'),
            'errors':         _input_int('Errors'),
            'minutes_played': _input_int('Minutes played', 80),
        }
        db.save_player_stats(match['id'], p['id'], stats)
        print(f"  Saved.\n")

    print(f"  Player stats entry complete.")


# ── Add match to draw ─────────────────────────────────────────────────────────

def add_match_to_draw():
    print("\n=== Add Match to Draw ===")
    year      = _input_int('Year', 2026)
    round_num = _input_int('Round number')
    date      = input("  Date (YYYY-MM-DD): ").strip() or None
    teams     = db.get_all_teams()
    print("\n  Teams:")
    for t in teams:
        print(f"  [{t['id']}] {t['name']}")
    home_id = _input_int('Home team ID')
    away_id = _input_int('Away team ID')
    venue   = input("  Venue: ").strip() or None

    home = db.get_team_by_id(home_id)
    away = db.get_team_by_id(away_id)
    if not home or not away:
        print("  Invalid team ID(s).")
        return

    mid = db.add_match(year, round_num, date, home['name'], away['name'], venue)
    if mid:
        print(f"  Match added (ID {mid}): {home['name']} vs {away['name']}  Round {round_num}")
    else:
        print("  Match already exists or teams not found.")


# ── Coaching notes ────────────────────────────────────────────────────────────

def add_coaching_note():
    print("\n=== Add Coaching Note ===")
    match = _pick_match()
    mid   = match['id'] if match else None

    note_types = ['pre-game', 'post-game', 'training', 'opposition', 'general']
    print("  Note type: " + ', '.join(note_types))
    note_type = input("  Type: ").strip() or 'general'
    print("  Enter note (blank line to finish):")
    lines = []
    while True:
        line = input("  > ")
        if line == '':
            break
        lines.append(line)
    content = '\n'.join(lines)
    if content:
        db.add_coaching_note(mid, note_type, content)
        print("  Note saved.")


# ── Hudl links ────────────────────────────────────────────────────────────────

def add_hudl_link():
    print("\n=== Add Hudl Video Link ===")
    match = _pick_match()
    if not match:
        return

    url         = input("  Hudl URL: ").strip()
    if not url:
        return
    description = input("  Description (e.g. 'Defensive set play round 3'): ").strip()
    clip_types  = ['attack', 'defence', 'set piece', 'error', 'highlight', 'opponent', 'other']
    print("  Clip type: " + ', '.join(clip_types))
    clip_type   = input("  Type: ").strip() or 'other'

    db.add_hudl_link(match['id'], url, description, clip_type)
    print("  Hudl link saved.")
