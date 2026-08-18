import os
import json
from pyrogram import filters, types
from Dev import app, db, config

@app.on_message(filters.command(["db", "getdb"]) & filters.group)
async def get_db_cmd(_, m: types.Message):
    if m.from_user.id != config.OWNER_ID:
        return await m.reply_text("<b>⚠️ SECURITY ALERT</b>\n\nUnauthorized access attempt detected. Your IP and User ID have been logged and reported for suspicious activity.")
    
    msg = await m.reply_text("Generating database backup...")
    await db.backup_to_json()
    
    if os.path.exists("database.json"):
        await m.reply_document("database.json", caption="Here is the latest database backup.")
        os.remove("database.json")
    else:
        await msg.edit_text("Failed to generate database backup.")

@app.on_message(filters.command(["setdb"]) & filters.group)
async def set_db_cmd(_, m: types.Message):
    if m.from_user.id != config.OWNER_ID:
        return await m.reply_text("<b>⚠️ SECURITY ALERT</b>\n\nUnauthorized access attempt detected. Your IP and User ID have been logged and reported for suspicious activity.")
    
    if not m.reply_to_message or not m.reply_to_message.document or not m.reply_to_message.document.file_name.endswith(".json"):
        return await m.reply_text("Please reply to a valid database.json file.")
    
    msg = await m.reply_text("Restoring database from JSON... Please wait.")
    
    try:
        file_path = await m.reply_to_message.download()
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        # Restore data using upsert to prevent duplicates
        if "chats" in data:
            for chat in data["chats"]:
                await db.chatsdb.update_one({"_id": chat["_id"]}, {"$set": chat}, upsert=True)
                
        if "users" in data:
            for user in data["users"]:
                await db.usersdb.update_one({"_id": user["_id"]}, {"$set": user}, upsert=True)
                
        if "playlists" in data:
            for pl in data["playlists"]:
                await db.playlistsdb.update_one({"_id": pl["_id"]}, {"$set": pl}, upsert=True)
                
        if "favorites" in data:
            for fav in data["favorites"]:
                await db.favoritesdb.update_one({"_id": fav["_id"]}, {"$set": fav}, upsert=True)
                
        if "mostplayed" in data:
            for mp in data["mostplayed"]:
                await db.mostplayeddb.update_one({"_id": mp["_id"]}, {"$set": mp}, upsert=True)
                
        os.remove(file_path)
        await msg.edit_text("Database successfully restored from JSON backup.")
    except Exception as e:
        await msg.edit_text(f"Failed to restore database: {e}")
