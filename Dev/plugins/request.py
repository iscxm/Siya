from pyrogram import filters, types
from Dev import app

@app.on_chat_join_request()
async def handle_join_request(_, req: types.ChatJoinRequest):
    try:
        bot = await app.get_me()
        
        await app.send_message(
            chat_id=req.from_user.id,
            text=(
                "<u><b>Click on the button below to verify yourself.</b></u>\n\n"
                "<i>Your request to join the group will be approved shortly.</i>"
            ),
            reply_markup=types.InlineKeyboardMarkup([
                [
                    types.InlineKeyboardButton(
                        "Verify", 
                        url=f"https://t.me/{bot.username}?start=verify"
                    )
                ]
            ])
        )
    except Exception:
        pass
