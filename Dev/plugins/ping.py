import time
import psutil

from pyrogram import filters, types
from Dev import app, unnati, boot, config, lang
from Dev.helpers import buttons


@app.on_message(filters.command(["alive", "ping"]) & ~app.bl_users)
@lang.language()
async def _ping(_, m: types.Message):
    start = time.time()
    sent = await m.reply_text(m.lang["pinging"])
    get_time = lambda s: (lambda r: (f"{r[-1]}, " if r[-1][:-4] != "0" else "") + ":".join(reversed(r[:-1])))([f"{v}{u}" for v, u in zip([s%60, (s//60)%60, (s//3600)%24, s//86400], ["s", "m", "h", "days"])])
    uptime = get_time(int(time.time() - boot))
    latency = round((time.time() - start) * 1000, 2)
    import subprocess
    try:
        cpu_freq = psutil.cpu_freq()
        cpu_speed = f"{cpu_freq.current / 1000:.2f} GHz" if cpu_freq else "N/A"
    except Exception:
        cpu_speed = "N/A"

    try:
        gpu_info = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,clocks.gr", "--format=csv,noheader"],
            stderr=subprocess.STDOUT, text=True
        ).strip().split("\n")[0]
        gpu_speed = gpu_info
    except Exception:
        try:
            lspci_out = subprocess.check_output(["lspci"], stderr=subprocess.STDOUT, text=True)
            gpu_speed = "N/A"
            for line in lspci_out.split('\n'):
                if "VGA compatible controller" in line or "3D controller" in line or "Display controller" in line:
                    gpu_speed = line.split(": ", 1)[1].split("(")[0].strip()
                    if "Corporation" in gpu_speed:
                        gpu_speed = gpu_speed.replace("Corporation ", "")
                    break
        except Exception:
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
