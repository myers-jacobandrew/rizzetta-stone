# brainrot translator bot

Discord bot that drops an Urban Dictionary card whenever someone uses
gen z / gen alpha slang — and **teaches itself new slang** as the vernacular
shifts, so you never have to maintain the word list. Born from "im not geomaxxing".

## How detection works

A word triggers a card if:
1. it's an **active term** in the DB (seeded, learned, or hand-added), or
2. it ends in a **productive suffix** — `-maxxing`, `-pilled`, `-mogging`, `-coded`
   (this catches infinite coinages: geomaxxing, gymmaxxing, doompilled).

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
- `db.py` — SQLite store (`slang.db`): `terms` + `candidates` tables
- `bot.py` — the bot: cards, auto-learn loop, slash commands

## Slash commands (optional — auto-learn handles the rest)

- `/define <word>` — anyone, look up any word
- `/slang list` — show top tracked terms
- `/slang add <word>` / `/slang remove <word>` — mods (Manage Server) only

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
| `SLANG_COOLDOWN` | 20 | seconds between cards per channel |
| `LEARN_HITS` | 3 | sightings before the bot checks UD for a new word |
| `LEARN_MIN_NET` | 150 | min UD net votes to auto-learn a word |
| `SLANG_DB` | ./slang.db | DB file path |

The `slang.db` file is the bot's memory — back it up / mount it on a volume if
hosting so learned words survive redeploys.
