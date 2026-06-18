"""SQLite-backed slang store.

Two tables:
  terms      — active slang the bot reacts to (seeded + learned + hand-added)
  candidates — unknown words seen in chat, counting toward auto-promotion
"""

import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.environ.get("SLANG_DB", os.path.join(os.path.dirname(__file__), "slang.db"))


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db(seed_words=None):
    """Create tables; seed `terms` from `seed_words` on first run."""
    with _conn() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS terms (
                   term      TEXT PRIMARY KEY,
                   source    TEXT NOT NULL,           -- seed | learned | manual
                   added_at  TEXT NOT NULL,
                   hits      INTEGER NOT NULL DEFAULT 0
               )"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS candidates (
                   term       TEXT PRIMARY KEY,
                   count      INTEGER NOT NULL DEFAULT 0,
                   first_seen TEXT NOT NULL,
                   last_seen  TEXT NOT NULL
               )"""
        )
        if seed_words:
            existing = c.execute("SELECT COUNT(*) FROM terms").fetchone()[0]
            if existing == 0:
                now = _now()
                c.executemany(
                    "INSERT OR IGNORE INTO terms(term, source, added_at) VALUES (?, 'seed', ?)",
                    [(w.lower(), now) for w in seed_words],
                )


def active_terms():
    """Set of all active slang terms (lowercase)."""
    with _conn() as c:
        return {r["term"] for r in c.execute("SELECT term FROM terms")}


def add_term(term, source="manual"):
    """Add/keep a term. Returns True if it was newly added."""
    term = term.lower()
    with _conn() as c:
        cur = c.execute(
            "INSERT OR IGNORE INTO terms(term, source, added_at) VALUES (?, ?, ?)",
            (term, source, _now()),
        )
        c.execute("DELETE FROM candidates WHERE term = ?", (term,))
        return cur.rowcount > 0


def remove_term(term):
    """Remove a term. Returns True if it existed."""
    with _conn() as c:
        cur = c.execute("DELETE FROM terms WHERE term = ?", (term.lower(),))
        return cur.rowcount > 0


def bump_hit(term):
    with _conn() as c:
        c.execute("UPDATE terms SET hits = hits + 1 WHERE term = ?", (term.lower(),))


def list_terms(limit=100):
    """Return rows (term, source, hits) ordered by hits desc."""
    with _conn() as c:
        return [
            (r["term"], r["source"], r["hits"])
            for r in c.execute(
                "SELECT term, source, hits FROM terms ORDER BY hits DESC, term LIMIT ?",
                (limit,),
            )
        ]


def list_candidates(limit=15):
    """Top auto-learn candidates (term, count) by sightings desc."""
    with _conn() as c:
        return [
            (r["term"], r["count"])
            for r in c.execute(
                "SELECT term, count FROM candidates ORDER BY count DESC, last_seen DESC LIMIT ?",
                (limit,),
            )
        ]


def bump_candidate(term):
    """Increment a candidate's sighting count; return the new count."""
    term = term.lower()
    now = _now()
    with _conn() as c:
        c.execute(
            """INSERT INTO candidates(term, count, first_seen, last_seen)
               VALUES (?, 1, ?, ?)
               ON CONFLICT(term) DO UPDATE SET count = count + 1, last_seen = excluded.last_seen""",
            (term, now, now),
        )
        return c.execute("SELECT count FROM candidates WHERE term = ?", (term,)).fetchone()[0]
