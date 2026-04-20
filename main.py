"""
Dapto Canaries - Coaching Analysis System
Harrigan Cup 2026

Usage: python main.py
"""
import os
import sys
import database as db

DAPTO_NAME = 'Dapto Canaries'
YEAR = 2026


def _dapto_id():
    t = db.get_team(DAPTO_NAME)
    return t['id'] if t else None


def banner():
    print()
    print("=" * 55)
    print("  DAPTO CANARIES  |  HARRIGAN CUP 2026")
    print("  Coaching Analysis System")
    print("=" * 55)


def print_ladder():
    ladder = db.get_ladder(YEAR)
    print("\n  2026 Harrigan Cup Ladder")
    print(f"  {'Pos':<4} {'Team':<28} {'P':>2} {'W':>2} {'L':>2} {'PF':>4} {'PA':>4} {'Diff':>5} {'Pts':>3}")
    print("  " + "-" * 55)
    for pos, row in enumerate(ladder, 1):
        marker = '>>>' if row['team'] == DAPTO_NAME else '   '
        print(f"  {marker} {pos:<2}  {row['short']:<26} {row['p']:>2} {row['w']:>2} {row['l']:>2} "
              f"{row['pf']:>4} {row['pa']:>4} {row['diff']:>+5} {row['pts']:>3}")
    print()


def print_fixtures():
    did = _dapto_id()
    matches = db.get_matches(YEAR, team_id=did)
    print("\n  Dapto Canaries - 2026 Fixtures")
    print(f"  {'Rnd':<5} {'Date':<12} {'H/A':<5} {'Opponent':<28} {'Result'}")
    print("  " + "-" * 60)
    for m in matches:
        is_home = m['home_team_id'] == did
        ha      = 'H' if is_home else 'A'
        opp     = m['away_name'] if is_home else m['home_name']
        if m['played']:
            if is_home:
                result = f"{m['home_score']}-{m['away_score']}"
                w = 'W' if m['home_score'] > m['away_score'] else ('D' if m['home_score'] == m['away_score'] else 'L')
            else:
                result = f"{m['away_score']}-{m['home_score']}"
                w = 'W' if m['away_score'] > m['home_score'] else ('D' if m['away_score'] == m['home_score'] else 'L')
            result = f"{w} {result}"
        else:
            result = 'vs'
        print(f"  {m['round']:<5} {(m['date'] or 'TBC'):<12} {ha:<5} {opp:<28} {result}")
    print()


def menu_reports():
    import reports
    did = _dapto_id()
    print("\n  Generate Report")
    print("  1. Pre-game opposition analysis")
    print("  2. Post-game review")
    choice = input("  Choice: ").strip()

    matches = db.get_matches(YEAR, team_id=did)
    if not matches:
        print("  No matches found.")
        return

    print("\n  Select match:")
    for m in matches:
        played = '[x]' if m['played'] else '   '
        opp    = m['away_name'] if m['home_team_id'] == did else m['home_name']
        print(f"  [{m['id']}] Rnd {m['round']:2d} {played}  vs {opp}  ({m['date'] or 'TBC'})")

    try:
        mid = int(input("  Match ID: ").strip())
    except ValueError:
        return

    match = db.get_match_by_id(mid)
    if not match:
        print("  Invalid match ID.")
        return

    if choice == '1':
        print("\n  Add coaching focus points (blank line to finish, Enter alone to skip):")
        focus = []
        while True:
            line = input("  > ").strip()
            if not line:
                break
            focus.append(line)
        reports.generate_pregame_report(mid, did, coaching_focus=focus or None)

    elif choice == '2':
        if not match['played']:
            print("  Match not marked as played. Enter the result first.")
            return
        print("\n  Add training priorities (blank line to finish):")
        priorities = []
        while True:
            line = input("  > ").strip()
            if not line:
                break
            priorities.append(line)
        reports.generate_postgame_report(mid, did, training_priorities=priorities or None)


def menu_data_entry():
    import data_entry
    print("\n  Data Entry")
    print("  1. Enter match result")
    print("  2. Enter team match stats")
    print("  3. Enter player match stats")
    print("  4. Add player to squad")
    print("  5. View squad")
    print("  6. Add match to draw")
    print("  7. Add coaching note")
    print("  8. Add Hudl video link")
    choice = input("  Choice: ").strip()

    if   choice == '1': data_entry.enter_match_result()
    elif choice == '2': data_entry.enter_match_stats()
    elif choice == '3': data_entry.enter_player_stats()
    elif choice == '4': data_entry.manage_players()
    elif choice == '5': data_entry.manage_players()
    elif choice == '6': data_entry.add_match_to_draw()
    elif choice == '7': data_entry.add_coaching_note()
    elif choice == '8': data_entry.add_hudl_link()
    else: print("  Invalid choice.")


def menu_analysis():
    import analysis as an
    did = _dapto_id()
    print("\n  Analysis")
    print("  1. Dapto season averages")
    print("  2. Opposition analysis")
    print("  3. Find edges vs next opponent")
    print("  4. Top try scorers - Dapto")
    print("  5. Defensive concerns - Dapto")
    choice = input("  Choice: ").strip()

    if choice == '1':
        avgs = an.team_averages(did, YEAR)
        if not avgs:
            print("  No data yet.")
            return
        print(f"\n  Dapto Canaries - {avgs['games']} game(s) played")
        print(f"  Completion:       {avgs['completion_pct']}%  (target 80%)")
        print(f"  Missed tackle %:  {avgs['missed_tackle_pct']}%  (target <10%)")
        print(f"  Penalties/game:   {avgs['penalties_conceded']}")
        print(f"  Errors/game:      {avgs['errors']}")
        print(f"  Kick metres/game: {avgs['kick_metres']}")
        print(f"  Points for/game:  {avgs['points_for']}")
        print(f"  Points against:   {avgs['points_against']}")

    elif choice == '2':
        teams = db.get_all_teams()
        print()
        for t in teams:
            if t['name'] != DAPTO_NAME:
                print(f"  [{t['id']}] {t['name']}")
        try:
            oid = int(input("  Team ID: ").strip())
        except ValueError:
            return
        opp = db.get_team_by_id(oid)
        if not opp:
            return
        avgs = an.team_averages(oid, YEAR)
        if not avgs:
            print(f"  No data for {opp['name']} yet.")
            return
        print(f"\n  {opp['name']} - {avgs['games']} game(s)")
        print(f"  Completion:       {avgs['completion_pct']}%")
        print(f"  Missed tackle %:  {avgs['missed_tackle_pct']}%")
        print(f"  Penalties/game:   {avgs['penalties_conceded']}")
        print(f"  Points for/game:  {avgs['points_for']}")
        print(f"  Points against:   {avgs['points_against']}")

    elif choice == '3':
        # find next unplayed Dapto match
        matches = db.get_matches(YEAR, team_id=did)
        next_m  = next((m for m in matches if not m['played']), None)
        if not next_m:
            print("  No upcoming matches found.")
            return
        is_home = next_m['home_team_id'] == did
        oid     = next_m['away_team_id'] if is_home else next_m['home_team_id']
        opp     = db.get_team_by_id(oid)
        print(f"\n  Next match: Dapto vs {opp['name']}  Round {next_m['round']}")
        edges = an.find_edges(oid, our_id=did, year=YEAR)
        print()
        for e in edges:
            print(f"  [{e['priority']:<6}] {e['category']}: {e['title']}")
            print(f"           {e['detail'][:100]}...")
            print()

    elif choice == '4':
        scorers = an.top_try_scorers(did, YEAR)
        if not scorers:
            print("  No try data yet.")
            return
        print(f"\n  {'Player':<25} {'Pos':<10} {'Games':>5} {'Tries':>5} {'LB':>4} {'Assists':>7}")
        for r in scorers:
            print(f"  {r['player_name']:<25} {(r['position'] or '?'):<10} "
                  f"{r['games_played']:>5} {r['tries']:>5} {r['linebreaks']:>4} {r['try_assists']:>7}")

    elif choice == '5':
        concerns = an.defensive_concerns(did, YEAR)
        if not concerns:
            print("  No defensive concerns flagged.")
            return
        print(f"\n  Defensive concerns (>15% miss rate, min 2 games):")
        for c in concerns:
            print(f"  {c['name']} ({c['position'] or '?'}) - {c['missed_tackle_pct']}% over {c['games']} game(s)")


def menu_scraper():
    import scraper
    print("\n  Scrape Results from playrugbyleague.com")
    print(f"  Current URL: {scraper.COMP_URL_2026 or 'Not set'}")
    print("  1. Run scraper (import results to DB)")
    print("  2. Dry run (preview only)")
    print("  3. Set competition URL")
    choice = input("  Choice: ").strip()

    if choice == '1':
        scraper.scrape_results(year=YEAR, dry_run=False)
    elif choice == '2':
        scraper.scrape_results(year=YEAR, dry_run=True)
    elif choice == '3':
        url = input("  Paste the playrugbyleague.com competition URL: ").strip()
        scraper.set_comp_url(url)
        # Persist it in scraper module file
        try:
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scraper.py')
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            content = content.replace(
                "COMP_URL_2026 = None",
                f"COMP_URL_2026 = '{url}'"
            )
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            print("  URL saved to scraper.py.")
        except Exception as e:
            print(f"  Could not save to file: {e}")


def main():
    db.init_db()
    banner()

    while True:
        print("\n  MAIN MENU")
        print("  1. Fixtures & Ladder")
        print("  2. Data Entry")
        print("  3. Analysis")
        print("  4. Generate PDF Report")
        print("  5. Scrape Latest Results")
        print("  0. Exit")
        print()
        choice = input("  Choice: ").strip()

        if   choice == '1': print_fixtures(); print_ladder()
        elif choice == '2': menu_data_entry()
        elif choice == '3': menu_analysis()
        elif choice == '4': menu_reports()
        elif choice == '5': menu_scraper()
        elif choice == '0':
            print("\n  Good luck Dapto!\n")
            sys.exit(0)
        else:
            print("  Invalid choice.")


if __name__ == '__main__':
    main()
