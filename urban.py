"""Thin client for the unofficial Urban Dictionary API."""

import aiohttp

API = "https://api.urbandictionary.com/v0/define"
_TIMEOUT = aiohttp.ClientTimeout(total=10)


async def define(term: str):
    """Top Urban Dictionary definition for `term`, or None if no entry.

    Returns word/definition/example/permalink/up/down/net.
    """
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.get(API, params={"term": term}) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
    except (aiohttp.ClientError, TimeoutError):
        return None

    entries = data.get("list") or []
    if not entries:
        return None

    entries.sort(
        key=lambda e: e.get("thumbs_up", 0) - e.get("thumbs_down", 0), reverse=True
    )
    top = entries[0]

    def clean(s):
        return (s or "").replace("[", "").replace("]", "").strip()

    up = top.get("thumbs_up", 0)
    down = top.get("thumbs_down", 0)
    return {
        "word": top.get("word", term),
        "definition": clean(top.get("definition")),
        "example": clean(top.get("example")),
        "permalink": top.get("permalink", ""),
        "up": up,
        "down": down,
        "net": up - down,
    }
