import os
from pathlib import Path
from pyrogram import filters, types
from Dev import app, config

@app.on_message(filters.document & filters.user(config.OWNER_ID) & filters.private)
async def auto_updater(_, m: types.Message):
    if not m.document.file_name.endswith(".py"):
        return
        
    file_name = m.document.file_name
    msg = await m.reply_text(f"Scanning codebase for {file_name}...")
    
    # Search codebase for the file
    found_paths = []
    for root, _, files in os.walk("Dev"):
        if file_name in files:
            found_paths.append(os.path.join(root, file_name))
            
    if not found_paths:
        if "config.py" == file_name:
            found_paths.append("config.py")
        elif "__main__.py" == file_name:
            found_paths.append("__main__.py")
            
    if len(found_paths) == 1:
        path = found_paths[0]
        await m.download(file_name=path)
        await msg.edit_text(f"File updated successfully at: <code>{path}</code>\nPlease /reboot the bot if necessary.")
    elif len(found_paths) > 1:
        paths_str = "\n".join([f"<code>{p}</code>" for p in found_paths])
        await msg.edit_text(f"Multiple matches found for {file_name}:\n{paths_str}\n\nPlease specify the exact path using /update path/to/file.py")
    else:
        await msg.edit_text(f"No existing file named {file_name} found in the codebase. If you want to add it as a new file, reply to it with /update path/to/new_file.py")

@app.on_message(filters.command(["update"]) & filters.user(config.OWNER_ID))
async def manual_update(_, m: types.Message):
    if not m.reply_to_message or not m.reply_to_message.document:
        return await m.reply_text("Please reply to a Python file with the path you want to save it to.")
        
    if len(m.command) < 2:
        return await m.reply_text("Please provide the path to save the file. Example: /update Dev/plugins/new_plugin.py")
        
    path = m.text.split(maxsplit=1)[1]
    
    try:
        await m.reply_to_message.download(file_name=path)
        await m.reply_text(f"File saved successfully to <code>{path}</code>")
    except Exception as e:
        await m.reply_text(f"Failed to update file: {e}")
