# Rizzetta Stone

A Discord bot by [@myers-jacobandrew](https://github.com/myers-jacobandrew).

Auto-detects gen z / gen alpha slang in chat and replies with an Urban
Dictionary card. It **teaches itself new slang** as terms trend — confirming
them against Urban Dictionary before adding them — so the word list stays
current with zero upkeep. Use `/define` to look up any word yourself.

Born from "im not geomaxxing".

## How detection works

A word triggers a card if:
1. it's an **active term** in the DB (seeded, learned, or hand-added), or
2. it ends in a **productive suffix** — `-maxxing`, `-pilled`, `-mogging`, `-coded`
   (this catches infinite coinages: geomaxxing, gymmaxxing, doompilled).

...unless either guard below kills it:

- **Context guard** — many terms double as ordinary English. A hit is skipped
  when the neighbouring word shows literal use: `based off of`, `based in Ohio`,
  `fire alarm`, `the cap of the bottle`, `mid day`. The per-word literal lists
  live in `LITERAL_NEXT` / `LITERAL_PREV` in `slang.py` — extend them as new
  false positives turn up.
- **Per-word cooldown** — once a word fires a card it won't fire again
  server-wide for `WORD_COOLDOWN` (default **5 days**), so repeats of the same
  word don't re-spam the same definition.

## How it self-updates (no manual upkeep)

Unknown words get tracked as *candidates* in the DB. When a word:
- gets used **`LEARN_HITS`** times in the server (default 3), **and**
- has an Urban Dictionary entry with **net votes ≥ `LEARN_MIN_NET`** (default 150), **and**
- isn't common English (filtered list in `slang.py`),

...the bot promotes it to an active term automatically and posts a
"📈 new slang learned" card. The vote threshold + common-word filter are what
keep it from "learning" normal words.

## Files

- `slang.py` — seed list, suffix rules, common-word filter, detection
- `urban.py` — Urban Dictionary API client (picks highest net-voted def)
- `db.py` — SQLite store (`slang.db`): `terms`, `candidates`, and the
  `guild_settings` / `channel_settings` on-off switches
- `bot.py` — the bot: cards, auto-learn loop, slash commands

## Slash commands (optional — auto-learn handles the rest)

- `/define <word>` — anyone, look up any word on Urban Dictionary (always works,
  even when auto-cards are off)
- `/cards off` / `/cards on` — anyone, pause/resume **automatic** detection in
  the current channel. Add `scope:server` to flip the whole server (mods only).
- `/cards status` — show whether auto-cards are on here
- `/slang list` — show the top tracked terms
- `/slang pending` — show words climbing toward auto-learn (with their hit counts)
- `/slang add <word>` / `/slang remove <word>` — mods (Manage Server) only

Auto-detection fires only when **both** the channel and the server have cards
on; `/define` is never affected by the switches. State is persisted in the DB.

## Setup

1. Create the bot + token (see token steps below), enable **Message Content Intent**.
2. Install:
   ```bash
   cd genz-slang-bot
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env   # paste your token
   ```
3. Run: `python bot.py`

## Config (.env)

| var | default | meaning |
|-----|---------|---------|
| `DISCORD_TOKEN` | — | bot token (required) |
| `GUILD_ID` | — | optional: sync slash commands to one server instantly |
| `SLANG_COOLDOWN` | 20 | seconds between cards per channel (anti-spam) |
| `WORD_COOLDOWN` | 432000 | seconds before the same word can fire again (default 5 days) |
| `LEARN_HITS` | 3 | sightings before the bot checks UD for a new word |
| `LEARN_MIN_NET` | 150 | min UD net votes to auto-learn a word |
| `LEARN_MIN_RATIO` | 0 | optional up/(up+down) floor (0 = off); blocks downvote-heavy words |
| `SLANG_DB` | ./slang.db | DB file path |

The `slang.db` file is the bot's memory — back it up / mount it on a volume if
hosting so learned words survive redeploys.
