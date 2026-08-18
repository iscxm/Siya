import random
from pyrogram import filters, types, enums
from Dev import app, db, lang

try:
    from google import genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

@app.on_message(filters.command(["chatbot"]) & filters.group & ~app.bl_users)
@lang.language()
async def chatbot_cmd(_, m: types.Message):
    if len(m.command) < 2 or m.command[1].lower() not in ["on", "off"]:
        return await m.reply_text("Usage: <code>/chatbot [on|off]</code>\nTurns the chatbot on or off in this group.")
    
    state = m.command[1].lower() == "on"
    await db.set_chatbot_state(m.chat.id, state)
    
    await m.reply_text(f"Chatbot has been turned **{'ON' if state else 'OFF'}** for this group.")


@app.on_message(filters.command(["setaikey"]) & filters.group & ~app.bl_users)
@lang.language()
async def setaikey_cmd(_, m: types.Message):
    if len(m.command) < 2:
        return await m.reply_text(
            "Usage: <code>/setaikey [your_gemini_api_key]</code> or <code>/setaikey none</code> to remove.\n"
            "Setting an API key upgrades the chatbot to use AI for realistic human-like conversations!"
        )
    
    key = m.command[1]
    if key.lower() == "none":
        await db.set_ai_key(m.chat.id, None)
        return await m.reply_text("AI API Key has been removed. Chatbot will use basic fallback logic now.")
    
    await db.set_ai_key(m.chat.id, key)
    
    # Delete message for privacy
    try:
        await m.delete()
    except Exception:
        pass
        
    await m.reply_text("AI API Key has been saved securely for this group! I am now a smart AI Chatbot.")


@app.on_message(
    filters.text & filters.group & ~filters.bot & ~filters.command(["chatbot", "setaikey"]),
    group=10
)
async def chatbot_watcher(_, m: types.Message):
    chat_id = m.chat.id
    
    if not await db.get_chatbot_state(chat_id):
        return
        
    user = m.from_user
    if not user:
        return
        
    name = user.first_name + (f" {user.last_name}" if user.last_name else "")
    username = user.username or ""
    
    # Save message data
    await db.save_chat_message(chat_id, user.id, name, username, m.text)
    
    # Decide whether to reply (10% chance, or if replied/mentioned)
    bot_member = await app.get_me()
    bot_username = bot_member.username or ""
    bot_name = bot_member.first_name or ""
    
    is_reply = bool(m.reply_to_message and m.reply_to_message.from_user and m.reply_to_message.from_user.id == bot_member.id)
    is_mentioned = (bot_username.lower() in m.text.lower()) or (bot_name.lower() in m.text.lower())
    
    if is_reply or is_mentioned or random.random() < 0.10:
        await app.send_chat_action(m.chat.id, enums.ChatAction.TYPING)
        
        ai_key = await db.get_ai_key(chat_id)
        history = await db.get_chat_history(chat_id, limit=15)
        
        if ai_key and HAS_GENAI:
            try:
                client = genai.Client(api_key=ai_key)
                context = (
                    f"You are a friendly, human-like member of a Telegram group chat. Your name is {bot_name}. "
                    "People are talking. Read the recent messages and reply naturally. Do not sound like an AI assistant. "
                    "Be casual, use short sentences, use slang, maybe emojis. Respond directly to the latest message.\n\n"
                    "Recent messages:\n"
                )
                for h in history:
                    context += f"{h['name']} (@{h['username']}): {h['message']}\n"
                
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=context,
                )
                
                if response.text:
                    await m.reply_text(response.text)
                return
            except Exception as e:
                pass # Fallback if AI fails
                
        # Basic logic fallback
        if len(history) > 5:
            # Pick a random past message to sound like a weird human
            random_msg = random.choice(history[:-1])
            reply = random_msg['message']
        else:
            responses = ["hmm", "sahi baat hai", "lol", "accha?", "kya bol raha hai", "waah", "nice", "ok", "badhiya"]
            reply = random.choice(responses)
            
        await m.reply_text(reply)
