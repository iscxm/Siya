import os
import re
import yt_dlp
import random
import asyncio
import aiohttp
from pathlib import Path
from typing import Optional, Union

from pyrogram import enums, types
from py_yt import Playlist, VideosSearch

from Dev import config, logger
from Dev.helpers import Track, utils


class YouTube:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = re.compile(
            r"(https?://)?(www\.|m\.|music\.)?"
            r"(youtube\.com/(watch\?v=|shorts/|playlist\?list=)|youtu\.be/)"
            r"([A-Za-z0-9_-]{11}|PL[A-Za-z0-9_-]+)([&?][^\s]*)?"
        )

    def valid(self, url: str) -> bool:
        return bool(re.match(self.regex, url))

    def url(self, message_1: types.Message) -> Union[str, None]:
        messages = [message_1]
        link = None
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)

        for message in messages:
            text = message.text or message.caption or ""

            if message.entities:
                for entity in message.entities:
                    if entity.type == enums.MessageEntityType.URL:
                        link = text[entity.offset : entity.offset + entity.length]
                        break

            if message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == enums.MessageEntityType.TEXT_LINK:
                        link = entity.url
                        break

        if link:
            return link.split("&si")[0].split("?si")[0]
        return None

    async def search(self, query: str, m_id: int, video: bool = False) -> Track | None:
        _search = VideosSearch(query, limit=1)
        results = await _search.next()
        if results and results["result"]:
            data = results["result"][0]
            return Track(
                id=data.get("id"),
                channel_name=data.get("channel", {}).get("name"),
                duration=data.get("duration"),
                duration_sec=utils.to_seconds(data.get("duration")),
                message_id=m_id,
                title=data.get("title")[:25],
                thumbnail=data.get("thumbnails", [{}])[-1].get("url").split("?")[0],
                url=data.get("link"),
                view_count=data.get("viewCount", {}).get("short"),
                video=video,
            )
        return None

    async def playlist(self, limit: int, user: str, url: str, video: bool) -> list[Track | None]:
        tracks = []
        try:
            plist = await Playlist.get(url)
            for data in plist["videos"][:limit]:
                track = Track(
                    id=data.get("id"),
                    channel_name=data.get("channel", {}).get("name", ""),
                    duration=data.get("duration"),
                    duration_sec=utils.to_seconds(data.get("duration")),
                    title=data.get("title")[:25],
                    thumbnail=data.get("thumbnails")[-1].get("url").split("?")[0],
                    url=data.get("link").split("&list=")[0],
                    user=user,
                    view_count="",
                    video=video,
                )
                tracks.append(track)
        except:
            pass
        return tracks

    async def download(self, video_id: str, video: bool = False) -> Optional[str]:
        existing = next(Path("downloads").glob(f"{video_id}.*"), None)
        if existing:
            return str(existing)
            
        api_url = f"{config.EDEV_API_URL}?query=https://youtu.be/{video_id}&format={'video' if video else 'audio'}"
        try:
            import aiohttp
            import aiofiles
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("success") and data.get("stream_url"):
                            stream_url = data["stream_url"]
                            # Download the stream to local file to ensure pytgcalls can play it reliably
                            ext = "mp4" if video else "m4a"
                            file_path = f"downloads/{video_id}.{ext}"
                            async with session.get(stream_url) as stream_resp:
                                if stream_resp.status == 200:
                                    async with aiofiles.open(file_path, 'wb') as f:
                                        async for chunk in stream_resp.content.iter_chunked(1024 * 1024):
                                            await f.write(chunk)
                                    return file_path
        except Exception as e:
            logger.error(f"eDev API failed for {video_id}: {e}")

        url = self.base + video_id
        base_opts = {
            "outtmpl": "downloads/%(id)s.%(ext)s",
            "quiet": True,
            "noplaylist": True,
            "no_warnings": True,
            "overwrites": False,
            "nocheckcertificate": True,
            "geo_bypass": True,
            "concurrent_fragment_downloads": 4,
            "socket_timeout": 10,
            "retries": 3,
            "fragment_retries": 3,
        }

        if video:
            ydl_opts = {
                **base_opts,
                "format": (
                    "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/"
                    "bestvideo[height<=720]+bestaudio/"
                    "best[height<=720]/best"
                ),
                "merge_output_format": "mp4",
            }
        else:
            ydl_opts = {
                **base_opts,
                "format": (
                    "bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best"
                ),
            }

        def _download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    ydl.download([url])
                    path = next(Path("downloads").glob(f"{video_id}.*"), None)
                    return str(path) if path else None
                except yt_dlp.utils.DownloadError as ex:
                    err = str(ex)
                    if "Sign in" in err or "bot" in err:
                        logger.warning("IP blocked: %s", video_id)
                    else:
                        logger.error("Download failed: %s", ex)
                    return None
                except Exception as ex:
                    logger.error("Download failed: %s", ex)
                    return None

        return await asyncio.to_thread(_download)
