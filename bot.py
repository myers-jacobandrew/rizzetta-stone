"""Brainrot translator bot: slang -> Urban Dictionary card, with a
self-updating word DB.

- Known slang (DB + suffix rules) -> replies with a definition card.
- Unknown words are tracked; once one trends in the server AND Urban Dictionary
  confirms it's real + popular + not plain English, the bot learns it on its
  own (no manual upkeep) and announces the new word.
"""

import os
import time

import discord
from discord import app_commands
from dotenv import load_dotenv

import db
from slang import SEED_WORDS, find_slang, candidate_tokens
from urban import define

load_dotenv()
TOKEN = os.environ.get("DISCORD_TOKEN")
GUILD_ID = os.environ.get("GUILD_ID")  # optional: instant slash-command sync

# Tuning (all overridable via env)
COOLDOWN = float(os.environ.get("SLANG_COOLDOWN", "20"))       # secs between cards / channel
LEARN_HITS = int(os.environ.get("LEARN_HITS", "3"))            # sightings before UD check
LEARN_MIN_NET = int(os.environ.get("LEARN_MIN_NET", "150"))    # min UD net votes to learn
LEARN_MIN_RATIO = float(os.environ.get("LEARN_MIN_RATIO", "0"))  # min up/(up+down); 0 = off

_last_fire: dict[int, float] = {}
KNOWN: set[str] = set()  # in-memory cache of active terms, kept in sync with DB

intents = discord.Intents.default()
intents.message_content = True


class TranslatorBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        db.init_db(seed_words=SEED_WORDS)
        KNOWN.update(db.active_terms())
        if GUILD_ID:
            g = discord.Object(id=int(GUILD_ID))
            self.tree.copy_global_to(guild=g)
            await self.tree.sync(guild=g)
        else:
            await self.tree.sync()


bot = TranslatorBot()


def _trim(s, n):
    s = s or "—"
    return s if len(s) <= n else s[: n - 1] + "…"


def _card(d, *, learned=False):
    e = discord.Embed(
        title=f"{'📈 new slang learned: ' if learned else '📖 '}{d['word']}",
        url=d["permalink"] or None,
        description=_trim(d["definition"], 1024),
        color=0x2ECC71 if learned else 0x9B59B6,
    )
    if d["example"]:
        e.add_field(name="Example", value=_trim(d["example"], 1024), inline=False)
    e.set_footer(text=f"👍 {d['up']}  👎 {d['down']}  ·  Urban Dictionary")
    return e


def _on_cooldown(channel_id):
    return time.monotonic() - _last_fire.get(channel_id, 0) < COOLDOWN


def _passes_ratio(d):
    """Guard against learning controversial words (high net, but down-vote heavy).
    Disabled when LEARN_MIN_RATIO == 0."""
    if LEARN_MIN_RATIO <= 0:
        return True
    total = d["up"] + d["down"]
    return total > 0 and d["up"] / total >= LEARN_MIN_RATIO


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} — {len(KNOWN)} terms loaded, watching for slang.")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.content:
        return

    # 1) Known slang -> fire a definition card.
    term = find_slang(message.content, KNOWN)
    if term:
        if _on_cooldown(message.channel.id):
            return
        d = await define(term)
        if d:
            db.bump_hit(term.lower())
            _last_fire[message.channel.id] = time.monotonic()
            await message.reply(embed=_card(d), mention_author=False)
        return

    # 2) No known slang -> grow the DB. Track unknown words; learn the ones that
    #    trend AND check out on Urban Dictionary.
    for tok in candidate_tokens(message.content, KNOWN):
        count = db.bump_candidate(tok)
        # Probe UD at the LEARN_HITS crossing, then re-probe every LEARN_HITS
        # sightings after. Probing only at the exact crossing meant a single
        # transient UD failure (or a word momentarily under the vote bar) could
        # never be reconsidered — the count climbs past LEARN_HITS forever.
        if count < LEARN_HITS or count % LEARN_HITS != 0:
            continue
        d = await define(tok)
        if d and d["net"] >= LEARN_MIN_NET and _passes_ratio(d):
            db.add_term(tok.lower(), source="learned")
            KNOWN.add(tok.lower())
            if not _on_cooldown(message.channel.id):
                _last_fire[message.channel.id] = time.monotonic()
                await message.channel.send(embed=_card(d, learned=True))
            return


# ---- optional manual overrides (mods only) --------------------------------

def _is_mod(interaction):
    p = interaction.user.guild_permissions
    return p.manage_guild or p.administrator


@bot.tree.command(name="define", description="Look up any word on Urban Dictionary")
async def define_cmd(interaction: discord.Interaction, word: str):
    d = await define(word)
    if not d:
        await interaction.response.send_message(f"No Urban Dictionary entry for **{word}**.", ephemeral=True)
        return
    await interaction.response.send_message(embed=_card(d))


slang_group = app_commands.Group(name="slang", description="Manage the slang word list")


@slang_group.command(name="add", description="Force-add a word the bot reacts to")
async def slang_add(interaction: discord.Interaction, word: str):
    if not _is_mod(interaction):
        await interaction.response.send_message("Mods only.", ephemeral=True)
        return
    added = db.add_term(word, source="manual")
    KNOWN.add(word.lower())
    await interaction.response.send_message(
        f"{'Added' if added else 'Already had'} **{word.lower()}**.", ephemeral=True
    )


@slang_group.command(name="remove", description="Stop reacting to a word")
async def slang_remove(interaction: discord.Interaction, word: str):
    if not _is_mod(interaction):
        await interaction.response.send_message("Mods only.", ephemeral=True)
        return
    removed = db.remove_term(word)
    KNOWN.discard(word.lower())
    await interaction.response.send_message(
        f"{'Removed' if removed else 'Was not tracking'} **{word.lower()}**.", ephemeral=True
    )


@slang_group.command(name="list", description="Show the top tracked slang")
async def slang_list(interaction: discord.Interaction):
    rows = db.list_terms(limit=40)
    if not rows:
        await interaction.response.send_message("No terms yet.", ephemeral=True)
        return
    lines = [f"`{t}` ·{h}× ({s})" for t, s, h in rows]
    e = discord.Embed(title="Tracked slang", description="\n".join(lines), color=0x9B59B6)
    e.set_footer(text=f"{len(KNOWN)} active terms · self-updating")
    await interaction.response.send_message(embed=e, ephemeral=True)


@slang_group.command(name="pending", description="Words climbing toward auto-learn")
async def slang_pending(interaction: discord.Interaction):
    rows = db.list_candidates(limit=15)
    if not rows:
        await interaction.response.send_message("No candidates being tracked yet.", ephemeral=True)
        return
    lines = [
        f"`{t}` · {n}/{LEARN_HITS} {'✅ probing UD' if n >= LEARN_HITS else ''}".rstrip()
        for t, n in rows
    ]
    e = discord.Embed(
        title="📊 Pending slang",
        description="\n".join(lines),
        color=0xF1C40F,
    )
    e.set_footer(text=f"Auto-learns at {LEARN_HITS}+ sightings & ≥{LEARN_MIN_NET} net UD votes")
    await interaction.response.send_message(embed=e, ephemeral=True)


bot.tree.add_command(slang_group)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Set DISCORD_TOKEN in your environment or .env file.")
    bot.run(TOKEN)
