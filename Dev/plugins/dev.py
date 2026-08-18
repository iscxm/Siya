import random
import urllib.parse

from pyrogram import filters, types, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from Dev import app, config

# ── Custom emoji IDs (from en.json) ──────────────────────────────────────────
def _e(eid: str, fb: str) -> str:
    return f"<emoji id='{eid}'>{fb}</emoji>"

E_RED      = "5321518192605019723"   # live / danger
E_WARN     = "5273914604752216432"   # warning
E_LOCK     = "6001348061714978531"   # restricted
E_TERMINAL = "5971801057540443125"   # terminal / bolt
E_ERROR    = "5420323339723881652"   # error / denied
E_ALERT    = "5321004106494526877"   # unauthorized
E_SKULL    = "5337082389581547813"   # roast / skull


ROASTS = [
    f"{_e(E_SKULL, '💀')} Aye {{mention}}, tu kya samjha apne aap ko? Bot owner ka baap? Chomu kahin ka!",
    f"{_e(E_SKULL, '💀')} {{mention}} bhai, ye button tere liye nahi bana. Seedha ja, dimaag mat khaa!",
    f"{_e(E_SKULL, '💀')} {{mention}} Owner reserved button pe haath lagana? Teri himmat toh dekho! Chomu!",
    f"{_e(E_SKULL, '💀')} {{mention}} teri aukaat kya hai button dabaane ki? Ruk, pehle permission le. Bewakoof!",
    f"{_e(E_SKULL, '💀')} {{mention}} ne button dabaya, socha VPS milega... Sapne mein rehna bhai! Ja khel bahar!",
    f"{_e(E_SKULL, '💀')} {{mention}}, ye DANGER button hai tere jaisi chomunities ke liye nahi. Bhag idhar se!",
    f"{_e(E_SKULL, '💀')} {{mention}} Seriously? Tujhe lagta tha ye kaam karega? Chomu level: MAXIMUM!",
    f"{_e(E_SKULL, '💀')} {{mention}} bhai wapas ja, ye terminal tera baap chalata hai, tu nahi! Chal hat!",
    f"{_e(E_SKULL, '💀')} {{mention}} ko laga VPS mil gaya... Nahi mila. Never will. Chomu extraordinaire!",
    f"{_e(E_SKULL, '💀')} {{mention}}, terminal ke sapne dekh raha tha? Seedha neend mein chala ja, CHOMU!",
]


@app.on_message(filters.command("x"))
async def dev_command(_, m: types.Message):
    if m.from_user.id != config.OWNER_ID:
        return await m.reply_text(
            f"{_e(E_ERROR, '❌')} <b>Access Denied!</b>\n\n"
            f"<b>/x</b> is an Owner-only command.",
            parse_mode=enums.ParseMode.HTML,
        )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "DANGER",
            callback_data="dev_terminal_open",
        )]
    ])

    await m.reply_text(
        f"{_e(E_RED, '🔴')} <b>LIVE TERMINAL ACCESS</b>\n\n"
        f"{_e(E_WARN, '⚠️')} <b>WARNING:</b> This button opens a live shell session on the VPS.\n"
        f"{_e(E_LOCK, '🔒')} <i>Restricted to Bot Owner only.</i>\n\n"
        f"<code>Click the button below to launch terminal.</code>",
        reply_markup=keyboard,
        parse_mode=enums.ParseMode.HTML,
    )


@app.on_callback_query(filters.regex("^dev_terminal_open$"))
async def dev_terminal_callback(_, query: types.CallbackQuery):
    user = query.from_user

    if user.id == config.OWNER_ID:
        await query.answer("🔓 Opening Terminal...", show_alert=False)

        terminal_url = (
            f"https://raw.githack.com/your-repo/terminal.html"
            f"?token={urllib.parse.quote(config.BOT_TOKEN)}"
            f"&owner={config.OWNER_ID}"
        )
        terminal_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "🖥️ Open Live Terminal",
                web_app=types.WebAppInfo(url=terminal_url),
            )],
            [InlineKeyboardButton("Close", callback_data="dev_close")],
        ])

        try:
            await app.send_message(
                chat_id=user.id,
                text=(
                    f"{_e(E_RED, '🔴')} <b>VPS LIVE TERMINAL</b>\n\n"
                    f"{_e(E_TERMINAL, '⚡')} <b>Shell:</b> <code>bash</code>\n"
                    f"{_e(E_LOCK, '🔒')} <b>Access:</b> Owner Only\n\n"
                    f"<i>Click below to open the terminal session.</i>"
                ),
                reply_markup=terminal_keyboard,
                parse_mode=enums.ParseMode.HTML,
            )
            await query.answer("Terminal link sent to your DM!", show_alert=True)
        except Exception:
            await query.answer(
                "⚠️ Open DM with bot first, then try again!",
                show_alert=True,
            )
        return

    mention = user.mention
    roast = random.choice(ROASTS).format(mention=mention)

    await query.answer(
        "🚫 Access Denied! Tu chomu hai, owner nahi!",
        show_alert=True,
    )

    try:
        await query.message.reply_text(
            f"{_e(E_ALERT, '🚨')} <b>UNAUTHORIZED ACCESS ATTEMPT</b> {_e(E_ALERT, '🚨')}\n\n{roast}",
            parse_mode=enums.ParseMode.HTML,
        )
    except Exception:
        pass


@app.on_callback_query(filters.regex("^dev_close$"))
async def dev_close_callback(_, query: types.CallbackQuery):
    if query.from_user.id != config.OWNER_ID:
        await query.answer("🚫 Gand MRA BHOSDI", show_alert=True)
        return
    await query.answer()
    try:
        await query.message.delete()
    except Exception:
        pass
