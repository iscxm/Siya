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
    try:
        await m.delete()
    except Exception:
        pass
    from Dev import config
    adminlist = await db.get_admins(m.chat.id)
    if m.from_user.id not in adminlist and m.from_user.id not in app.sudoers and m.from_user.id != config.OWNER_ID:
        msg = await m.reply_text("<emoji id='5420323339723881652'>❌</emoji> You must be an admin to reboot the bot in this chat.")
        async def _del_msg(msg):
            import asyncio
            await asyncio.sleep(10)
            try: await msg.delete()
            except: pass
        import asyncio
        asyncio.create_task(_del_msg(msg))
        return
        
    sent = await m.reply_text("<emoji id='5971801057540443125'>⚡</emoji> Rebooting voice chat state for this group...")
    
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
        
    await sent.edit_text(
        "<emoji id='5978776462386269988'>✨</emoji> Group voice chat state has been successfully rebooted.\n"
        "<emoji id='5321518192605019723'>🔴</emoji> You can now use <code>/play</code> again."
    )
    async def _del_sent(msg):
        import asyncio
        await asyncio.sleep(15)
        try: await msg.delete()
        except: pass
    import asyncio
    asyncio.create_task(_del_sent(sent))
