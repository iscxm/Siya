import os
import sys
import shutil
import asyncio

from pyrogram import filters, types

from Dev import app, db, lang, stop


@app.on_message(filters.command(["logs"]) & app.sudoers)
@lang.language()
async def _logs(_, m: types.Message):
    sent = await m.reply_text(m.lang["log_fetch"])
    if not os.path.exists("log.txt"):
        return await sent.edit_text(m.lang["log_not_found"])
    await sent.edit_media(
        media=types.InputMediaDocument(
            media="log.txt",
            caption=m.lang["log_sent"].format(app.name),
        )
    )


@app.on_message(filters.command(["logger"]) & app.sudoers)
@lang.language()
async def _logger(_, m: types.Message):
    if len(m.command) < 2:
        return await m.reply_text(m.lang["logger_usage"].format(m.command[0]))
    if m.command[1] not in ("on", "off"):
        return await m.reply_text(m.lang["logger_usage"].format(m.command[0]))

    if m.command[1] == "on":
        await db.set_logger(True)
        await m.reply_text(m.lang["logger_on"])
    else:
        await db.set_logger(False)
        await m.reply_text(m.lang["logger_off"])


@app.on_message(filters.command(["restart"]) & app.sudoers)
@lang.language()
async def _restart(_, m: types.Message):
    sent = await m.reply_text(m.lang["restarting"])

    for directory in ["cache", "downloads"]:
        shutil.rmtree(directory, ignore_errors=True)

    await sent.edit_text(m.lang["restarted"])
    asyncio.create_task(stop())
    await asyncio.sleep(2)

    try: os.remove("log.txt")
    except: pass

    os.execl(sys.executable, sys.executable, "-m", "Dev")

@app.on_message(filters.command(["reboot"]) & filters.group & ~app.bl_users)
async def _reboot_chat(_, m: types.Message):
    from Dev import config
    adminlist = await db.get_admins(m.chat.id)
    if m.from_user.id not in adminlist and m.from_user.id not in app.sudoers and m.from_user.id != config.OWNER_ID:
        return await m.reply_text("You must be an admin to reboot the bot in this chat.")
        
    sent = await m.reply_text("Rebooting voice chat state for this group...")
    
    from Dev import unnati, queue
    chat_id = m.chat.id
    
    try:
        await unnati.stop(chat_id)
    except Exception:
        pass
        
    try:
        queue.clear(chat_id)
    except Exception:
        pass
        
    await db.remove_call(chat_id)
    
    try:
        client = await db.get_client(chat_id)
        await client.leave_chat(chat_id)
    except Exception:
        pass
        
    await sent.edit_text("Group voice chat state has been successfully rebooted. You can now use /play again.")
