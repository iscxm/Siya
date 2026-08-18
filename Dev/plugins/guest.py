"""
Guest Mode - triggers for users who @mention or reply to the bot in a group.
Uses Bot API 10.2 ephemeral messages. Falls back to auto-delete reply.
Custom emojis from en.json used throughout.
"""
import asyncio
import json
import aiohttp
from pyrogram import filters, types, enums
from Dev import app, config


async def send_ephemeral(chat_id: int, user_id: int, text: str, reply_markup: dict = None) -> bool:
    """Send Bot API 10.2 ephemeral message (visible only to that user)."""
    params = {
        "chat_id": chat_id,
        "user_id": user_id,
        "text": text,
        "parse_mode": "HTML",
    }
    if reply_markup:
        params["reply_markup"] = json.dumps(reply_markup)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendEphemeralMessage",
                json=params,
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                data = await resp.json()
                return bool(data.get("ok"))
    except Exception:
        return False


async def _send_fallback(chat_id: int, text: str, reply_markup, reply_to_id: int) -> None:
    """Fallback: send normal reply + auto-delete after 30s."""
    try:
        msg = await app.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=enums.ParseMode.HTML,
            reply_markup=reply_markup,
            reply_to_message_id=reply_to_id,
        )
        await asyncio.sleep(30)
        try:
            await msg.delete()
        except Exception:
            pass
    except Exception:
        pass


def _guest_text(first_name: str, bot_name: str, bot_username: str) -> str:
    # Custom emoji IDs from en.json
    MUSIC   = "5337147651609610232"   # music note
    SPARKLE = "5978776462386269988"   # sparkle/star
    LOCK    = "5204843207000751586"   # lock (used in bot)
    WAVE    = "5199785165735367039"   # wave
    PLUS    = "5895739888262713455"   # plus/add
    CHAT    = "6289589175284928919"   # chat bubble

    return (
        f"<emoji id='{WAVE}'>\U0001f44b</emoji> <b>Hey {first_name}!</b>\n\n"
        f"<emoji id='{MUSIC}'>\U0001f3b5</emoji> I'm <b><i>{bot_name}</i></b> — your group's music companion!\n\n"
        f"<emoji id='{SPARKLE}'>\u2728</emoji> <b>What I can do:</b>\n"
        f"  <emoji id='{MUSIC}'>\U0001f3b5</emoji> Play music &amp; videos in voice chats\n"
        f"  \U0001f50d YouTube, Spotify &amp; playlists\n"
        f"  \U0001f3bc Queue, autoplay &amp; full controls\n\n"
        f"<emoji id='{PLUS}'>\u2795</emoji> <b>Add me to your group</b> or "
        f"<emoji id='{CHAT}'>\U0001f4ac</emoji> <b>DM me to get started!</b>\n\n"
        f"<blockquote><emoji id='{LOCK}'>\U0001f512</emoji> <i>Only you can see this message.</i></blockquote>"
    )


def _guest_markup_dict(bot_username: str) -> dict:
    """Keyboard for ephemeral HTTP API call."""
    return {
        "inline_keyboard": [
            [{"text": "\u2795 Add Me to Your Group", "url": f"https://t.me/{bot_username}?startgroup=true"}],
            [
                {"text": "\U0001f4ac Start in DM",   "url": f"https://t.me/{bot_username}?start=hello"},
                {"text": "\U0001f3b5 Play Music",     "url": f"https://t.me/{bot_username}?startgroup=true"},
            ],
        ]
    }


def _guest_markup_pyro(bot_username: str) -> types.InlineKeyboardMarkup:
    """Keyboard for pyrogram fallback."""
    return types.InlineKeyboardMarkup([
        [types.InlineKeyboardButton(
            text="\u2795 Add Me to Your Group",
            url=f"https://t.me/{bot_username}?startgroup=true",
        )],
        [
            types.InlineKeyboardButton(text="\U0001f4ac Start in DM",  url=f"https://t.me/{bot_username}?start=hello"),
            types.InlineKeyboardButton(text="\U0001f3b5 Play Music",   url=f"https://t.me/{bot_username}?startgroup=true"),
        ],
    ])


# ─── Watcher ──────────────────────────────────────────────────────────────────
# group=15 ensures this runs last so it doesn't interfere with command handlers
# ~filters.bot: ignore other bots
# We intentionally do NOT filter by bl_users here so truly new users can see it
@app.on_message(filters.group & ~filters.bot, group=15)
async def guest_mode_watcher(_, m: types.Message) -> None:
    """
    Fires when:
      1. Any user @mentions the bot in a group, OR
      2. Any user replies to a bot message in a group
    Works regardless of whether the user has ever started the bot.
    """
    if not m.from_user:
        return

    bot_id       = app.id
    bot_username = (app.username or "").lower()
    bot_name     = app.name or "Siya"

    # ── Check: reply to bot ────────────────────────────────────────────────────
    is_reply = (
        m.reply_to_message
        and m.reply_to_message.from_user
        and m.reply_to_message.from_user.id == bot_id
    )

    # ── Check: @mention of bot ─────────────────────────────────────────────────
    is_mention = False
    if not is_reply and m.entities:
        for ent in m.entities:
            if ent.type == enums.MessageEntityType.MENTION and m.text:
                chunk = m.text[ent.offset: ent.offset + ent.length].lstrip("@").lower()
                if chunk == bot_username:
                    is_mention = True
                    break
            elif ent.type == enums.MessageEntityType.TEXT_MENTION:
                if ent.user and ent.user.id == bot_id:
                    is_mention = True
                    break
    # Also check caption entities (for photo/video messages)
    if not is_reply and not is_mention and m.caption_entities:
        for ent in m.caption_entities:
            if ent.type == enums.MessageEntityType.MENTION and m.caption:
                chunk = m.caption[ent.offset: ent.offset + ent.length].lstrip("@").lower()
                if chunk == bot_username:
                    is_mention = True
                    break

    if not (is_reply or is_mention):
        return

    user       = m.from_user
    username   = app.username or ""
    text       = _guest_text(user.first_name, bot_name, username)
    m_dict     = _guest_markup_dict(username)
    m_pyro     = _guest_markup_pyro(username)

    # Try ephemeral first (Bot API 10.2) — visible only to that user
    ok = await send_ephemeral(m.chat.id, user.id, text, m_dict)
    if not ok:
        # Fallback: normal reply, auto-deletes after 30s
        asyncio.create_task(_send_fallback(m.chat.id, text, m_pyro, m.id))
