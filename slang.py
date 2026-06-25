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

# Context guards — many slang terms double as ordinary English. A hit is
# suppressed when the surrounding word shows literal use (e.g. "based off of",
# "fire department", "lit up"). Keyed by term (lowercase); values are the words
# that, when they sit immediately after / before the term, mean "not slang".
# Conservative on purpose — easy to extend as false positives turn up.
LITERAL_NEXT = {
    "based": {"off", "on", "in", "upon", "out", "around", "near", "at"},
    "cap": {"of"},
    "cope": {"with"},
    "drip": {"of"},
    "fire": {"alarm", "department", "truck", "wood", "works", "fighter",
             "fighters", "place", "pit", "extinguisher", "hydrant"},
    "goat": {"cheese", "milk", "farm", "meat"},
    "lit": {"up"},
    "mid": {"section", "day", "week", "night", "term", "field", "range",
            "point", "west", "east", "level", "size", "century", "morning"},
    "ratio": {"of"},
    "cooked": {"the", "a", "dinner", "breakfast", "lunch", "meal", "food",
               "rice", "chicken", "eggs", "pasta"},
}
LITERAL_PREV = {
    "based": {"is", "was", "are", "be", "been", "being", "company", "team"},
    "cap": {"bottle", "knee", "ball", "the", "a", "kneecap"},
    "fire": {"a", "the", "camp", "cease", "open", "wild", "gun", "rapid"},
    "goat": {"a", "the", "mountain", "pet", "billy"},
    "ohio": {"in", "from", "to", "near", "of", "leaving", "visit", "visiting"},
}

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


def _literal_use(low: str, prev: str, nxt: str) -> bool:
    """True if the term is being used in plain English, not as slang."""
    return nxt in LITERAL_NEXT.get(low, ()) or prev in LITERAL_PREV.get(low, ())


def find_slang(text: str, known: set):
    """First active-or-suffix slang term in text (original case), else None.

    Skips hits that look like ordinary English given the neighbouring words
    (e.g. "based off of ..." -> not the slang "based")."""
    toks = _TOKEN_RE.findall(text)
    for i, raw in enumerate(toks):
        low = raw.lower()
        if not _is_hit(low, known):
            continue
        prev = toks[i - 1].lower() if i > 0 else ""
        nxt = toks[i + 1].lower() if i + 1 < len(toks) else ""
        if _literal_use(low, prev, nxt):
            continue
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
