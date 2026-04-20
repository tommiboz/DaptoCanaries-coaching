"""
PDF report generation - pre-game opposition analysis and post-game review.
Uses fpdf2.
"""
import os
from datetime import datetime
from fpdf import FPDF

import database as db
import analysis as an

# ── Colours (Dapto Canaries: yellow & black) ──────────────────────────────────
C_BLACK      = (0,   0,   0)
C_YELLOW     = (255, 210, 0)
C_DARK       = (30,  30,  30)
C_GREY_BG    = (245, 245, 245)
C_GREY_LINE  = (200, 200, 200)
C_WHITE      = (255, 255, 255)
C_RED        = (200, 40,  40)
C_GREEN      = (40,  140, 60)
C_ORANGE     = (220, 120, 0)

PRIORITY_COLOUR = {
    'HIGH':   C_RED,
    'MEDIUM': C_ORANGE,
    'LOW':    C_GREEN,
}

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reports')
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ── Base PDF class ────────────────────────────────────────────────────────────

class CoachingPDF(FPDF):
    def __init__(self, title, subtitle=''):
        super().__init__()
        self.report_title    = title
        self.report_subtitle = subtitle
        self.set_margins(15, 15, 15)
        self.set_auto_page_break(True, 20)

    def header(self):
        # Yellow banner
        self.set_fill_color(*C_YELLOW)
        self.rect(0, 0, 210, 22, 'F')
        self.set_fill_color(*C_BLACK)
        self.rect(0, 22, 210, 3, 'F')

        self.set_font('Helvetica', 'B', 14)
        self.set_text_color(*C_BLACK)
        self.set_xy(15, 5)
        self.cell(0, 8, 'DAPTO CANARIES  |  HARRIGAN CUP 2026', ln=False)

        self.set_font('Helvetica', '', 8)
        self.set_xy(15, 13)
        self.cell(0, 5, self.report_title, ln=False)

        self.set_xy(0, 28)

    def footer(self):
        self.set_y(-13)
        self.set_fill_color(*C_BLACK)
        self.rect(0, self.get_y(), 210, 13, 'F')
        self.set_font('Helvetica', '', 7)
        self.set_text_color(*C_YELLOW)
        self.cell(0, 13,
                  f'Dapto Canaries Coaching Staff  |  Generated {datetime.now().strftime("%d %b %Y %H:%M")}  |  CONFIDENTIAL',
                  align='C')
        self.set_text_color(*C_BLACK)

    # ── Helpers ───────────────────────────────────────────────────────────

    def section_heading(self, text):
        self.ln(4)
        self.set_fill_color(*C_BLACK)
        self.set_text_color(*C_YELLOW)
        self.set_font('Helvetica', 'B', 10)
        self.cell(0, 7, f'  {text.upper()}', ln=True, fill=True)
        self.set_text_color(*C_BLACK)
        self.ln(2)

    def sub_heading(self, text):
        self.set_font('Helvetica', 'B', 9)
        self.set_text_color(*C_DARK)
        self.cell(0, 6, text, ln=True)
        self.set_text_color(*C_BLACK)

    def body(self, text, size=9):
        self.set_font('Helvetica', '', size)
        self.set_text_color(*C_DARK)
        w = self.w - self.l_margin - self.r_margin
        self.multi_cell(w, 5, text)
        self.set_text_color(*C_BLACK)

    def kv(self, label, value, value_colour=None):
        self.set_font('Helvetica', 'B', 9)
        self.cell(55, 6, label + ':', ln=False)
        self.set_font('Helvetica', '', 9)
        if value_colour:
            self.set_text_color(*value_colour)
        self.cell(0, 6, str(value), ln=True)
        self.set_text_color(*C_BLACK)

    def stat_bar(self, label, value, target, unit='', higher_is_better=True):
        """Single stat row with a visual bar."""
        w_total = self.w - self.l_margin - self.r_margin
        w_label = 60
        w_bar   = w_total - w_label - 20

        good = (higher_is_better and value >= target) or (not higher_is_better and value <= target)
        colour = C_GREEN if good else C_RED
        fill_w = min(w_bar, max(2, w_bar * min(value / max(target, 1), 1.5)))

        y = self.get_y()
        self.set_font('Helvetica', '', 8)
        self.set_xy(self.l_margin, y)
        self.cell(w_label, 6, label, ln=False)

        # Bar background
        self.set_fill_color(*C_GREY_LINE)
        self.rect(self.l_margin + w_label, y + 1, w_bar, 4, 'F')
        # Bar fill
        self.set_fill_color(*colour)
        self.rect(self.l_margin + w_label, y + 1, fill_w, 4, 'F')

        # Value
        self.set_xy(self.l_margin + w_label + w_bar + 2, y)
        self.set_text_color(*colour)
        self.set_font('Helvetica', 'B', 8)
        self.cell(18, 6, f'{value}{unit}', ln=True)
        self.set_text_color(*C_BLACK)

    def edge_box(self, edge):
        colour = PRIORITY_COLOUR.get(edge['priority'], C_DARK)
        x = self.l_margin
        w = self.w - self.l_margin - self.r_margin

        # Priority badge
        self.set_fill_color(*colour)
        self.set_text_color(*C_WHITE)
        self.set_font('Helvetica', 'B', 7)
        self.rect(x, self.get_y(), 18, 5, 'F')
        self.set_xy(x, self.get_y())
        self.cell(18, 5, edge['priority'], align='C', ln=False)

        # Category + title
        self.set_fill_color(*C_GREY_BG)
        self.set_text_color(*C_DARK)
        self.set_font('Helvetica', 'B', 9)
        self.cell(w - 18, 5, f"  [{edge['category']}]  {edge['title']}", fill=True, ln=True)

        # Detail text
        self.set_x(x)
        self.set_font('Helvetica', '', 8)
        self.multi_cell(w, 4.5, f'   {edge["detail"]}')
        self.ln(2)
        self.set_text_color(*C_BLACK)

    def stats_table(self, headers, rows, col_widths=None):
        w_total = self.w - self.l_margin - self.r_margin
        n = len(headers)
        if not col_widths:
            col_widths = [w_total / n] * n

        # Header row
        self.set_fill_color(*C_BLACK)
        self.set_text_color(*C_YELLOW)
        self.set_font('Helvetica', 'B', 8)
        for h, cw in zip(headers, col_widths):
            self.cell(cw, 6, str(h), border=0, fill=True, align='C')
        self.ln()

        # Data rows
        self.set_text_color(*C_DARK)
        self.set_font('Helvetica', '', 8)
        for i, row in enumerate(rows):
            fill = i % 2 == 0
            self.set_fill_color(*C_GREY_BG if fill else C_WHITE)
            for val, cw in zip(row, col_widths):
                self.cell(cw, 5.5, str(val), border=0, fill=fill, align='C')
            self.ln()
        self.set_text_color(*C_BLACK)
        self.ln(2)


# ── Pre-game report ───────────────────────────────────────────────────────────

def generate_pregame_report(match_id, our_team_id, coaching_focus=None):
    match = db.get_match_by_id(match_id)
    if not match:
        print(f"Match {match_id} not found.")
        return None

    our_team = db.get_team_by_id(our_team_id)
    opp_id   = match['away_team_id'] if match['home_team_id'] == our_team_id else match['home_team_id']
    opp_team = db.get_team_by_id(opp_id)

    is_home = match['home_team_id'] == our_team_id
    venue_str = match['venue'] or 'TBC'
    date_str  = match['date'] or 'TBC'

    title = f"PRE-GAME: Round {match['round']} vs {opp_team['short_name']}"
    pdf = CoachingPDF(title)
    pdf.add_page()

    # ── Cover block ────────────────────────────────────────────────────────
    pdf.set_font('Helvetica', 'B', 18)
    pdf.set_text_color(*C_BLACK)
    pdf.ln(2)
    pdf.cell(0, 10, f"ROUND {match['round']} - OPPOSITION ANALYSIS", ln=True, align='C')

    pdf.set_font('Helvetica', 'B', 14)
    our_label = our_team['short_name'] + (' (H)' if is_home else ' (A)')
    opp_label = opp_team['name']
    pdf.cell(0, 8, f"{our_label}  vs  {opp_label}", ln=True, align='C')

    pdf.set_font('Helvetica', '', 9)
    pdf.cell(0, 5, f"Venue: {venue_str}   |   Date: {date_str}", ln=True, align='C')
    pdf.ln(4)

    # ── Ladder snapshot ────────────────────────────────────────────────────
    pdf.section_heading('2026 Ladder')
    ladder = db.get_ladder()
    headers = ['Pos', 'Team', 'P', 'W', 'L', 'PF', 'PA', 'Diff', 'Pts']
    col_w   = [10, 55, 10, 10, 10, 14, 14, 14, 10]
    rows_out = []
    for pos, row in enumerate(ladder, 1):
        marker = '** ' if row['team'] == our_team['name'] else ('>> ' if row['team'] == opp_team['name'] else '   ')
        rows_out.append([
            f"{pos}", marker + row['short'],
            row['p'], row['w'], row['l'],
            row['pf'], row['pa'], f"{row['diff']:+d}", row['pts']
        ])
    pdf.stats_table(headers, rows_out, col_w)

    # ── Opposition recent form ─────────────────────────────────────────────
    form = an.recent_form(opp_id, last_n=5)
    pdf.section_heading(f"{opp_team['short_name']} - Recent Form (Last 5)")
    if form:
        headers = ['Rnd', 'Opponent', 'Score', 'Res', 'Comp%', 'MissTkl%', 'Errors', 'Pens']
        col_w   = [12, 48, 20, 10, 20, 22, 18, 18]
        rows_out = [[
            r['round'], r['opponent'], r['score'], r['result'],
            f"{r['completion_pct']}%", f"{r['missed_tackle_pct']}%",
            r['errors'], r['penalties']
        ] for r in form]
        pdf.stats_table(headers, rows_out, col_w)
    else:
        pdf.body('No match data recorded yet. Enter stats after Round 1 to unlock.')

    # ── Opposition averages ────────────────────────────────────────────────
    opp_avgs = an.team_averages(opp_id)
    pdf.section_heading(f"{opp_team['short_name']} - Season Averages")
    if opp_avgs:
        pdf.stat_bar('Set Completion',     opp_avgs['completion_pct'],    80.0,  '%')
        pdf.stat_bar('Missed Tackle Rate', opp_avgs['missed_tackle_pct'], 10.0,  '%', higher_is_better=False)
        pdf.stat_bar('Penalties / Game',   opp_avgs['penalties_conceded'], 6.0,  '',  higher_is_better=False)
        pdf.stat_bar('Errors / Game',      opp_avgs['errors'],             5.0,  '',  higher_is_better=False)
        pdf.stat_bar('Kick Metres / Game', opp_avgs['kick_metres'],       300,   'm')
        pdf.ln(2)
        pdf.kv('Avg Points For',     f"{opp_avgs['points_for']:.1f}/game")
        pdf.kv('Avg Points Against', f"{opp_avgs['points_against']:.1f}/game")
        pdf.kv('Possession',         f"{opp_avgs['possession_pct']:.1f}%")
        pdf.kv('Avg Tries / Game',   f"{opp_avgs['tries']:.1f}")
    else:
        pdf.body('No season data yet.')

    # ── Edges ──────────────────────────────────────────────────────────────
    pdf.section_heading('Identified Edges & Tactical Recommendations')
    edges = an.find_edges(opp_id, our_id=our_team_id)
    for edge in edges:
        pdf.edge_box(edge)

    # ── Key threats ────────────────────────────────────────────────────────
    scorers = an.top_try_scorers(opp_id)
    if scorers:
        pdf.section_heading(f"{opp_team['short_name']} - Key Threats")
        headers = ['Player', 'Position', 'Games', 'Tries', 'Linebreaks', 'Assists']
        col_w   = [55, 25, 18, 18, 22, 22]
        rows_out = [[
            r['player_name'], r['position'] or '-', r['games_played'],
            r['tries'], r['linebreaks'], r['try_assists']
        ] for r in scorers]
        pdf.stats_table(headers, rows_out, col_w)

    # ── Our recent form ────────────────────────────────────────────────────
    our_form = an.recent_form(our_team_id, last_n=3)
    pdf.section_heading('Dapto - Last 3 Results')
    if our_form:
        headers = ['Rnd', 'Opponent', 'Score', 'Res', 'Comp%', 'MissTkl%', 'Pens']
        col_w   = [12, 50, 20, 10, 22, 24, 20]
        rows_out = [[
            r['round'], r['opponent'], r['score'], r['result'],
            f"{r['completion_pct']}%", f"{r['missed_tackle_pct']}%", r['penalties']
        ] for r in our_form]
        pdf.stats_table(headers, rows_out, col_w)
    else:
        pdf.body('Season just underway - no results recorded yet.')

    # ── Coaching focus ─────────────────────────────────────────────────────
    pdf.section_heading('Coaching Focus This Week')
    if coaching_focus:
        for i, point in enumerate(coaching_focus, 1):
            pdf.set_font('Helvetica', 'B', 9)
            pdf.cell(6, 6, f'{i}.', ln=False)
            pdf.set_font('Helvetica', '', 9)
            w = pdf.w - pdf.l_margin - pdf.r_margin - 6
            pdf.multi_cell(w, 5, point)
    else:
        pdf.body('Add coaching focus points via the main menu.')

    # ── Save ───────────────────────────────────────────────────────────────
    fname = f"pregame_round{match['round']}_{opp_team['short_name'].replace(' ','_')}.pdf"
    path  = os.path.join(OUTPUT_DIR, fname)
    pdf.output(path)
    print(f"Pre-game report saved: {path}")
    return path


# ── Post-game report ──────────────────────────────────────────────────────────

def generate_postgame_report(match_id, our_team_id, training_priorities=None):
    match = db.get_match_by_id(match_id)
    if not match:
        print(f"Match {match_id} not found.")
        return None

    our_team = db.get_team_by_id(our_team_id)
    opp_id   = match['away_team_id'] if match['home_team_id'] == our_team_id else match['home_team_id']
    opp_team = db.get_team_by_id(opp_id)

    review = an.post_game_review(match_id, our_team_id)

    title = f"POST-GAME: Round {match['round']} vs {opp_team['short_name']}"
    pdf = CoachingPDF(title)
    pdf.add_page()

    # ── Result banner ──────────────────────────────────────────────────────
    result = review['result'] if review else 'NO DATA'
    res_colour = {'WIN': C_GREEN, 'LOSS': C_RED, 'DRAW': C_ORANGE}.get(result, C_DARK)

    pdf.set_font('Helvetica', 'B', 20)
    pdf.set_text_color(*res_colour)
    pdf.ln(2)
    pdf.cell(0, 12, result, ln=True, align='C')
    pdf.set_text_color(*C_BLACK)

    pdf.set_font('Helvetica', 'B', 14)
    if review:
        pdf.cell(0, 8,
                 f"Dapto Canaries {review['our_score']}  -  {review['opp_score']}  {opp_team['short_name']}",
                 ln=True, align='C')
    pdf.set_font('Helvetica', '', 9)
    pdf.cell(0, 5,
             f"Round {match['round']}  |  {match['date'] or 'TBC'}  |  {match['venue'] or 'TBC'}",
             ln=True, align='C')
    pdf.ln(4)

    # ── Stats comparison ───────────────────────────────────────────────────
    pdf.section_heading('Match Statistics Comparison')
    our_s = review['our_stats'] if review else None
    opp_s = review['opp_stats'] if review else None

    def fmt(stats, key, fmt_str='{}'):
        if not stats:
            return '-'
        val = stats[key]
        return fmt_str.format(val if val is not None else '-')

    def comp_pct(stats):
        if not stats:
            return '-'
        cp = an.completion_pct(stats)
        return f"{cp:.0f}%"

    def mtp(stats):
        if not stats:
            return '-'
        m = an.missed_tackle_pct(stats)
        return f"{m:.0f}%"

    stat_rows = [
        ('Tries',              fmt(our_s, 'tries'),           fmt(opp_s, 'tries')),
        ('Points',             str(review['our_score'] if review else '-'),
                               str(review['opp_score'] if review else '-')),
        ('Set Completion',     comp_pct(our_s),               comp_pct(opp_s)),
        ('Errors',             fmt(our_s, 'errors'),           fmt(opp_s, 'errors')),
        ('Missed Tackles',     fmt(our_s, 'missed_tackles'),   fmt(opp_s, 'missed_tackles')),
        ('Missed Tackle %',    mtp(our_s),                     mtp(opp_s)),
        ('Penalties',          fmt(our_s, 'penalties_conceded'), fmt(opp_s, 'penalties_conceded')),
        ('Kick Metres',        fmt(our_s, 'kick_metres'),       fmt(opp_s, 'kick_metres')),
        ('40/20s',             fmt(our_s, 'forty_twenties'),    fmt(opp_s, 'forty_twenties')),
        ('Linebreaks',         fmt(our_s, 'linebreaks'),        fmt(opp_s, 'linebreaks')),
        ('Possession %',       fmt(our_s, 'possession_pct', '{:.0f}%'), fmt(opp_s, 'possession_pct', '{:.0f}%')),
    ]
    pdf.stats_table(
        ['Statistic', 'Dapto', opp_team['short_name']],
        stat_rows,
        [70, 55, 55]
    )

    # ── Performance vs targets ─────────────────────────────────────────────
    pdf.section_heading('Performance vs Targets')
    if our_s:
        cp  = an.completion_pct(our_s)
        mtp_val = an.missed_tackle_pct(our_s)
        pen = our_s['penalties_conceded'] or 0

        pdf.stat_bar('Set Completion',     cp,      an.TARGETS['completion_pct'],    '%')
        pdf.stat_bar('Missed Tackle Rate', mtp_val, an.TARGETS['missed_tackle_pct'], '%', higher_is_better=False)
        pdf.stat_bar('Penalties',          pen,     an.TARGETS['penalties_game'],    '',  higher_is_better=False)
        pdf.stat_bar('Kick Metres',        our_s['kick_metres'] or 0, an.TARGETS['kick_metres_game'], 'm')
    else:
        pdf.body('No team stats entered for this match.')

    # ── Strengths ──────────────────────────────────────────────────────────
    if review and review['positives']:
        pdf.section_heading('What We Did Well')
        for p in review['positives']:
            pdf.set_font('Helvetica', '', 9)
            pdf.cell(8, 5, '[+]', ln=False)
            w = pdf.w - pdf.l_margin - pdf.r_margin - 5
            pdf.multi_cell(w, 5, ' ' + p)

    # ── Areas to address ───────────────────────────────────────────────────
    if review and review['flags']:
        pdf.section_heading('Areas to Address')
        for f in review['flags']:
            pdf.set_font('Helvetica', 'B', 9)
            pdf.set_text_color(*C_RED)
            pdf.cell(5, 5, '!', ln=False)
            pdf.set_font('Helvetica', '', 9)
            pdf.set_text_color(*C_DARK)
            w = pdf.w - pdf.l_margin - pdf.r_margin - 5
            pdf.multi_cell(w, 5, ' ' + f)
        pdf.set_text_color(*C_BLACK)

    # ── Player performance ─────────────────────────────────────────────────
    dapto_id = db.get_team('Dapto Canaries')['id'] if db.get_team('Dapto Canaries') else our_team_id
    player_rows = db.get_player_match_stats(match_id, dapto_id)
    if player_rows:
        pdf.section_heading('Player Performances')
        headers = ['#', 'Player', 'Pos', 'Tries', 'Assists', 'LB', 'Tkl', 'MissTkl', 'Errors', 'Mins']
        col_w   = [8, 45, 16, 12, 14, 10, 12, 18, 16, 14]
        rows_out = [[
            r['jersey_num'] or '-', r['player_name'], r['position'] or '-',
            r['tries'], r['try_assists'], r['linebreaks'],
            r['tackles'], r['missed_tackles'], r['errors'], r['minutes_played']
        ] for r in player_rows]
        pdf.stats_table(headers, rows_out, col_w)

    # ── Player flags ───────────────────────────────────────────────────────
    concerns = an.defensive_concerns(dapto_id)
    if concerns:
        pdf.section_heading('Defensive Flags - Players to Address')
        for c in concerns:
            pdf.set_font('Helvetica', 'B', 9)
            pdf.set_text_color(*C_ORANGE)
            pdf.cell(0, 5,
                     f"  {c['name']} ({c['position'] or '?'}) - {c['missed_tackle_pct']}% miss rate over {c['games']} games",
                     ln=True)
        pdf.set_text_color(*C_BLACK)

    # ── Hudl clips ─────────────────────────────────────────────────────────
    hudl = db.get_hudl_links(match_id)
    if hudl:
        pdf.section_heading('Hudl Video Clips')
        for h in hudl:
            pdf.set_font('Helvetica', 'B', 8)
            pdf.cell(25, 5, f"[{h['clip_type'] or 'CLIP'}]", ln=False)
            pdf.set_font('Helvetica', '', 8)
            pdf.cell(0, 5, f"{h['description'] or ''}", ln=True)
            pdf.set_font('Helvetica', 'I', 7)
            pdf.set_text_color(60, 100, 180)
            pdf.cell(0, 4, f"  {h['url']}", ln=True)
            pdf.set_text_color(*C_BLACK)

    # ── Training priorities ────────────────────────────────────────────────
    pdf.section_heading('Training Priorities This Week')
    if training_priorities:
        for i, point in enumerate(training_priorities, 1):
            pdf.set_font('Helvetica', 'B', 9)
            pdf.cell(6, 6, f'{i}.', ln=False)
            pdf.set_font('Helvetica', '', 9)
            w = pdf.w - pdf.l_margin - pdf.r_margin - 6
            pdf.multi_cell(w, 5, point)
    else:
        notes = db.get_coaching_notes(match_id=match_id, note_type='training')
        if notes:
            for i, n in enumerate(notes, 1):
                pdf.set_font('Helvetica', 'B', 9)
                pdf.cell(6, 6, f'{i}.', ln=False)
                pdf.set_font('Helvetica', '', 9)
                w = pdf.w - pdf.l_margin - pdf.r_margin - 6
                pdf.multi_cell(w, 5, n['content'])
        else:
            pdf.body('Add training priorities via the main menu.')

    # ── Save ───────────────────────────────────────────────────────────────
    result_tag = review['result'].lower() if review else 'nodata'
    fname = f"postgame_round{match['round']}_{opp_team['short_name'].replace(' ','_')}_{result_tag}.pdf"
    path  = os.path.join(OUTPUT_DIR, fname)
    pdf.output(path)
    print(f"Post-game report saved: {path}")
    return path
