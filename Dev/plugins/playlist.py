from pyrogram import filters, types
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from Dev import app, config, db, lang, queue, unnati, yt
from Dev.helpers import Track, utils
from Dev.helpers._spotify import parse_spotify, valid as spotify_valid


_rec_cache: dict[tuple[int, str], dict] = {}
_last_playlist: dict[int, list[dict]] = {}

SPOTIFY_IMPORT_LIMIT = 300


def _track_to_dict(track) -> dict:
    return {
        "id": track.id,
        "title": track.title,
        "duration": getattr(track, "duration", "") or "",
        "url": track.url,
        "thumbnail": getattr(track, "thumbnail", None) or config.DEFAULT_THUMB,
        "video": getattr(track, "video", False),
    }


def _dict_to_track(t: dict, mention: str) -> Track:
    return Track(
        id=t["id"],
        channel_name="",
        duration=t.get("duration", ""),
        duration_sec=utils.to_seconds(t["duration"]) if t.get("duration") else 0,
        title=t["title"][:25],
        thumbnail=t.get("thumbnail"),
        url=t["url"],
        user=mention,
        view_count="",
        video=t.get("video", False),
    )



@app.on_message(filters.command(["add", "addsong"]) & ~app.bl_users)
@lang.language()
async def pladd_cmd(_, m: types.Message):
    if len(m.command) < 2:
        return await m.reply_text(
            "<b>Usage:</b> <code>/add playlist_name [song name]</code>\n\n"
            "If you don't give a song name, the song currently playing in the group will be added."
        )

    name = m.command[1]
    query = " ".join(m.command[2:]).strip()
    user_id = m.from_user.id

    if query:
        sent = await m.reply_text("Searching...")
        track = await yt.search(query, sent.id)
        if not track:
            return await sent.edit_text("Song not found.")
    else:
        if m.chat.type == "private":
            return await m.reply_text(
                "To add the song currently playing, send this command in the group, "
                "or provide a song name: <code>/add playlist_name song name</code>"
            )
        current = queue.get_current(m.chat.id)
        if not current:
            return await m.reply_text(
                "No song is playing right now. You can also give a song name: "
                "<code>/add playlist_name song name</code>"
            )
        track = current
        sent = await m.reply_text("Adding...")

    track_dict = _track_to_dict(track)
    count = await db.add_to_playlist(user_id, name, track_dict)
    await sent.edit_text(
        f"<b>{track.title}</b> has been added to playlist \"<b>{name}</b>\". ({count} songs total)"
    )


@app.on_message(filters.command(["list", "myplaylists"]) & ~app.bl_users)
@lang.language()
async def pllist_cmd(_, m: types.Message):
    playlists = await db.get_playlists(m.from_user.id)
    if not playlists:
        return await m.reply_text(
            "You don't have any playlists yet.\n"
            "Create one with <code>/add playlist_name song name</code>."
        )
    text = "<b>Your Playlists:</b>\n\n"
    for name, tracks in playlists.items():
        text += f"- <b>{name}</b> - {len(tracks)} songs\n"
    text += "\nTo view: <code>/plsongs name</code>\nTo play: <code>/plplay name</code>"
    await m.reply_text(text)


@app.on_message(filters.command(["plsongs", "view"]) & ~app.bl_users)
@lang.language()
async def plsongs_cmd(_, m: types.Message):
    if len(m.command) < 2:
        return await m.reply_text("Usage: <code>/plsongs playlist_name</code>")
    name = " ".join(m.command[1:])
    tracks = await db.get_playlist(m.from_user.id, name)
    if not tracks:
        return await m.reply_text(f"Playlist \"{name}\" is empty or doesn't exist.")

    text = f"<b>{name}</b> ({len(tracks)} songs)\n<blockquote expandable>"
    for i, t in enumerate(tracks, start=1):
        text += f"<b>{i}.</b> {t['title']} - {t.get('duration', '')}\n"
    text = text[:3900] + "</blockquote>"
    await m.reply_text(text)


@app.on_message(filters.command(["del"]) & ~app.bl_users)
@lang.language()
async def plremove_cmd(_, m: types.Message):
    if len(m.command) < 3 or not m.command[-1].isdigit():
        return await m.reply_text("Usage: <code>/del playlist_name position</code>")
    pos = int(m.command[-1])
    name = " ".join(m.command[1:-1])
    ok = await db.remove_from_playlist(m.from_user.id, name, pos)
    await m.reply_text("Song removed." if ok else "Invalid position or playlist name.")


@app.on_message(filters.command(["pldel", "delplaylist"]) & ~app.bl_users)
@lang.language()
async def pldel_cmd(_, m: types.Message):
    if len(m.command) < 2:
        return await m.reply_text("Usage: <code>/pldel playlist_name</code>")
    name = " ".join(m.command[1:])
    ok = await db.delete_playlist(m.from_user.id, name)
    await m.reply_text(
        f"Playlist \"{name}\" has been deleted." if ok else f"Playlist \"{name}\" not found."
    )


@app.on_message(filters.command(["plplay"]) & filters.group & ~app.bl_users)
@lang.language()
async def plplay_cmd(_, m: types.Message):
    if len(m.command) < 2:
        return await m.reply_text("Usage: <code>/plplay playlist_name [position]</code>")

    args = m.command[1:]
    start_pos = 1
    if len(args) >= 2 and args[-1].isdigit():
        start_pos = int(args[-1])
        name = " ".join(args[:-1])
    else:
        name = " ".join(args)

    chat_id = m.chat.id

    if not await db.get_call(chat_id):
        return await m.reply_text(
            "First start the voice chat with <code>/play</code>, "
            "then use <code>/plplay</code> to queue the playlist - all songs will play one by one."
        )

    tracks = await db.get_playlist(m.from_user.id, name)
    if not tracks:
        # Fallback: maybe the last part wasn't a position but part of the name
        full_name = " ".join(args)
        tracks_fallback = await db.get_playlist(m.from_user.id, full_name)
        if tracks_fallback:
            name = full_name
            tracks = tracks_fallback
            start_pos = 1
        else:
            return await m.reply_text(f"Playlist \"{name}\" is empty or doesn't exist.")

    if start_pos < 1 or start_pos > len(tracks):
        return await m.reply_text(f"Invalid position. Playlist \"{name}\" only has {len(tracks)} songs.")

    tracks = tracks[start_pos - 1:]

    room = config.QUEUE_LIMIT - len(queue.get_queue(chat_id))
    if room <= 0:
        return await m.reply_text("Queue is already full.")
    tracks = tracks[:room]

    sent = await m.reply_text("Adding playlist to the queue...")
    text = "<blockquote expandable>"
    added = 0
    for t in tracks:
        file = _dict_to_track(t, m.from_user.mention)
        pos = queue.add(chat_id, file)
        added += 1
        text += f"<b>{pos}.</b> {file.title}\n"
    text = text[:1948] + "</blockquote>"

    _last_playlist[chat_id] = tracks

    await sent.edit_text(
        f"<b>{added}</b> songs from \"<b>{name}</b>\" added to the queue, they will play one after another:\n{text}"
    )


@app.on_message(filters.command(["fav", "favourite", "favorite"]) & filters.group & ~app.bl_users)
@lang.language()
async def fav_cmd(_, m: types.Message):
    current = queue.get_current(m.chat.id)
    if not current:
        return await m.reply_text("No song is playing right now. Play a song first to favorite it.")

    track_dict = _track_to_dict(current)
    await db.add_favorite(m.from_user.id, track_dict)
    await m.reply_text(
        f"<b>{current.title}</b> has been added to your personal favorites and the global favorites!"
    )


@app.on_message(filters.command(["myfav", "myfavorites", "myfavourites"]) & ~app.bl_users)
@lang.language()
async def myfav_cmd(_, m: types.Message):
    favs = await db.get_favorites(m.from_user.id)
    if not favs:
        return await m.reply_text(
            "You don't have any personal favorites yet.\n"
            "Play a song in the group and use <code>/fav</code> to favorite it."
        )
    text = "<b>Your Personal Favorites:</b>\n\n<blockquote expandable>"
    for i, t in enumerate(favs[:50], start=1):
        text += f"<b>{i}.</b> {t['title']} - {t.get('duration', '')}\n"
    text = text[:3900] + "</blockquote>"
    await m.reply_text(text)


@app.on_message(filters.command(["topfav", "globalfav"]) & ~app.bl_users)
@lang.language()
async def topfav_cmd(_, m: types.Message):
    top = await db.get_global_favorites(15)
    if not top:
        return await m.reply_text("No favorites yet.")
    text = "<b>Global Favorites (everyone's favorite songs):</b>\n\n"
    for i, t in enumerate(top, start=1):
        text += f"<b>{i}.</b> {t['title']} - {t.get('count', 0)}\n"
    await m.reply_text(text)


@app.on_message(filters.command(["top", "mostplayed"]) & ~app.bl_users)
@lang.language()
async def mostplayed_cmd(_, m: types.Message):
    top = await db.get_most_played(15)
    if not top:
        return await m.reply_text("No song has been played yet.")
    text = "<b>Most Played Songs:</b>\n\n"
    for i, t in enumerate(top, start=1):
        text += f"<b>{i}.</b> {t['title']} - {t.get('count', 0)} plays\n"
    await m.reply_text(text)


# ---------------------------------------------------------------------------
# SPOTIFY LINK IMPORT (playlist/track/album link songs saved to a playlist)
# ---------------------------------------------------------------------------

@app.on_message(filters.command(["spotify", "spimport"]) & ~app.bl_users)
@lang.language()
async def spotify_cmd(_, m: types.Message):
    if len(m.command) < 2:
        return await m.reply_text(
            "<b>Usage:</b> <code>/spotify spotify_link [playlist_name]</code>\n\n"
            "Give a Spotify playlist/track/album link - its songs will be matched on YouTube\n"
            "and saved to your playlist."
        )

    link = m.command[1]
    playlist_name = " ".join(m.command[2:]).strip() or "spotify import"

    if not spotify_valid(link):
        return await m.reply_text("Please give a valid Spotify link (open.spotify.com playlist/track/album link).")

    sent = await m.reply_text("Fetching songs from Spotify...")
    kind, sp_tracks = await parse_spotify(link, limit=SPOTIFY_IMPORT_LIMIT)

    if not sp_tracks:
        return await sent.edit_text("Could not fetch songs from that Spotify link. Check the link or try again later.")

    await sent.edit_text(f"Found {len(sp_tracks)} songs, matching them on YouTube (this may take a moment)...")

    saved = 0
    text = "<blockquote expandable>"
    for sp in sp_tracks:
        query = f"{sp['name']} {sp.get('artists', '')}".strip()
        track = await yt.search(query, sent.id)
        if not track:
            continue
        await db.add_to_playlist(m.from_user.id, playlist_name, _track_to_dict(track))
        saved += 1
        text += f"<b>{saved}.</b> {track.title}\n"
    text = text[:3900] + "</blockquote>"

    if not saved:
        return await sent.edit_text("None of the songs could be matched on YouTube.")

    await sent.edit_text(
        f"<b>{saved}</b> songs saved to playlist \"<b>{playlist_name}</b>\"!\n{text}\n"
        f"To play it in a group: <code>/plplay {playlist_name}</code>"
    )


# ---------------------------------------------------------------------------
# RECOMMENDATIONS (suggest songs similar to the last played track)
# ---------------------------------------------------------------------------

@app.on_message(filters.command(["recommend", "rec"]) & filters.group & ~app.bl_users)
@lang.language()
async def recommend_cmd(_, m: types.Message):
    from Dev.plugins.autoplay import _fetch_mix_playlist, _fetch_mix_via_innertube

    chat_id = m.chat.id
    last = await db.get_last_played(chat_id)
    if not last:
        return await m.reply_text("Play a song first, then I can recommend similar ones.")

    sent = await m.reply_text("Looking for similar songs...")
    tracks = await _fetch_mix_playlist(last["id"])
    if not tracks:
        tracks = await _fetch_mix_via_innertube(last["id"])
    if not tracks:
        return await sent.edit_text("Couldn't find recommendations, try again in a bit.")

    tracks = tracks[:10]
    text = f"<b>Recommended, similar to \"{last['title']}\":</b>\n\n"
    keyboard = []
    for i, t in enumerate(tracks, start=1):
        text += f"{i}. {t['title']} - {t.get('duration', '')}\n"
        _rec_cache[(chat_id, t["id"])] = t
        keyboard.append(
            [InlineKeyboardButton(f"{i}. {t['title'][:22]}", callback_data=f"recadd_{chat_id}_{t['id']}")]
        )

    await sent.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


@app.on_callback_query(filters.regex(r"^recadd_(-?\d+)_([\w-]+)$"))
async def recommend_add_cb(_, q: types.CallbackQuery):
    chat_id = int(q.matches[0].group(1))
    vid_id = q.matches[0].group(2)

    track_data = _rec_cache.get((chat_id, vid_id))
    if not track_data:
        return await q.answer("This list has expired, run /recommend again.", show_alert=True)

    await q.answer("Adding...")
    file = _dict_to_track(track_data, q.from_user.mention)

    if await db.get_call(chat_id):
        position = queue.add(chat_id, file)
        await q.message.reply_text(f"Added to queue: <b>{file.title}</b> (position {position})")
    else:
        msg = await app.send_message(chat_id=chat_id, text="Downloading & playing...")
        file.file_path = await yt.download(file.id, video=False)
        file.message_id = msg.id
        if not file.file_path:
            return await msg.edit_text("Download failed, try again.")
        await unnati.play_media(chat_id=chat_id, message=msg, media=file)


# ---------------------------------------------------------------------------
# NEW PLAYLIST FEATURES (Copy, View, Replay)
# ---------------------------------------------------------------------------

import asyncio

@app.on_message(filters.command(["cp", "copy"], prefixes=["/", "."]) & ~app.bl_users)
@lang.language()
async def cp_cmd(_, m: types.Message):
    args = m.command[1:]
    target_user = None
    target_name = None

    if m.reply_to_message:
        target_user = m.reply_to_message.from_user
        target_name = " ".join(args).strip() if args else None
    else:
        if not args:
            return await m.reply_text("Reply to a user's message or provide their username/id to copy their collection.")
        try:
            target_user = await app.get_users(args[0])
            target_name = " ".join(args[1:]).strip() if len(args) > 1 else None
        except Exception:
            return await m.reply_text("Could not find that user.")

    if not target_user:
        return await m.reply_text("Could not find that user.")

    if target_user.id == m.from_user.id:
        return await m.reply_text("You can't copy from yourself, genius.")

    sent = await m.reply_text("Attacking........")
    await asyncio.sleep(1.5)
    await sent.edit_text("Access Granted.....")
    await asyncio.sleep(1)
    
    target_playlists = await db.get_playlists(target_user.id)
    if not target_playlists:
        return await sent.edit_text("Target has nothing to steal... Mission Failed. ❌")
        
    await sent.edit_text("Initiating Database Breach... ⚡\nBypassing Security Firewalls... 🛡️\nExtracting Target Data... 💾")
    await asyncio.sleep(2)
    
    await sent.edit_text("Doing....")
    
    saved = 0
    if target_name:
        if target_name not in target_playlists:
            return await sent.edit_text("Requested data block not found in target's database... Mission Failed. ❌")
        
        for track in target_playlists[target_name]:
            await db.add_to_playlist(m.from_user.id, target_name, track)
            saved += 1
    else:
        for name, tracks in target_playlists.items():
            for track in tracks:
                await db.add_to_playlist(m.from_user.id, name, track)
                saved += 1
                
    await asyncio.sleep(1.5)
    await sent.edit_text(
        f"Its done bro {m.from_user.mention}\n\n"
        f"Mission Successful! 🟢\n"
        f"Successfully injected <b>{saved}</b> encrypted data blocks into your secure vault.\n"
        f"Hack Complete. System returning to normal operations."
    )


@app.on_message(filters.command(["view"]) & ~app.bl_users)
@lang.language()
async def view_cmd(_, m: types.Message):
    args = m.command[1:]
    target_user = None

    if m.reply_to_message:
        target_user = m.reply_to_message.from_user
    else:
        if not args:
            return await m.reply_text("Reply to a user's message or provide their username/id.")
        try:
            target_user = await app.get_users(args[0])
        except Exception:
            return await m.reply_text("Could not find that user.")
            
    if not target_user:
        return await m.reply_text("Could not find that user.")

    playlists = await db.get_playlists(target_user.id)
    if not playlists:
        return await m.reply_text(f"{target_user.first_name} has an empty collection.")

    text = f"<b>{target_user.first_name}'s Collection:</b>\n\n"
    for name, tracks in playlists.items():
        text += f"- <b>{name}</b> - {len(tracks)} items\n"
    
    await m.reply_text(text)


@app.on_message(filters.command(["rp"]) & filters.group & ~app.bl_users)
@lang.language()
async def rp_cmd(_, m: types.Message):
    chat_id = m.chat.id
    if chat_id not in _last_playlist or not _last_playlist[chat_id]:
        return await m.reply_text("No previous collection sequence found to replay in this chat.")

    if not await db.get_call(chat_id):
        return await m.reply_text("Start the voice chat with <code>/play</code> first.")

    tracks = _last_playlist[chat_id]
    room = config.QUEUE_LIMIT - len(queue.get_queue(chat_id))
    if room <= 0:
        return await m.reply_text("Queue is already full.")
    
    tracks = tracks[:room]
    
    sent = await m.reply_text("Injecting previous sequence into the system queue...")
    text = "<blockquote expandable>"
    added = 0
    for t in tracks:
        file = _dict_to_track(t, m.from_user.mention)
        pos = queue.add(chat_id, file)
        added += 1
        text += f"<b>{pos}.</b> {file.title}\n"
    text = text[:1948] + "</blockquote>"

    await sent.edit_text(
        f"<b>{added}</b> items re-injected into the queue sequence:\n{text}"
    )
