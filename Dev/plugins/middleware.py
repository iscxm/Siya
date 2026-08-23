import asyncio
from pyrogram import filters, types
from pyrogram import StopPropagation
from Dev import app

MAINTENANCE_MODE = False

@app.on_message(filters.command(["maintenance"]) & filters.user(app.owner))
async def toggle_maintenance(_, m: types.Message):
    global MAINTENANCE_MODE
    MAINTENANCE_MODE = not MAINTENANCE_MODE
    state = "ON" if MAINTENANCE_MODE else "OFF"
    await m.reply_text(f"Maintenance mode is now {state}.")

BOT_COMMANDS = [
    "play", "vplay", "cplay", "cvplay", "playforce", "vplayforce", "cplayforce", "cvplayforce",
    "skip", "pause", "resume", "end", "stop", "queue", "player", "cqueue", "cplayer",
    "ping", "stats", "help", "settings", "playmode", "reboot", "restart", "logger", "logs",
    "eval", "exec",
    "playlist", "add", "remove", "delete", "view", "plplay", "recommend", "spotify", "maintenance", "cp", "copy"
]

@app.on_message(filters.command(BOT_COMMANDS) & filters.group, group=-1)
async def auto_delete_and_maintenance(_, m: types.Message):
    try:
        await m.delete()
    except Exception:
        pass
    
    if MAINTENANCE_MODE:
        if m.from_user and m.from_user.id not in app.sudoers and m.from_user.id != app.owner:
            msg = await m.reply_text("Bot is currently under maintenance.\n\nPlease try again later.\n\nAnd Ping Here @dotshv")
            
            async def delete_warning(c_id, m_id):
                await asyncio.sleep(5)
                try:
                    await app.delete_messages(c_id, m_id)
                except Exception:
                    pass
            asyncio.create_task(delete_warning(m.chat.id, msg.id))
            raise StopPropagation
