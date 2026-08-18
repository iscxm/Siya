import json
import asyncio
from pathlib import Path
from random import randint
from time import time

from pymongo import AsyncMongoClient

from Dev import config, logger, userbot, app


class MongoDB:
    def __init__(self):
        self.mongo = AsyncMongoClient(config.MONGO_URL, serverSelectionTimeoutMS=12500)
        self.db = self.mongo.unnati

        self.admin_list = {}
        self.active_calls = {}
        self.admin_play = []
        self.blacklisted = []
        self.autoplay_chats = []
        self.notified = []
        self.cache = self.db.cache
        self.logger = False

        self.assistant = {}
        self.assistantdb = self.db.assistant

        self.auth = {}
        self.authdb = self.db.auth

        self.chats = []
        self.chatsdb = self.db.chats

        self.lang = {}
        self.langdb = self.db.lang

        self.users = []
        self.usersdb = self.db.users

        self.playlistsdb = self.db.playlists
        self.favoritesdb = self.db.favorites
        self.mostplayeddb = self.db.mostplayed

        self.chatbotdb = self.db.chatbot
        self.chat_historydb = self.db.chat_history
        self.gamedb = self.db.game

        # Puguin (Azure AI Foundry agent)
        self.puguindb = self.db.puguin
        self.puguin_historydb = self.db.puguin_history
        self.puguin_factsdb = self.db.puguin_facts

    async def connect(self) -> None:
        try:
            start = time()
            await self.mongo.admin.command("ping")
            logger.info(f"Database connection successful. ({time() - start:.2f}s)")
            await self.load_cache()
            
            from Dev import tasks
            tasks.append(asyncio.create_task(self.backup_loop()))
        except Exception as e:
            raise SystemExit(f"Database connection failed: {type(e).__name__}") from e

    async def close(self) -> None:
        await self.mongo.close()
        logger.info("Database connection closed.")

    async def backup_loop(self):
        while True:
            await asyncio.sleep(604800)
            await self.backup_to_json()

    async def backup_to_json(self):
        try:
            data = {
                "chats": [doc async for doc in self.chatsdb.find()],
                "users": [doc async for doc in self.usersdb.find()],
                "playlists": [doc async for doc in self.playlistsdb.find()],
                "favorites": [doc async for doc in self.favoritesdb.find()],
                "mostplayed": [doc async for doc in self.mostplayeddb.find()],
                "lang": [doc async for doc in self.langdb.find()],
                "assistant": [doc async for doc in self.assistantdb.find()],
                "auth": [doc async for doc in self.authdb.find()],
                "cache": [doc async for doc in self.cache.find()]
            }
            file_path = Path("database.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, default=str)
            
            await app.send_document(
                config.LOGGER_ID,
                document=str(file_path),
                caption=f"Automated 7-Day Database Backup - {time()}"
            )
            file_path.unlink(missing_ok=True)
            logger.info("Automated database backup completed.")
        except Exception as e:
            logger.error(f"Failed to backup database to JSON: {e}")

    async def get_call(self, chat_id: int) -> bool:
        return chat_id in self.active_calls

    async def add_call(self, chat_id: int) -> None:
        self.active_calls[chat_id] = 1

    async def remove_call(self, chat_id: int) -> None:
        self.active_calls.pop(chat_id, None)

    async def playing(self, chat_id: int, paused: bool = None) -> bool | None:
        if paused is not None:
            self.active_calls[chat_id] = int(not paused)
        return bool(self.active_calls.get(chat_id, 0))

    async def get_admins(self, chat_id: int, reload: bool = False) -> list[int]:
        from Dev.helpers._admins import reload_admins
        if chat_id not in self.admin_list or reload:
            self.admin_list[chat_id] = await reload_admins(chat_id)
        return self.admin_list[chat_id]

    async def _get_auth(self, chat_id: int) -> set[int]:
        if chat_id not in self.auth:
            doc = await self.authdb.find_one({"_id": chat_id}) or {}
            self.auth[chat_id] = set(doc.get("user_ids", []))
        return self.auth[chat_id]

    async def is_auth(self, chat_id: int, user_id: int) -> bool:
        return user_id in await self._get_auth(chat_id)

    async def add_auth(self, chat_id: int, user_id: int) -> None:
        users = await self._get_auth(chat_id)
        if user_id not in users:
            users.add(user_id)
            await self.authdb.update_one(
                {"_id": chat_id}, {"$addToSet": {"user_ids": user_id}}, upsert=True
            )

    async def rm_auth(self, chat_id: int, user_id: int) -> None:
        users = await self._get_auth(chat_id)
        if user_id in users:
            users.discard(user_id)
            await self.authdb.update_one(
                {"_id": chat_id}, {"$pull": {"user_ids": user_id}}
            )

    async def set_assistant(self, chat_id: int) -> int:
        num = randint(1, len(userbot.clients))
        await self.assistantdb.update_one(
            {"_id": chat_id},
            {"$set": {"num": num}},
            upsert=True,
        )
        self.assistant[chat_id] = num
        return num

    async def get_assistant(self, chat_id: int):
        from Dev import unnati
        if chat_id not in self.assistant:
            doc = await self.assistantdb.find_one({"_id": chat_id})
            num = doc["num"] if doc else await self.set_assistant(chat_id)
            self.assistant[chat_id] = num
        return unnati.clients[self.assistant[chat_id] - 1]

    async def get_client(self, chat_id: int):
        if chat_id not in self.assistant:
            await self.get_assistant(chat_id)
        return {1: userbot.one, 2: userbot.two, 3: userbot.three}.get(
            self.assistant[chat_id]
        )

    async def add_blacklist(self, chat_id: int) -> None:
        if str(chat_id).startswith("-"):
            self.blacklisted.append(chat_id)
            return await self.cache.update_one(
                {"_id": "bl_chats"}, {"$addToSet": {"chat_ids": chat_id}}, upsert=True
            )
        await self.cache.update_one(
            {"_id": "bl_users"}, {"$addToSet": {"user_ids": chat_id}}, upsert=True
        )

    async def del_blacklist(self, chat_id: int) -> None:
        if str(chat_id).startswith("-"):
            if chat_id in self.blacklisted:
                self.blacklisted.remove(chat_id)
            return await self.cache.update_one(
                {"_id": "bl_chats"},
                {"$pull": {"chat_ids": chat_id}},
            )
        await self.cache.update_one(
            {"_id": "bl_users"},
            {"$pull": {"user_ids": chat_id}},
        )

    async def get_blacklisted(self, chat: bool = False) -> list[int]:
        if chat:
            if not self.blacklisted:
                doc = await self.cache.find_one({"_id": "bl_chats"})
                self.blacklisted.extend(doc.get("chat_ids", []) if doc else [])
            return self.blacklisted
        doc = await self.cache.find_one({"_id": "bl_users"})
        return doc.get("user_ids", []) if doc else []

    async def is_chat(self, chat_id: int) -> bool:
        return chat_id in self.chats

    async def add_chat(self, chat_id: int) -> None:
        if not await self.is_chat(chat_id):
            self.chats.append(chat_id)
            await self.chatsdb.update_one({"_id": chat_id}, {"$set": {"_id": chat_id}}, upsert=True)

    async def rm_chat(self, chat_id: int) -> None:
        if await self.is_chat(chat_id):
            self.chats.remove(chat_id)
            await self.chatsdb.delete_one({"_id": chat_id})

    async def get_chats(self) -> list:
        if not self.chats:
            self.chats.extend([chat["_id"] async for chat in self.chatsdb.find()])
        return self.chats

    async def set_lang(self, chat_id: int, lang_code: str):
        await self.langdb.update_one(
            {"_id": chat_id},
            {"$set": {"lang": lang_code}},
            upsert=True,
        )
        self.lang[chat_id] = lang_code

    async def get_lang(self, chat_id: int) -> str:
        if chat_id not in self.lang:
            doc = await self.langdb.find_one({"_id": chat_id})
            self.lang[chat_id] = doc["lang"] if doc else "en"
        return self.lang[chat_id]

    async def is_logger(self) -> bool:
        return self.logger

    async def get_logger(self) -> bool:
        doc = await self.cache.find_one({"_id": "logger"})
        if doc:
            self.logger = doc["status"]
        return self.logger

    async def set_logger(self, status: bool) -> None:
        self.logger = status
        await self.cache.update_one(
            {"_id": "logger"},
            {"$set": {"status": status}},
            upsert=True,
        )

    async def get_play_mode(self, chat_id: int) -> bool:
        if chat_id not in self.admin_play:
            doc = await self.chatsdb.find_one({"_id": chat_id})
            if doc and doc.get("admin_play"):
                self.admin_play.append(chat_id)
        return chat_id in self.admin_play

    async def set_play_mode(self, chat_id: int, remove: bool = False) -> None:
        if remove and chat_id in self.admin_play:
            self.admin_play.remove(chat_id)
        else:
            if chat_id not in self.admin_play:
                self.admin_play.append(chat_id)
        await self.chatsdb.update_one(
            {"_id": chat_id},
            {"$set": {"admin_play": not remove}},
            upsert=True,
        )

    async def get_autoplay(self, chat_id: int) -> bool:
        if chat_id not in self.autoplay_chats:
            doc = await self.chatsdb.find_one({"_id": chat_id})
            if doc and doc.get("autoplay"):
                self.autoplay_chats.append(chat_id)
        return chat_id in self.autoplay_chats

    async def set_autoplay(self, chat_id: int, state: bool) -> None:
        if state:
            if chat_id not in self.autoplay_chats:
                self.autoplay_chats.append(chat_id)
        else:
            if chat_id in self.autoplay_chats:
                self.autoplay_chats.remove(chat_id)
        await self.chatsdb.update_one(
            {"_id": chat_id},
            {"$set": {"autoplay": state}},
            upsert=True,
        )

    async def set_last_played(self, chat_id: int, title: str) -> None:
        await self.chatsdb.update_one(
            {"_id": chat_id},
            {"$set": {"last_played": title}},
            upsert=True,
        )

    async def get_last_played(self, chat_id: int) -> str | None:
        doc = await self.chatsdb.find_one({"_id": chat_id})
        return doc.get("last_played") if doc else None

    async def add_to_playlist(self, user_id: int, name: str, track: dict) -> int:
        doc = await self.playlistsdb.find_one({"_id": user_id}) or {}
        songs = doc.get("playlists", {}).get(name, [])
        songs.append(track)
        await self.playlistsdb.update_one(
            {"_id": user_id},
            {"$set": {f"playlists.{name}": songs}},
            upsert=True,
        )
        return len(songs)

    async def get_playlists(self, user_id: int) -> dict:
        doc = await self.playlistsdb.find_one({"_id": user_id})
        return doc.get("playlists", {}) if doc else {}

    async def get_playlist(self, user_id: int, name: str) -> list[dict]:
        playlists = await self.get_playlists(user_id)
        return playlists.get(name, [])

    async def remove_from_playlist(self, user_id: int, name: str, position: int) -> bool:
        songs = await self.get_playlist(user_id, name)
        if not songs or position < 1 or position > len(songs):
            return False
        songs.pop(position - 1)
        await self.playlistsdb.update_one(
            {"_id": user_id},
            {"$set": {f"playlists.{name}": songs}},
        )
        return True

    async def delete_playlist(self, user_id: int, name: str) -> bool:
        doc = await self.playlistsdb.find_one({"_id": user_id})
        if not doc or name not in doc.get("playlists", {}):
            return False
        await self.playlistsdb.update_one(
            {"_id": user_id},
            {"$unset": {f"playlists.{name}": ""}},
        )
        return True

    async def add_favorite(self, user_id: int, track: dict) -> None:
        doc = await self.playlistsdb.find_one({"_id": user_id}) or {}
        favs = [f for f in doc.get("favorites", []) if f.get("id") != track.get("id")]
        favs.insert(0, track)
        await self.playlistsdb.update_one(
            {"_id": user_id},
            {"$set": {"favorites": favs[:200]}},
            upsert=True,
        )
        await self.favoritesdb.update_one(
            {"_id": track["id"]},
            {
                "$set": {
                    "title": track.get("title", "Unknown"),
                    "url": track.get("url", ""),
                    "thumbnail": track.get("thumbnail"),
                    "duration": track.get("duration", ""),
                },
                "$inc": {"count": 1},
            },
            upsert=True,
        )

    async def get_favorites(self, user_id: int) -> list[dict]:
        doc = await self.playlistsdb.find_one({"_id": user_id})
        return doc.get("favorites", []) if doc else []

    async def get_global_favorites(self, limit: int = 15) -> list[dict]:
        cursor = self.favoritesdb.find().sort("count", -1).limit(limit)
        return [doc async for doc in cursor]

    async def track_play(self, track: dict) -> None:
        if not track.get("id"):
            return
        await self.mostplayeddb.update_one(
            {"_id": track["id"]},
            {
                "$set": {
                    "title": track.get("title", "Unknown"),
                    "url": track.get("url", ""),
                    "thumbnail": track.get("thumbnail"),
                    "duration": track.get("duration", ""),
                },
                "$inc": {"count": 1},
            },
            upsert=True,
        )

    async def get_most_played(self, limit: int = 15) -> list[dict]:
        cursor = self.mostplayeddb.find().sort("count", -1).limit(limit)
        return [doc async for doc in cursor]

    async def add_sudo(self, user_id: int) -> None:
        await self.cache.update_one(
            {"_id": "sudoers"}, {"$addToSet": {"user_ids": user_id}}, upsert=True
        )

    async def del_sudo(self, user_id: int) -> None:
        await self.cache.update_one(
            {"_id": "sudoers"}, {"$pull": {"user_ids": user_id}}
        )

    async def get_sudoers(self) -> list[int]:
        doc = await self.cache.find_one({"_id": "sudoers"})
        return doc.get("user_ids", []) if doc else []

    async def is_user(self, user_id: int) -> bool:
        return user_id in self.users

    async def add_user(self, user_id: int) -> None:
        if not await self.is_user(user_id):
            self.users.append(user_id)
            await self.usersdb.update_one({"_id": user_id}, {"$set": {"_id": user_id}}, upsert=True)

    async def rm_user(self, user_id: int) -> None:
        if await self.is_user(user_id):
            self.users.remove(user_id)
            await self.usersdb.delete_one({"_id": user_id})

    async def get_users(self) -> list:
        if not self.users:
            self.users.extend([user["_id"] async for user in self.usersdb.find()])
        return self.users

    async def load_cache(self) -> None:
        await self.get_chats()
        await self.get_users()
        await self.get_blacklisted(True)
        await self.get_logger()
        logger.info("Database cache loaded.")

    async def get_chatbot_state(self, chat_id: int) -> bool:
        doc = await self.chatbotdb.find_one({"_id": chat_id})
        return doc.get("enabled", False) if doc else False

    async def set_chatbot_state(self, chat_id: int, state: bool) -> None:
        await self.chatbotdb.update_one(
            {"_id": chat_id},
            {"$set": {"enabled": state}},
            upsert=True,
        )

    async def get_ai_key(self, chat_id: int) -> str | None:
        doc = await self.chatbotdb.find_one({"_id": chat_id})
        return doc.get("ai_key") if doc else None

    async def set_ai_key(self, chat_id: int, key: str | None) -> None:
        if key is None:
            await self.chatbotdb.update_one({"_id": chat_id}, {"$unset": {"ai_key": ""}})
        else:
            await self.chatbotdb.update_one({"_id": chat_id}, {"$set": {"ai_key": key}}, upsert=True)

    async def save_chat_message(self, chat_id: int, user_id: int, name: str, username: str, message: str) -> None:
        doc = {
            "chat_id": chat_id,
            "user_id": user_id,
            "name": name,
            "username": username,
            "message": message,
            "timestamp": time()
        }
        await self.chat_historydb.insert_one(doc)

    async def get_chat_history(self, chat_id: int, limit: int = 15) -> list[dict]:
        cursor = self.chat_historydb.find({"chat_id": chat_id}).sort("timestamp", -1).limit(limit)
        docs = [doc async for doc in cursor]
        docs.reverse()
        return docs

    # ──────────────────── Puguin (Azure AI Foundry) ──────────────────────

    async def get_puguin_state(self, chat_id: int) -> bool:
        doc = await self.puguindb.find_one({"_id": chat_id})
        return doc.get("enabled", False) if doc else False

    async def set_puguin_state(self, chat_id: int, state: bool) -> None:
        await self.puguindb.update_one(
            {"_id": chat_id},
            {"$set": {"enabled": state}},
            upsert=True,
        )

    async def save_puguin_message(
        self,
        chat_id: int,
        user_id: int,
        name: str,
        role: str,  # 'user' or 'assistant'
        message: str,
    ) -> None:
        from time import time as _time
        await self.puguin_historydb.insert_one({
            "chat_id": chat_id,
            "user_id": user_id,
            "name": name,
            "role": role,
            "message": message,
            "timestamp": _time(),
        })

    async def get_puguin_history(self, chat_id: int, limit: int = 20) -> list[dict]:
        cursor = (
            self.puguin_historydb
            .find({"chat_id": chat_id})
            .sort("timestamp", -1)
            .limit(limit)
        )
        docs = [doc async for doc in cursor]
        docs.reverse()
        return docs

    async def clear_puguin_history(self, chat_id: int) -> None:
        await self.puguin_historydb.delete_many({"chat_id": chat_id})

    async def save_puguin_fact(self, chat_id: int, fact: str) -> None:
        from time import time as _time
        await self.puguin_factsdb.insert_one({
            "chat_id": chat_id,
            "fact": fact,
            "timestamp": _time(),
        })

    async def get_puguin_facts(self, chat_id: int, limit: int = 50) -> list[str]:
        cursor = (
            self.puguin_factsdb
            .find({"chat_id": chat_id})
            .sort("timestamp", -1)
            .limit(limit)
        )
        docs = [doc async for doc in cursor]
        # Return newest facts first or reverse them, doesn't matter much for system prompt
        # We will just return strings
        return [d["fact"] for d in docs]
