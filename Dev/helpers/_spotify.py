import json
import re

import aiohttp

SPOTIFY_RE = re.compile(
    r"open\.spotify\.com/(?:intl-[a-z]{2}/)?(playlist|track|album)/([A-Za-z0-9]+)"
)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def valid(url: str) -> bool:
    return bool(SPOTIFY_RE.search(url))


async def parse_spotify(url: str, limit: int = 50) -> tuple[str | None, list[dict]]:
    match = SPOTIFY_RE.search(url)
    if not match:
        return None, []

    kind, sid = match.group(1), match.group(2)
    embed_url = f"https://open.spotify.com/embed/{kind}/{sid}"

    try:
        async with aiohttp.ClientSession(headers=_HEADERS) as session:
            async with session.get(
                embed_url, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                html = await resp.text()
    except Exception:
        return kind, []

    marker = '<script id="__NEXT_DATA__" type="application/json">'
    start = html.find(marker)
    if start == -1:
        return kind, []
    start += len(marker)
    end = html.find("</script>", start)
    if end == -1:
        return kind, []

    try:
        data = json.loads(html[start:end])
        entity = data["props"]["pageProps"]["state"]["data"]["entity"]
    except Exception:
        return kind, []

    tracks: list[dict] = []
    try:
        if kind == "track":
            name = entity.get("title") or entity.get("name")
            artists = entity.get("subtitle", "")
            if name:
                tracks.append({"name": name, "artists": artists})
        else:
            for item in entity.get("trackList", [])[:limit]:
                name = item.get("title")
                artists = item.get("subtitle", "")
                if name:
                    tracks.append({"name": name, "artists": artists})
    except Exception:
        pass

    return kind, tracks
