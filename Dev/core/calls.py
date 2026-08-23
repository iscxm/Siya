import asyncio
from ntgcalls import ConnectionNotFound, TelegramServerError
from pyrogram.errors import MessageIdInvalid
from pyrogram.types import InputMediaPhoto, Message
from pytgcalls import PyTgCalls, exceptions, types
from pytgcalls.pytgcalls_session import PyTgCallsSession

from Dev import app, config, db, lang, logger, queue, userbot, yt
from Dev.helpers import Media, Track, buttons, thumb
from Dev.plugins.loop import get_loop, set_loop


class TgCall(PyTgCalls):
    def __init__(self):
        self.clients = []

    async def pause(self, chat_id: int) -> bool:
        client = await db.get_assistant(chat_id)
        await db.playing(chat_id, paused=True)
        return await client.pause(chat_id)

    async def resume(self, chat_id: int) -> bool:
        client = await db.get_assistant(chat_id)
        await db.playing(chat_id, paused=False)
        return await client.resume(chat_id)

    async def stop(self, chat_id: int) -> None:
        client = await db.get_assistant(chat_id)
        try:
            queue.clear(chat_id)
            await db.remove_call(chat_id)
        except Exception:
            pass
        try:
            await client.leave_call(chat_id, close=False)
        except Exception:
            pass

    async def play_media(self, chat_id: int, message: Message, media: Media | Track, seek_time: int = 0) -> None:
        client = await db.get_assistant(chat_id)
        _lang = await lang.get_lang(chat_id)

        if not media.file_path:
            return await message.edit_text(_lang["error_no_file"].format(config.SUPPORT_CHAT))

        ffmpeg_params = "-vn " if not media.video else ""
        if seek_time > 0:
            ffmpeg_params += f"-ss {seek_time}"

        kwargs = {
            "media_path": media.file_path,
            "audio_parameters": types.AudioQuality.STUDIO,
            "video_parameters": types.VideoQuality.SD_480p,
            "audio_flags": types.MediaStream.Flags.REQUIRED,
            "video_flags": types.MediaStream.Flags.AUTO_DETECT if media.video else types.MediaStream.Flags.IGNORE,
        }
        if ffmpeg_params.strip():
            kwargs["ffmpeg_parameters"] = ffmpeg_params.strip()
            
        stream = types.MediaStream(**kwargs)
        try:
            await client.play(chat_id=chat_id, stream=stream)
            if not seek_time:
                media.time = 1
                await db.add_call(chat_id)
                await db.set_last_played(chat_id, {"id": media.id, "title": media.title})
                
                raw_thumb = getattr(media, "thumbnail", None) or config.DEFAULT_THUMB
                text = _lang["play_media"].format(media.url, media.title, media.duration, media.user)
                keyboard = buttons.controls(chat_id)
                
                try:
                    msg = await message.edit_media(media=InputMediaPhoto(media=raw_thumb, caption=text), reply_markup=keyboard)
                    media.message_id = msg.id if getattr(msg, "id", None) else message.id
                except MessageIdInvalid:
                    msg = await app.send_photo(chat_id=chat_id, photo=raw_thumb, caption=text, reply_markup=keyboard)
                    media.message_id = msg.id
                
                async def _update_thumb():
                    try:
                        _custom = await thumb.generate(media) if isinstance(media, Track) else raw_thumb
                        await db.track_play({
                            "id": media.id,
                            "title": media.title,
                            "url": media.url,
                            "thumbnail": _custom if isinstance(_custom, str) else None,
                            "duration": getattr(media, "duration", ""),
                        })
                        if _custom and _custom != raw_thumb:
                            await app.edit_message_media(
                                chat_id=chat_id,
                                message_id=media.message_id,
                                media=InputMediaPhoto(media=_custom, caption=text),
                                reply_markup=keyboard
                            )
                    except Exception:
                        pass
                
                asyncio.create_task(_update_thumb())
                asyncio.create_task(self._delete_msg(chat_id, media.message_id))
                
                from Dev.plugins.autoplay import cache_autoplay
                asyncio.create_task(cache_autoplay(chat_id, {"id": media.id, "title": media.title}))
                
                async def _prefetch_q():
                    from Dev.plugins.loop import get_loop
                    if await get_loop(chat_id) > 0: return
                    q = queue.get_queue(chat_id)
                    if q:
                        nxt = q[0]
                        if not nxt.file_path:
                            await yt.download(nxt.id, video=nxt.video)
                asyncio.create_task(_prefetch_q())
                
        except FileNotFoundError:
            await message.edit_text(_lang["error_no_file"].format(config.SUPPORT_CHAT))
            await self.play_next(chat_id)
        except exceptions.NoActiveGroupCall:
            await self.stop(chat_id)
            await message.edit_text(_lang["error_no_call"])
        except exceptions.NoAudioSourceFound:
            await message.edit_text(_lang["error_no_audio"])
            await self.play_next(chat_id)
        except (ConnectionNotFound, TelegramServerError):
            await self.stop(chat_id)
            await message.edit_text(_lang["error_tg_server"])

    async def _delete_msg(self, chat_id: int, message_id: int) -> None:
        await asyncio.sleep(12)
        try:
            await app.delete_messages(chat_id=chat_id, message_ids=message_id)
        except Exception:
            pass

    async def replay(self, chat_id: int) -> None:
        if not await db.get_call(chat_id):
            return
        media = queue.get_current(chat_id)
        _lang = await lang.get_lang(chat_id)
        msg = await app.send_message(chat_id=chat_id, text=_lang["play_again"])
        await self.play_media(chat_id, msg, media)

    async def play_next(self, chat_id: int) -> None:
        if not hasattr(self, "_is_processing"):
            self._is_processing = {}
            
        if self._is_processing.get(chat_id):
            return
            
        self._is_processing[chat_id] = True
        try:
            await self._play_next_logic(chat_id)
        finally:
            self._is_processing.pop(chat_id, None)

    async def _play_next_logic(self, chat_id: int) -> None:
        if not await db.get_call(chat_id):
            return

        loop_count = await get_loop(chat_id)
        current = queue.get_current(chat_id)

        if loop_count > 0 and current:
            current.time = 0
            await set_loop(chat_id, loop_count - 1)
            _lang = await lang.get_lang(chat_id)
            msg = await app.send_message(chat_id=chat_id, text=_lang["play_again"])
            current.message_id = msg.id
            await self.play_media(chat_id, msg, current)
            return

        media = queue.get_next(chat_id)

        try:
            if media and media.message_id:
                await app.delete_messages(chat_id=chat_id, message_ids=media.message_id, revoke=True)
                media.message_id = 0
        except Exception:
            pass

        if not media:
            if await db.get_autoplay(chat_id):
                await self._autoplay_next(chat_id)
            else:
                await self.stop(chat_id)
            return

        _lang = await lang.get_lang(chat_id)
        msg = await app.send_message(chat_id=chat_id, text=_lang["play_next"])

        if not media.file_path:
            media.file_path = await yt.download(media.id, video=media.video)
            if not media.file_path:
                await self.stop(chat_id)
                await msg.edit_text(_lang["error_no_file"].format(config.SUPPORT_CHAT))
                return

        media.message_id = msg.id
        await asyncio.sleep(1.5)
        await self.play_media(chat_id, msg, media)

    async def _autoplay_next(self, chat_id: int) -> None:
        from Dev.plugins.autoplay import get_autoplay, get_next_autoplay_track
        from Dev.helpers import utils

        if not await get_autoplay(chat_id):
            await self.stop(chat_id)
            return

        last = await db.get_last_played(chat_id)
        if not last:
            await self.stop(chat_id)
            return

        related = await get_next_autoplay_track(chat_id, last)
        if not related:
            await self.stop(chat_id)
            return

        file_path = await yt.download(related["id"], video=False)
        if not file_path:
            related2 = await get_next_autoplay_track(chat_id, last)
            if related2:
                file_path = await yt.download(related2["id"], video=False)
                related = related2
        if not file_path:
            await self.stop(chat_id)
            return

        _lang = await lang.get_lang(chat_id)
        msg = await app.send_message(chat_id=chat_id, text=_lang["play_next"])

        track = Track(
            id=related["id"],
            title=related["title"][:25],
            duration=related.get("duration", ""),
            duration_sec=utils.to_seconds(related.get("duration", "")),
            url=related.get("url", f"https://www.youtube.com/watch?v={related['id']}"),
            thumbnail=related.get("thumbnail", f"https://i.ytimg.com/vi/{related['id']}/hqdefault.jpg"),
            channel_name="",
            view_count="",
            user="Autoplay",
            message_id=msg.id,
            video=False,
            file_path=file_path,
        )

        queue.force_add(chat_id, track)
        await self.play_media(chat_id, msg, track)

    async def ping(self) -> float:
        pings = [client.ping for client in self.clients]
        return round(sum(pings) / len(pings), 2)

    async def decorators(self, client: PyTgCalls) -> None:
        for client in self.clients:
            @client.on_update()
            async def update_handler(_, update: types.Update) -> None:
                if isinstance(update, types.StreamEnded):
                    if update.stream_type == types.StreamEnded.Type.AUDIO:
                        await asyncio.sleep(1.5)
                        await self.play_next(update.chat_id)
                elif isinstance(update, types.ChatUpdate):
                    if update.status in [types.ChatUpdate.Status.KICKED, types.ChatUpdate.Status.LEFT_GROUP, types.ChatUpdate.Status.CLOSED_VOICE_CHAT]:
                        await self.stop(update.chat_id)

    async def boot(self) -> None:
        PyTgCallsSession.notice_displayed = True
        for ub in userbot.clients:
            client = PyTgCalls(ub, cache_duration=100)
            await client.start()
            self.clients.append(client)
            await self.decorators(client)
        logger.info("Toxic PyTgCalls client(s) started.")
