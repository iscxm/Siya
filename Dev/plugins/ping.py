import time
import psutil

from pyrogram import filters, types
from Dev import app, unnati, boot, config, lang
from Dev.helpers import buttons


@app.on_message(filters.command(["alive", "ping"]) & ~app.bl_users)
@lang.language()
async def _ping(_, m: types.Message):
    try:
        await m.delete()
    except Exception:
        pass
    start = time.time()
    sent = await m.reply_text(m.lang["pinging"])
    get_time = lambda s: (lambda r: (f"{r[-1]}, " if r[-1][:-4] != "0" else "") + ":".join(reversed(r[:-1])))([f"{v}{u}" for v, u in zip([s%60, (s//60)%60, (s//3600)%24, s//86400], ["s", "m", "h", "days"])])
    uptime = get_time(int(time.time() - boot))
    latency = round((time.time() - start) * 1000, 2)
    import asyncio
    try:
        cpu_freq = psutil.cpu_freq()
        cpu_speed = f"{cpu_freq.current / 1000:.2f} GHz" if cpu_freq else "N/A"
    except Exception:
        cpu_speed = "N/A"

    gpu_speed = "N/A"

    await sent.edit_media(
        media=types.InputMediaVideo(
            media="https://ar-hosting.pages.dev/1770752137400.mp4",
            caption=m.lang["ping_pong"].format(
                latency,
                uptime,
                psutil.cpu_percent(interval=0),
                cpu_speed,
                psutil.virtual_memory().percent,
                psutil.disk_usage("/").percent,
                await unnati.ping(),
                gpu_speed
            )
        ),
        reply_markup=buttons.ping_markup(m.lang["support"]),
    )

    async def _delete_ping():
        import asyncio
        await asyncio.sleep(60)
        try:
            await sent.delete()
        except Exception:
            pass
    import asyncio
    asyncio.create_task(_delete_ping())
