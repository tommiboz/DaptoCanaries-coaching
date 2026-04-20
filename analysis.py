"""
Analysis engine - computes averages, trends, and coaching edges from match stats.
"""
import database as db

# ── Targets & thresholds ──────────────────────────────────────────────────────

TARGETS = {
    'completion_pct':    80.0,   # set completion %
    'missed_tackle_pct': 10.0,   # % of all tackle attempts
    'penalties_game':     6.0,   # per game
    'errors_game':        5.0,   # handling errors per game
    'kick_metres_game':  300,    # metres per game
}

EDGE_THRESHOLDS = {
    'completion_pct_weak':      73.0,   # opp below this = exploit kick chase
    'completion_pct_strong':    85.0,   # opp above = be wary
    'missed_tackle_pct_weak':   15.0,   # opp above = attack direct
    'missed_tackle_pct_solid':   8.0,   # opp below = respect their D
    'penalties_high':            9.0,   # opp above = force them to penalties
    'errors_high':               7.0,   # opp above = pressure pays off
    'kick_metres_low':          200,    # opp below = territory dominance possible
}


# ── Core helpers ──────────────────────────────────────────────────────────────

def safe_div(a, b, default=0.0):
    return a / b if b else default

def completion_pct(row):
    return safe_div(row['completions'], row['sets_played']) * 100

def missed_tackle_pct(row):
    total = (row['tackles'] or 0) + (row['missed_tackles'] or 0)
    return safe_div(row['missed_tackles'] or 0, total) * 100

def score_for_team(match_row, team_id):
    if match_row['home_team_id'] == team_id:
        return match_row['home_score'], match_row['away_score']
    return match_row['away_score'], match_row['home_score']


# ── Team averages ─────────────────────────────────────────────────────────────

def team_averages(team_id, year=2026, last_n=None):
    rows = db.get_team_match_stats(team_id, year, last_n)
    if not rows:
        return None

    n = len(rows)
    totals = {
        'tries': 0, 'errors': 0, 'sets_played': 0, 'completions': 0,
        'tackles': 0, 'missed_tackles': 0, 'linebreaks': 0,
        'kick_metres': 0, 'forty_twenties': 0, 'penalties_conceded': 0,
        'possession_pct': 0, 'points_for': 0, 'points_against': 0,
    }
    for r in rows:
        totals['tries']              += r['tries'] or 0
        totals['errors']             += r['errors'] or 0
        totals['sets_played']        += r['sets_played'] or 0
        totals['completions']        += r['completions'] or 0
        totals['tackles']            += r['tackles'] or 0
        totals['missed_tackles']     += r['missed_tackles'] or 0
        totals['linebreaks']         += r['linebreaks'] or 0
        totals['kick_metres']        += r['kick_metres'] or 0
        totals['forty_twenties']     += r['forty_twenties'] or 0
        totals['penalties_conceded'] += r['penalties_conceded'] or 0
        totals['possession_pct']     += r['possession_pct'] or 50.0
        own, opp = score_for_team(r, team_id)
        totals['points_for']     += own or 0
        totals['points_against'] += opp or 0

    avgs = {k: round(v / n, 1) for k, v in totals.items()}
    avgs['games'] = n

    # Derived
    avgs['completion_pct']    = round(safe_div(totals['completions'], totals['sets_played']) * 100, 1)
    total_tackles = totals['tackles'] + totals['missed_tackles']
    avgs['missed_tackle_pct'] = round(safe_div(totals['missed_tackles'], total_tackles) * 100, 1)

    return avgs


def recent_form(team_id, year=2026, last_n=5):
    """Last N results as list of dicts with round, opponent, score, result."""
    rows = db.get_team_match_stats(team_id, year, last_n)
    form = []
    for r in rows:
        own, opp = score_for_team(r, team_id)
        opp_name = r['away_name'] if r['home_team_id'] == team_id else r['home_name']
        result = 'W' if own > opp else ('D' if own == opp else 'L')
        form.append({
            'round':    r['round'],
            'date':     r['date'],
            'opponent': opp_name,
            'score':    f"{own}-{opp}",
            'result':   result,
            'completion_pct':    round(completion_pct(r), 1),
            'missed_tackle_pct': round(missed_tackle_pct(r), 1),
            'errors':            r['errors'] or 0,
            'penalties':         r['penalties_conceded'] or 0,
            'tries':             r['tries'] or 0,
        })
    return form


# ── Edge finding ──────────────────────────────────────────────────────────────

def find_edges(opp_id, our_id=None, year=2026):
    """
    Returns a list of edge dicts: {category, title, detail, priority}.
    priority: 'HIGH' | 'MEDIUM' | 'LOW'
    """
    edges = []
    avgs = team_averages(opp_id, year)
    if not avgs or avgs['games'] == 0:
        return [{'category': 'DATA', 'title': 'No data yet',
                 'detail': 'Enter match stats to unlock edge analysis.',
                 'priority': 'LOW'}]

    cp = avgs['completion_pct']
    mtp = avgs['missed_tackle_pct']
    pen = avgs['penalties_conceded']
    err = avgs['errors']
    km  = avgs['kick_metres']

    # ── Completion rate ────────────────────────────────────────────────────
    if cp < EDGE_THRESHOLDS['completion_pct_weak']:
        edges.append({
            'category': 'ATTACK',
            'title':    f'Weak set completion ({cp:.0f}% avg)',
            'detail':   (f'Opposition complete only {cp:.0f}% of their sets '
                         f'(league target 80%). Apply pressure early in sets - '
                         f'rush line speed and close in on dummy half to force errors.'),
            'priority': 'HIGH',
        })
    elif cp > EDGE_THRESHOLDS['completion_pct_strong']:
        edges.append({
            'category': 'DEFENCE',
            'title':    f'Strong set completion ({cp:.0f}% avg)',
            'detail':   (f'They rarely give the ball up. Defensive shape must hold '
                         f'for long sets - discipline in line speed critical.'),
            'priority': 'MEDIUM',
        })

    # ── Missed tackles ─────────────────────────────────────────────────────
    if mtp > EDGE_THRESHOLDS['missed_tackle_pct_weak']:
        edges.append({
            'category': 'ATTACK',
            'title':    f'High missed tackle rate ({mtp:.0f}% avg)',
            'detail':   (f'They miss {mtp:.0f}% of attempted tackles. '
                         f'Target direct runners at the line - big men hitting straight '
                         f'with offload threat will exploit gaps. Play through the middle '
                         f'before shifting wide.'),
            'priority': 'HIGH',
        })
    elif mtp < EDGE_THRESHOLDS['missed_tackle_pct_solid']:
        edges.append({
            'category': 'ATTACK',
            'title':    f'Solid defence ({mtp:.0f}% miss rate)',
            'detail':   (f'They tackle well. Rely on structures, kick game, and set play '
                         f'to earn field position rather than forcing it.'),
            'priority': 'MEDIUM',
        })

    # ── Penalties ──────────────────────────────────────────────────────────
    if pen > EDGE_THRESHOLDS['penalties_high']:
        edges.append({
            'category': 'FIELD POSITION',
            'title':    f'High penalty count ({pen:.1f}/game avg)',
            'detail':   (f'They concede {pen:.1f} penalties per game. '
                         f'Force defensive work - kick for field position on repeat sets, '
                         f'earn territory and let their discipline cost them.'),
            'priority': 'HIGH',
        })

    # ── Errors ─────────────────────────────────────────────────────────────
    if err > EDGE_THRESHOLDS['errors_high']:
        edges.append({
            'category': 'DEFENCE',
            'title':    f'Handling errors ({err:.1f}/game avg)',
            'detail':   (f'They average {err:.1f} errors per game. '
                         f'Aggressive kick chase and rush defence on 5th tackle will '
                         f'compound pressure and force more mistakes.'),
            'priority': 'HIGH',
        })

    # ── Kick metres ────────────────────────────────────────────────────────
    if km < EDGE_THRESHOLDS['kick_metres_low']:
        edges.append({
            'category': 'TERRITORY',
            'title':    f'Limited kicking game ({km:.0f}m/game avg)',
            'detail':   (f'Their kicker averages only {km:.0f}m per game. '
                         f'Pin them in their own half - bomb and chase aggressively, '
                         f'they may struggle to relieve pressure.'),
            'priority': 'MEDIUM',
        })

    if not edges:
        edges.append({
            'category': 'GENERAL',
            'title':    'No clear statistical edges identified',
            'detail':   ('Opposition stats are well-rounded. Focus on set piece '
                         'execution, discipline, and forcing the contest in field position.'),
            'priority': 'LOW',
        })

    # ── Our weaknesses ─────────────────────────────────────────────────────
    if our_id:
        our = team_averages(our_id, year)
        if our and our['games'] > 0:
            if our['completion_pct'] < TARGETS['completion_pct']:
                edges.append({
                    'category': 'OUR FOCUS',
                    'title':    f'Our completion below target ({our["completion_pct"]:.0f}% vs 80% target)',
                    'detail':   ('Reduce handling errors in first two tackles. '
                                 'Simple ball to big men - no forcing.'),
                    'priority': 'HIGH',
                })
            if our['missed_tackle_pct'] > TARGETS['missed_tackle_pct']:
                edges.append({
                    'category': 'OUR FOCUS',
                    'title':    f'Our missed tackles above target ({our["missed_tackle_pct"]:.0f}% vs 10% target)',
                    'detail':   ('Review defensive line speed and body position. '
                                 'Prioritise first-up defence drills this week.'),
                    'priority': 'HIGH',
                })
            if our['penalties_conceded'] > TARGETS['penalties_game']:
                edges.append({
                    'category': 'OUR FOCUS',
                    'title':    f'Our penalty count ({our["penalties_conceded"]:.1f}/game vs target 6)',
                    'detail':   'Discipline review - late shots, offside, marker infringements.',
                    'priority': 'MEDIUM',
                })

    edges.sort(key=lambda e: {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}[e['priority']])
    return edges


# ── Post-game performance review ──────────────────────────────────────────────

def post_game_review(match_id, our_team_id):
    match = db.get_match_by_id(match_id)
    if not match:
        return None

    stats_rows = db.get_match_stats(match_id)
    our_stats  = next((r for r in stats_rows if r['team_id'] == our_team_id), None)
    opp_stats  = next((r for r in stats_rows if r['team_id'] != our_team_id), None)

    own_score, opp_score = score_for_team(match, our_team_id)
    result = 'WIN' if own_score > opp_score else ('DRAW' if own_score == opp_score else 'LOSS')

    flags = []
    positives = []

    if our_stats:
        cp  = completion_pct(our_stats)
        mtp = missed_tackle_pct(our_stats)
        pen = our_stats['penalties_conceded'] or 0
        err = our_stats['errors'] or 0

        if cp >= TARGETS['completion_pct']:
            positives.append(f"Set completion {cp:.0f}% - at or above {TARGETS['completion_pct']:.0f}% target.")
        else:
            flags.append(f"Set completion {cp:.0f}% - below {TARGETS['completion_pct']:.0f}% target. Errors: {err}.")

        if mtp <= TARGETS['missed_tackle_pct']:
            positives.append(f"Missed tackle rate {mtp:.0f}% - within {TARGETS['missed_tackle_pct']:.0f}% target.")
        else:
            flags.append(f"Missed tackle rate {mtp:.0f}% - above {TARGETS['missed_tackle_pct']:.0f}% target.")

        if pen <= TARGETS['penalties_game']:
            positives.append(f"Penalty count {pen} - at or below target of {int(TARGETS['penalties_game'])}.")
        else:
            flags.append(f"Penalty count {pen} - above target of {int(TARGETS['penalties_game'])}.")

    return {
        'result':    result,
        'our_score': own_score,
        'opp_score': opp_score,
        'our_stats': our_stats,
        'opp_stats': opp_stats,
        'positives': positives,
        'flags':     flags,
    }


# ── Top performers ────────────────────────────────────────────────────────────

def top_try_scorers(team_id, year=2026, top_n=5):
    rows = db.get_player_season_stats(team_id, year)
    return [r for r in rows if (r['tries'] or 0) > 0][:top_n]

def defensive_concerns(team_id, year=2026):
    """Players with high missed tackle rates (min 3 games)."""
    rows = db.get_player_season_stats(team_id, year)
    concerns = []
    for r in rows:
        if (r['games_played'] or 0) < 2:
            continue
        total = (r['tackles'] or 0) + (r['missed_tackles'] or 0)
        mtp = safe_div(r['missed_tackles'] or 0, total) * 100
        if mtp > 15 and total > 5:
            concerns.append({'name': r['player_name'], 'position': r['position'],
                             'missed_tackle_pct': round(mtp, 1), 'games': r['games_played']})
    concerns.sort(key=lambda x: -x['missed_tackle_pct'])
    return concerns
