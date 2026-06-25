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
                   term       TEXT PRIMARY KEY,
                   source     TEXT NOT NULL,           -- seed | learned | manual
                   added_at   TEXT NOT NULL,
                   hits       INTEGER NOT NULL DEFAULT 0,
                   last_fired TEXT                      -- when a card last fired for this term
               )"""
        )
        # Migrate older DBs that predate the last_fired column.
        cols = {r["name"] for r in c.execute("PRAGMA table_info(terms)")}
        if "last_fired" not in cols:
            c.execute("ALTER TABLE terms ADD COLUMN last_fired TEXT")
        c.execute(
            """CREATE TABLE IF NOT EXISTS candidates (
                   term       TEXT PRIMARY KEY,
                   count      INTEGER NOT NULL DEFAULT 0,
                   first_seen TEXT NOT NULL,
                   last_seen  TEXT NOT NULL
               )"""
        )
        # Auto-translation on/off, tracked independently per guild and per
        # channel. A missing row means "on". Auto fires only when BOTH the
        # guild and the channel are enabled.
        c.execute(
            """CREATE TABLE IF NOT EXISTS guild_settings (
                   guild_id     INTEGER PRIMARY KEY,
                   auto_enabled INTEGER NOT NULL DEFAULT 1
               )"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS channel_settings (
                   channel_id   INTEGER PRIMARY KEY,
                   auto_enabled INTEGER NOT NULL DEFAULT 1
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
    """Record that a card fired for `term`: count it and stamp last_fired."""
    with _conn() as c:
        c.execute(
            "UPDATE terms SET hits = hits + 1, last_fired = ? WHERE term = ?",
            (_now(), term.lower()),
        )


def word_recently_fired(term, within_seconds):
    """True if a card for `term` fired within the last `within_seconds`.

    Drives the long per-word cooldown so an already-defined word doesn't keep
    re-firing. Server-wide (keyed on the term, not the channel)."""
    with _conn() as c:
        row = c.execute(
            "SELECT last_fired FROM terms WHERE term = ?", (term.lower(),)
        ).fetchone()
    if not row or not row["last_fired"]:
        return False
    last = datetime.fromisoformat(row["last_fired"])
    return (datetime.now(timezone.utc) - last).total_seconds() < within_seconds


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


# ---- auto-translation on/off (per guild + per channel) --------------------

def disabled_guilds():
    """Set of guild ids where auto-translation is paused server-wide."""
    with _conn() as c:
        return {
            r["guild_id"]
            for r in c.execute("SELECT guild_id FROM guild_settings WHERE auto_enabled = 0")
        }


def disabled_channels():
    """Set of channel ids where auto-translation is paused."""
    with _conn() as c:
        return {
            r["channel_id"]
            for r in c.execute("SELECT channel_id FROM channel_settings WHERE auto_enabled = 0")
        }


def set_guild_auto(guild_id, enabled):
    """Turn auto-translation on/off for a whole guild (persisted)."""
    with _conn() as c:
        c.execute(
            """INSERT INTO guild_settings(guild_id, auto_enabled) VALUES (?, ?)
               ON CONFLICT(guild_id) DO UPDATE SET auto_enabled = excluded.auto_enabled""",
            (guild_id, 1 if enabled else 0),
        )


def set_channel_auto(channel_id, enabled):
    """Turn auto-translation on/off for a single channel (persisted)."""
    with _conn() as c:
        c.execute(
            """INSERT INTO channel_settings(channel_id, auto_enabled) VALUES (?, ?)
               ON CONFLICT(channel_id) DO UPDATE SET auto_enabled = excluded.auto_enabled""",
            (channel_id, 1 if enabled else 0),
        )
