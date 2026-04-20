"""
Scraper for playrugbyleague.com — pulls Harrigan Cup results as they are published.

The 2026 competition URL will appear on playrugbyleague.com once the season launches.
Update COMP_URL below when you find it (search for 'Harrigan Cup 2026' on the site).
"""
import re
import urllib.request
import urllib.error

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

import database as db

# ── Update this once the 2026 competition page is live ───────────────────────
# 2025 example: https://www.playrugbyleague.com/Competitions/Competition/2025-nswrl-major-competitions---harrigan-cup-61324817
COMP_URL_2026 = None   # set to the 2026 URL when available

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0 Safari/537.36'
    )
}


def _fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {url}")
        return None
    except Exception as e:
        print(f"  Fetch error: {e}")
        return None


def _normalise_team(name):
    """Map scraped team name to DB team name."""
    mapping = {
        'dapto':       'Dapto Canaries',
        'canaries':    'Dapto Canaries',
        'collegians':  'Collegians Collie Dogs',
        'collie':      'Collegians Collie Dogs',
        'wests':       'Western Suburbs Devils',
        'western':     'Western Suburbs Devils',
        'corrimal':    'Corrimal Cougars',
        'cougars':     'Corrimal Cougars',
        'thirroul':    'Thirroul Butchers',
        'butchers':    'Thirroul Butchers',
        'sutherland':  'Sutherland-Loftus Pirates',
        'pirates':     'Sutherland-Loftus Pirates',
        'loftus':      'Sutherland-Loftus Pirates',
    }
    key = name.lower().strip()
    for k, v in mapping.items():
        if k in key:
            return v
    return name.strip()


def scrape_results(comp_url=None, year=2026, dry_run=False):
    """
    Attempt to scrape results from playrugbyleague.com.
    Returns list of dicts: {round, home, away, home_score, away_score, date}.
    """
    if not BS4_AVAILABLE:
        print("  BeautifulSoup4 not installed. Run: pip install beautifulsoup4")
        return []

    url = comp_url or COMP_URL_2026
    if not url:
        print("  No competition URL set for 2026 yet.")
        print("  Once the season starts, find the Harrigan Cup page on playrugbyleague.com")
        print("  and update COMP_URL_2026 in scraper.py.")
        return []

    print(f"  Fetching: {url}")
    html = _fetch(url)
    if not html:
        return []

    soup   = BeautifulSoup(html, 'html.parser')
    results = []

    # playrugbyleague.com renders results via JavaScript — look for embedded JSON
    json_match = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.+?\});', html, re.DOTALL)
    if json_match:
        import json
        try:
            data   = json.loads(json_match.group(1))
            rounds = (data.get('competition', {})
                          .get('fixtures', {})
                          .get('rounds', []))
            for rnd in rounds:
                rnd_num = rnd.get('roundNumber') or rnd.get('round', 0)
                for fixture in rnd.get('fixtures', []):
                    home_name  = _normalise_team(fixture.get('homeTeamName', ''))
                    away_name  = _normalise_team(fixture.get('awayTeamName', ''))
                    home_score = fixture.get('homeScore')
                    away_score = fixture.get('awayScore')
                    date       = fixture.get('matchDate', '')[:10] if fixture.get('matchDate') else None
                    status     = fixture.get('matchStatus', '')
                    if status.lower() in ('complete', 'final') and home_score is not None:
                        results.append({
                            'round':      rnd_num,
                            'home':       home_name,
                            'away':       away_name,
                            'home_score': int(home_score),
                            'away_score': int(away_score),
                            'date':       date,
                        })
        except Exception as e:
            print(f"  JSON parse error: {e}")

    # Fallback — try HTML table parsing
    if not results:
        for table in soup.find_all('table'):
            rows = table.find_all('tr')
            for row in rows:
                cells = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
                score_re = re.search(r'(\d+)\s*[-–]\s*(\d+)', ' '.join(cells))
                if score_re and len(cells) >= 3:
                    results.append({
                        'round':      None,
                        'home':       _normalise_team(cells[0]),
                        'away':       _normalise_team(cells[-1]),
                        'home_score': int(score_re.group(1)),
                        'away_score': int(score_re.group(2)),
                        'date':       None,
                    })

    print(f"  Found {len(results)} completed result(s).")

    if dry_run or not results:
        for r in results:
            print(f"    Rnd {r['round']}: {r['home']} {r['home_score']}–{r['away_score']} {r['away']}")
        return results

    # Save to DB
    saved = 0
    for r in results:
        matches = db.get_matches(year)
        for m in matches:
            hn = _normalise_team(m['home_name'])
            an = _normalise_team(m['away_name'])
            if hn == r['home'] and an == r['away']:
                if not m['played']:
                    db.save_match_result(m['id'], r['home_score'], r['away_score'])
                    saved += 1
                break
    print(f"  Saved {saved} new result(s) to database.")
    return results


def set_comp_url(url):
    """Convenience to update the competition URL at runtime."""
    global COMP_URL_2026
    COMP_URL_2026 = url
    print(f"  Competition URL set to: {url}")


if __name__ == '__main__':
    scrape_results(dry_run=True)
