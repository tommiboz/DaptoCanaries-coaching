import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "coaching.db")


def get_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            is_dapto INTEGER DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            round INTEGER NOT NULL,
            match_date TEXT,
            home_team_id INTEGER NOT NULL,
            away_team_id INTEGER NOT NULL,
            home_score INTEGER DEFAULT 0,
            away_score INTEGER DEFAULT 0,
            home_halftime INTEGER DEFAULT 0,
            away_halftime INTEGER DEFAULT 0,
            FOREIGN KEY(home_team_id) REFERENCES teams(id),
            FOREIGN KEY(away_team_id) REFERENCES teams(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS match_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER NOT NULL,
            team_id INTEGER NOT NULL,
            possession_pct REAL DEFAULT 50,
            sets_received INTEGER DEFAULT 0,
            sets_completed INTEGER DEFAULT 0,
            errors INTEGER DEFAULT 0,
            tries INTEGER DEFAULT 0,
            conversions_made INTEGER DEFAULT 0,
            conversions_attempted INTEGER DEFAULT 0,
            penalty_goals INTEGER DEFAULT 0,
            field_goals INTEGER DEFAULT 0,
            metres_gained INTEGER DEFAULT 0,
            linebreaks INTEGER DEFAULT 0,
            offloads INTEGER DEFAULT 0,
            tackles_made INTEGER DEFAULT 0,
            missed_tackles INTEGER DEFAULT 0,
            linebreaks_conceded INTEGER DEFAULT 0,
            penalties_conceded INTEGER DEFAULT 0,
            set_restarts_conceded INTEGER DEFAULT 0,
            kicks_general_play INTEGER DEFAULT 0,
            kick_metres INTEGER DEFAULT 0,
            notes TEXT DEFAULT "",
            FOREIGN KEY(match_id) REFERENCES matches(id),
            FOREIGN KEY(team_id) REFERENCES teams(id)
        )
    """)

    default_teams = [
        ("Dapto Canaries", 1),
        ("Corrimal Cougars", 0),
        ("Thirroul Butchers", 0),
        ("Wollongong Wolves", 0),
        ("Collegians Tigers", 0),
        ("Helensburgh Tigers", 0),
        ("Oakdale Workers", 0),
        ("Unanderra Devils", 0),
        ("Shellharbour Sharks", 0),
        ("Port Kembla Blacks", 0),
    ]
    for name, is_dapto in default_teams:
        c.execute("INSERT OR IGNORE INTO teams (name, is_dapto) VALUES (?, ?)", (name, is_dapto))

    init_video_tables(c)

    conn.commit()
    conn.close()


def init_video_tables(cursor):
    """Create the 5 video analysis tables. Safe to call multiple times."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS video_sessions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path       TEXT    NOT NULL,
            file_name       TEXT    NOT NULL,
            duration_secs   REAL,
            fps             REAL,
            total_frames    INTEGER,
            match_id        INTEGER REFERENCES matches(id),
            status          TEXT    DEFAULT 'pending',
            processed_at    TEXT,
            created_at      TEXT    DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS players (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            jersey      INTEGER,
            team        TEXT    DEFAULT 'Dapto',
            position    TEXT,
            active      INTEGER DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS video_players (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id      INTEGER NOT NULL REFERENCES video_sessions(id),
            track_id        INTEGER NOT NULL,
            jersey_number   INTEGER,
            ocr_confidence  REAL,
            team_side       TEXT,
            confirmed       INTEGER DEFAULT 0,
            player_id       INTEGER REFERENCES players(id),
            thumbnail_path  TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS video_detections (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id      INTEGER NOT NULL REFERENCES video_sessions(id),
            frame_number    INTEGER NOT NULL,
            track_id        INTEGER NOT NULL,
            x1              REAL,
            y1              REAL,
            x2              REAL,
            y2              REAL,
            confidence      REAL
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_detections_session_frame
            ON video_detections(session_id, frame_number)
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS video_events (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id          INTEGER NOT NULL REFERENCES video_sessions(id),
            frame_number        INTEGER NOT NULL,
            timestamp_secs      REAL,
            event_type          TEXT    NOT NULL,
            team_side           TEXT,
            primary_player_id   INTEGER REFERENCES video_players(id),
            secondary_player_id INTEGER REFERENCES video_players(id),
            notes               TEXT,
            created_at          TEXT    DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS video_derived_stats (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id      INTEGER NOT NULL REFERENCES video_sessions(id),
            team_side       TEXT    NOT NULL,
            tries           INTEGER DEFAULT 0,
            tackles         INTEGER DEFAULT 0,
            missed_tackles  INTEGER DEFAULT 0,
            errors          INTEGER DEFAULT 0,
            penalties       INTEGER DEFAULT 0,
            linebreaks      INTEGER DEFAULT 0,
            offloads        INTEGER DEFAULT 0,
            kicks           INTEGER DEFAULT 0,
            exported        INTEGER DEFAULT 0,
            exported_at     TEXT
        )
    """)


def get_video_session_count() -> int:
    """Return the number of video sessions processed."""
    conn = get_conn()
    try:
        row = conn.execute("SELECT COUNT(*) FROM video_sessions").fetchone()
        return row[0]
    except Exception:
        return 0
    finally:
        conn.close()


def get_teams():
    conn = get_conn()
    df = __import__("pandas").read_sql_query("SELECT * FROM teams ORDER BY is_dapto DESC, name", conn)
    conn.close()
    return df


def get_matches():
    conn = get_conn()
    df = __import__("pandas").read_sql_query("""
        SELECT m.id, m.round, m.match_date,
               ht.name as home_team, at.name as away_team,
               m.home_score, m.away_score,
               m.home_halftime, m.away_halftime
        FROM matches m
        JOIN teams ht ON m.home_team_id = ht.id
        JOIN teams at ON m.away_team_id = at.id
        ORDER BY m.round DESC
    """, conn)
    conn.close()
    return df


def get_match_stats_full():
    conn = get_conn()
    df = __import__("pandas").read_sql_query("""
        SELECT ms.*, t.name as team_name, t.is_dapto,
               m.round, m.match_date,
               ht.name as home_team, at.name as away_team,
               m.home_score, m.away_score
        FROM match_stats ms
        JOIN teams t ON ms.team_id = t.id
        JOIN matches m ON ms.match_id = m.id
        JOIN teams ht ON m.home_team_id = ht.id
        JOIN teams at ON m.away_team_id = at.id
        ORDER BY m.round DESC
    """, conn)
    conn.close()
    return df


def insert_match(round_num, match_date, home_team_id, away_team_id,
                 home_score, away_score, home_halftime, away_halftime):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO matches (round, match_date, home_team_id, away_team_id,
                             home_score, away_score, home_halftime, away_halftime)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (round_num, match_date, home_team_id, away_team_id,
          home_score, away_score, home_halftime, away_halftime))
    match_id = c.lastrowid
    conn.commit()
    conn.close()
    return match_id


def insert_match_stats(match_id, team_id, stats: dict):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO match_stats (
            match_id, team_id,
            possession_pct, sets_received, sets_completed, errors,
            tries, conversions_made, conversions_attempted, penalty_goals, field_goals,
            metres_gained, linebreaks, offloads,
            tackles_made, missed_tackles, linebreaks_conceded,
            penalties_conceded, set_restarts_conceded,
            kicks_general_play, kick_metres, notes
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        match_id, team_id,
        stats.get("possession_pct", 50),
        stats.get("sets_received", 0),
        stats.get("sets_completed", 0),
        stats.get("errors", 0),
        stats.get("tries", 0),
        stats.get("conversions_made", 0),
        stats.get("conversions_attempted", 0),
        stats.get("penalty_goals", 0),
        stats.get("field_goals", 0),
        stats.get("metres_gained", 0),
        stats.get("linebreaks", 0),
        stats.get("offloads", 0),
        stats.get("tackles_made", 0),
        stats.get("missed_tackles", 0),
        stats.get("linebreaks_conceded", 0),
        stats.get("penalties_conceded", 0),
        stats.get("set_restarts_conceded", 0),
        stats.get("kicks_general_play", 0),
        stats.get("kick_metres", 0),
        stats.get("notes", ""),
    ))
    conn.commit()
    conn.close()


def add_team(name):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO teams (name, is_dapto) VALUES (?, 0)", (name,))
    conn.commit()
    conn.close()


def get_existing_match_keys():
    """Return a set of (round, home_team_id, away_team_id) for duplicate detection."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT round, home_team_id, away_team_id FROM matches"
    ).fetchall()
    conn.close()
    return {(r[0], r[1], r[2]) for r in rows}


def delete_match(match_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM match_stats WHERE match_id = ?", (match_id,))
    c.execute("DELETE FROM matches WHERE id = ?", (match_id,))
    conn.commit()
    conn.close()
