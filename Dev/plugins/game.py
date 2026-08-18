import io
import random
from pyrogram import filters, types
import asyncio
from PIL import Image, ImageDraw, ImageFont
from Dev import app, db, lang

# Global states for games (in-memory)
rps_challenges = {}
active_scrambles = {}
active_math = {}

WORDS = ["PYTHON", "TELEGRAM", "BOT", "MUSIC", "GAMING", "CHALLENGE", "WINNER", "PYROGRAM", "DEVELOPER"]

def create_slot_machine_image(slots):
    width = 400
    height = 200
    img = Image.new('RGB', (width, height), color=(30, 30, 40))
    draw = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.truetype("arial.ttf", 40)
        title_font = ImageFont.truetype("arial.ttf", 20)
    except IOError:
        font = ImageFont.load_default()
        title_font = ImageFont.load_default()
    
    box_width = 80
    box_height = 80
    start_x = 50
    start_y = 60
    gap = 20
    
    colors = [(255, 100, 100), (100, 255, 100), (100, 100, 255), (255, 255, 100), (255, 100, 255)]
    
    for i, symbol in enumerate(slots):
        x0 = start_x + i * (box_width + gap)
        y0 = start_y
        x1 = x0 + box_width
        y1 = y0 + box_height
        
        # Draw box
        draw.rectangle([x0, y0, x1, y1], fill=(50, 50, 60), outline=(200, 200, 200), width=3)
        
        # Draw symbol
        try:
            bbox = draw.textbbox((0,0), symbol, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
        except AttributeError:
            # Fallback for older PIL
            tw, th = draw.textsize(symbol, font=font)
        
        draw.text((x0 + (box_width-tw)/2, y0 + (box_height-th)/2 - 5), symbol, font=font, fill=random.choice(colors))

    # Add game title
    try:
        bbox = draw.textbbox((0,0), "VIRTUAL SLOTS", font=title_font)
        tw = bbox[2] - bbox[0]
    except AttributeError:
        tw, th = draw.textsize("VIRTUAL SLOTS", font=title_font)
        
    draw.text(((width - tw) / 2, 20), "VIRTUAL SLOTS", fill=(255, 215, 0), font=title_font)
    
    bio = io.BytesIO()
    bio.name = 'slots.png'
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio


@app.on_message(filters.command(["slotmachine", "slots"]) & filters.group & ~app.bl_users)
@lang.language()
async def slotmachine_cmd(_, m: types.Message):
    symbols = ["🍒", "🍋", "🔔", "⭐", "💎", "7️⃣"]
    
    # Spin the slots
    result = [random.choice(symbols) for _ in range(3)]
    
    msg = await m.reply_text("Spinning the slots... 🎰")
    
    # Generate image
    img_io = create_slot_machine_image(result)
    
    # Check win
    if result[0] == result[1] == result[2]:
        text = f"🎉 **JACKPOT!** You rolled {result[0]} {result[1]} {result[2]}!"
    elif result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:
        text = f"✨ **Mini Win!** You got a pair of {result[1]}!"
    else:
        text = f"😢 Better luck next time!"
        
    await m.reply_photo(photo=img_io, caption=text)
    await msg.delete()

# --- 1v1 ROCK PAPER SCISSORS ---

@app.on_message(filters.command(["rps"]) & filters.group & ~app.bl_users)
async def rps_cmd(_, m: types.Message):
    if not m.reply_to_message:
        return await m.reply_text("Reply to a user to challenge them to Rock Paper Scissors!")
        
    p1 = m.from_user
    p2 = m.reply_to_message.from_user
    
    if not p2 or p1.id == p2.id or p2.is_bot:
        return await m.reply_text("You can't challenge yourself or a bot!")
        
    keyboard = types.InlineKeyboardMarkup([
        [
            types.InlineKeyboardButton("Rock 🪨", callback_data=f"rps_r_{p1.id}_{p2.id}"),
            types.InlineKeyboardButton("Paper 📄", callback_data=f"rps_p_{p1.id}_{p2.id}"),
            types.InlineKeyboardButton("Scissors ✂️", callback_data=f"rps_s_{p1.id}_{p2.id}")
        ]
    ])
    
    msg = await m.reply_text(
        f"🎮 **Rock Paper Scissors!**\n\n{p1.mention} challenged {p2.mention}!\n\nBoth players, make your choice below (Choices are hidden until both pick):",
        reply_markup=keyboard
    )
    
    rps_challenges[msg.id] = {
        "p1_id": p1.id,
        "p2_id": p2.id,
        "p1_choice": None,
        "p2_choice": None,
        "p1_name": p1.first_name,
        "p2_name": p2.first_name
    }


@app.on_callback_query(filters.regex(r"^rps_(r|p|s)_(\d+)_(\d+)$"))
async def rps_cb(_, q: types.CallbackQuery):
    choice = q.matches[0].group(1)
    p1_id = int(q.matches[0].group(2))
    p2_id = int(q.matches[0].group(3))
    
    game = rps_challenges.get(q.message.id)
    if not game:
        return await q.answer("This game has ended.", show_alert=True)
        
    user_id = q.from_user.id
    if user_id not in [p1_id, p2_id]:
        return await q.answer("This is not your game!", show_alert=True)
        
    is_p1 = (user_id == p1_id)
    
    if (is_p1 and game["p1_choice"]) or (not is_p1 and game["p2_choice"]):
        return await q.answer("You already made your choice!", show_alert=True)
        
    if is_p1:
        game["p1_choice"] = choice
    else:
        game["p2_choice"] = choice
        
    await q.answer("Choice registered!")
    
    # Check if both have played
    if game["p1_choice"] and game["p2_choice"]:
        c1 = game["p1_choice"]
        c2 = game["p2_choice"]
        
        emoji_map = {"r": "🪨", "p": "📄", "s": "✂️"}
        
        text = f"🎮 **Game Over!**\n\n"
        text += f"{game['p1_name']}: {emoji_map[c1]}\n"
        text += f"{game['p2_name']}: {emoji_map[c2]}\n\n"
        
        if c1 == c2:
            text += "**Result:** It's a TIE! 🤝"
        elif (c1 == "r" and c2 == "s") or (c1 == "p" and c2 == "r") or (c1 == "s" and c2 == "p"):
            text += f"**Result:** {game['p1_name']} WINS! 🎉"
        else:
            text += f"**Result:** {game['p2_name']} WINS! 🎉"
            
        await q.message.edit_text(text)
        del rps_challenges[q.message.id]


# --- SOLO CHALLENGES (Tasks) ---

@app.on_message(filters.command(["scramble"]) & filters.group & ~app.bl_users)
async def scramble_cmd(_, m: types.Message):
    if m.chat.id in active_scrambles:
        return await m.reply_text("A word scramble challenge is already running in this group!")
        
    word = random.choice(WORDS)
    scrambled = "".join(random.sample(word, len(word)))
    
    active_scrambles[m.chat.id] = word
    
    await m.reply_text(
        f"🔡 **Word Scramble Challenge!**\n\n"
        f"Unscramble this word: `{scrambled}`\n\n"
        f"First person to type the correct word in chat wins!"
    )
    
    # Auto-expire after 30 seconds
    await asyncio.sleep(30)
    if active_scrambles.get(m.chat.id) == word:
        del active_scrambles[m.chat.id]
        await m.reply_text(f"⏳ Time's up! The correct word was **{word}**.")


@app.on_message(filters.command(["math"]) & filters.group & ~app.bl_users)
async def math_cmd(_, m: types.Message):
    if m.chat.id in active_math:
        return await m.reply_text("A math challenge is already running in this group!")
        
    ops = ["+", "-", "*"]
    op = random.choice(ops)
    
    if op == "*":
        a = random.randint(2, 12)
        b = random.randint(2, 12)
    else:
        a = random.randint(10, 100)
        b = random.randint(1, 50)
        
    if op == "-":
        if b > a:
            a, b = b, a # Ensure positive result
            
    question = f"{a} {op} {b}"
    answer = eval(question)
    
    active_math[m.chat.id] = str(answer)
    
    await m.reply_text(
        f"🧮 **Math Challenge!**\n\n"
        f"Solve this: `{question}`\n\n"
        f"First person to type the correct answer wins!"
    )
    
    # Auto-expire after 30 seconds
    await asyncio.sleep(30)
    if active_math.get(m.chat.id) == str(answer):
        del active_math[m.chat.id]
        await m.reply_text(f"⏳ Time's up! The correct answer was **{answer}**.")


# Watcher for answers
@app.on_message(filters.text & filters.group & ~filters.bot, group=11)
async def task_answer_watcher(_, m: types.Message):
    chat_id = m.chat.id
    text = m.text.upper().strip()
    
    if chat_id in active_scrambles:
        if text == active_scrambles[chat_id]:
            word = active_scrambles.pop(chat_id)
            await m.reply_text(f"🎉 **{m.from_user.first_name}** wins! The word was **{word}**.")
            
    if chat_id in active_math:
        if m.text.strip() == active_math[chat_id]:
            ans = active_math.pop(chat_id)
            await m.reply_text(f"🎉 **{m.from_user.first_name}** wins! The answer was **{ans}**.")

