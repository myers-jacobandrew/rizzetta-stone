"""Slang detection + auto-learn gating.

A word fires a card if:
  1. it's an active term in the DB (seeded, learned, or hand-added), OR
  2. it ends in a productive suffix (-maxxing, -pilled, -mogging, ...).

Words that are none of the above become auto-learn *candidates*: if one gets
used enough and Urban Dictionary confirms it's real + popular + not plain
English, the bot promotes it to an active term on its own. See db.py / bot.py.
"""

import re

# Seed list — just gets the DB started on first run. After that the DB is the
# source of truth and grows itself. Lowercase only.
SEED_WORDS = {
    "rizz", "rizzler", "mewing", "mogging", "mogged", "looksmaxxing", "sigma",
    "skibidi", "gyatt", "gyat", "fanum", "ohio", "sus", "cap", "bussin",
    "sheesh", "drip", "fr", "ong", "tuff", "gooning", "glazing", "yap",
    "yapping", "delulu", "aura", "npc", "ratio", "cooked", "edging", "huzz",
    "tweaking", "pmo", "diddy", "demure", "mindful", "brainrot", "based",
    "cringe", "cope", "ick", "slay", "mid", "goat", "baddie", "simp", "crashout",
}

# Productive suffixes — any token ending in one of these fires immediately,
# which is how endless "-maxxing"/"-pilled" coinages work with zero upkeep.
SUFFIXES = (
    "maxxing", "maxx", "maxing", "pilled", "mogging", "coded",
)

_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z'\-]*[a-zA-Z]|[a-zA-Z]")

# Common English — auto-learn skips these so the bot never "learns" the/and/lol.
# Doesn't need to be exhaustive; it just kills the obvious false positives. The
# Urban Dictionary vote threshold (bot.py) does the rest of the filtering.
COMMON = {
    "the","be","to","of","and","a","in","that","have","i","it","for","not","on",
    "with","he","as","you","do","at","this","but","his","by","from","they","we",
    "say","her","she","or","an","will","my","one","all","would","there","their",
    "what","so","up","out","if","about","who","get","which","go","me","when",
    "make","can","like","time","no","just","him","know","take","people","into",
    "year","your","good","some","could","them","see","other","than","then","now",
    "look","only","come","its","over","think","also","back","after","use","two",
    "how","our","work","first","well","way","even","new","want","because","any",
    "these","give","day","most","us","is","are","was","were","been","has","had",
    "did","got","going","really","right","here","much","too","very","still","why",
    "where","something","someone","never","always","every","please","thanks","yeah",
    "okay","ok","lol","lmao","bro","man","dude","guys","hey","gonna","wanna","im",
    "dont","cant","wont","didnt","thats","whats","hes","shes","theyre","were",
    "youre","ive","id","ill","ya","nah","yep","yup","hmm","stuff","things","love",
    "hate","feel","need","tell","ask","try","let","put","keep","play","game","games",
    "today","tonight","tomorrow","week","month","actually","probably","maybe","sure",
    "thing","said","talk","talking","made","using","used","best","better","kinda",
    "sorta","lowkey","highkey",
}


def is_learnable(word: str) -> bool:
    """Could this unknown token plausibly be new slang worth checking?"""
    w = word.lower()
    return len(w) >= 4 and w not in COMMON and w.isalpha()


def _is_hit(low: str, known: set) -> bool:
    if low in known:
        return True
    return any(low.endswith(suf) and len(low) > len(suf) for suf in SUFFIXES)


def find_slang(text: str, known: set):
    """First active-or-suffix slang term in text (original case), else None."""
    for raw in _TOKEN_RE.findall(text):
        if _is_hit(raw.lower(), known):
            return raw
    return None


def candidate_tokens(text: str, known: set):
    """Distinct learnable unknown tokens — the auto-learn candidates."""
    out, seen = [], set()
    for raw in _TOKEN_RE.findall(text):
        low = raw.lower()
        if low in seen or _is_hit(low, known):
            continue
        if is_learnable(low):
            seen.add(low)
            out.append(raw)
    return out
