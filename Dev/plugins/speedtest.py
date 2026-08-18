"""
/speedtest - Server internet speed test with a Pillow-generated image card.
Network name is shown as 'Toxic Pvt Network' | Location: Rajasthan, India
"""

import asyncio
import io
import time

from pyrogram import filters, types, enums
from Dev import app, config

# ── Custom emoji IDs (sourced from en.json) ──────────────────────────────────
def _e(eid: str, fb: str) -> str:
    return f"<emoji id='{eid}'>{fb}</emoji>"

E_BOLT     = "5971801057540443125"   # ⚡ processing / bolt
E_DL       = "5337147651609610232"   # 📥 download / arrow
E_UL       = "5334556918746729184"   # 📤 upload / arrow
E_SEARCH   = "6181345004309451395"   # 🔍 connecting / search
E_CHECK    = "5021905410089550576"   # ✅ success
E_ERROR    = "5420323339723881652"   # ❌ error
E_WARN     = "5273914604752216432"   # ⚠️ warning
E_NETWORK  = "5337291468589516017"   # 🌐 network / title
E_LOCATION = "6134340169257452868"   # 📍 location
E_PING     = "5121007227779416740"   # 🔗 latency
E_LOCK     = "6001348061714978531"   # 🔒 access denied

# ─────────────────────────── Pillow draw ────────────────────────────────────

def _draw_speedtest_image(
    download_mbps: float,
    upload_mbps: float,
    ping_ms: float,
    jitter_ms: float,
) -> io.BytesIO:
    from PIL import Image, ImageDraw, ImageFont
    import random

    W, H = 900, 520

    # ── Background gradient (dark navy → deep purple) ──
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)

    for y in range(H):
        r = int(10  + (25  - 10)  * y / H)
        g = int(10  + (8   - 10)  * y / H)
        b = int(40  + (60  - 40)  * y / H)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # ── Glowing blobs ──
    def blob(cx, cy, radius, col):
        for step in range(12, 0, -1):
            alpha = int(28 * step / 12)
            r2 = int(radius * step / 12)
            overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            od = ImageDraw.Draw(overlay)
            od.ellipse(
                [cx - r2, cy - r2, cx + r2, cy + r2],
                fill=(*col, alpha),
            )
            img.paste(
                Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
            )

    blob(130, 100, 160, (80, 0, 200))
    blob(750, 400, 180, (0, 120, 255))
    blob(450, 260, 120, (180, 0, 120))

    draw = ImageDraw.Draw(img)

    # ── Glassmorphism card ──
    card_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    card_d = ImageDraw.Draw(card_overlay)
    card_d.rounded_rectangle(
        [40, 30, 860, 490],
        radius=28,
        fill=(255, 255, 255, 18),
        outline=(255, 255, 255, 50),
        width=2,
    )
    img = Image.alpha_composite(img.convert("RGBA"), card_overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    # ── Font helper (falls back to default) ──
    def font(size):
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
        except Exception:
            try:
                return ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", size)
            except Exception:
                return ImageFont.load_default()

    def font_reg(size):
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
        except Exception:
            try:
                return ImageFont.truetype("C:/Windows/Fonts/arial.ttf", size)
            except Exception:
                return ImageFont.load_default()

    # ── Colour palette ──
    ACCENT  = (120, 80, 255)
    CYAN    = (0, 220, 255)
    LIME    = (80, 255, 160)
    ORANGE  = (255, 160, 40)
    WHITE   = (255, 255, 255)
    GRAY    = (160, 160, 200)

    # ── Header logo circle ──
    draw.ellipse([55, 45, 115, 105], fill=(80, 40, 180), outline=(180, 140, 255), width=2)
    draw.text((85, 75), "Z", font=font(40), fill=(255, 220, 80), anchor="mm")

    # Title
    draw.text((130, 47), "SPEED TEST", font=font(36), fill=WHITE)
    draw.text((130, 88), "Network Performance Report", font=font_reg(16), fill=GRAY)

    # Divider
    draw.rectangle([55, 118, 845, 121], fill=(100, 60, 220))

    # ── Network Info Row ──
    draw.text((60, 135), "Network :", font=font(17), fill=GRAY)
    draw.text((175, 135), "Toxic Pvt Network", font=font(17), fill=(120, 200, 255))

    draw.text((470, 135), "Location :", font=font(17), fill=GRAY)
    draw.text((590, 135), "Rajasthan, India", font=font(17), fill=(120, 200, 255))

    # ── Speed arc meters ──
    def draw_arc_meter(cx, cy, r, value, max_val, color_fill, label, unit, sub):
        angle_start = 210
        span        = 300

        # Background arc
        for w in range(8, 0, -1):
            draw.arc(
                [cx - r, cy - r, cx + r, cy + r],
                start=angle_start,
                end=angle_start + span,
                fill=(50, 50, 90),
                width=w,
            )

        # Value arc
        pct   = min(value / max_val, 1.0)
        v_end = angle_start + int(span * pct)
        if v_end > angle_start:
            for w in range(12, 0, -1):
                draw.arc(
                    [cx - r + w // 2, cy - r + w // 2, cx + r - w // 2, cy + r - w // 2],
                    start=angle_start,
                    end=v_end,
                    fill=color_fill,
                    width=max(1, 12 - w),
                )

        # Center value
        draw.text((cx, cy - 12), f"{value:.1f}", font=font(32), fill=WHITE, anchor="mm")
        draw.text((cx, cy + 22), unit, font=font_reg(14), fill=GRAY, anchor="mm")
        draw.text((cx, cy + 50), label, font=font(16), fill=color_fill, anchor="mm")
        draw.text((cx, cy + 70), sub, font=font_reg(12), fill=GRAY, anchor="mm")

    draw_arc_meter(
        cx=210, cy=310, r=110,
        value=download_mbps, max_val=200,
        color_fill=CYAN,
        label="DOWNLOAD", unit="Mbps",
        sub="Incoming",
    )
    draw_arc_meter(
        cx=480, cy=310, r=110,
        value=upload_mbps, max_val=200,
        color_fill=LIME,
        label="UPLOAD", unit="Mbps",
        sub="Outgoing",
    )

    # ── Right panel: Ping / Jitter ──
    panel_x1, panel_y1, panel_x2, panel_y2 = 640, 165, 850, 415
    p_ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pd = ImageDraw.Draw(p_ov)
    pd.rounded_rectangle(
        [panel_x1, panel_y1, panel_x2, panel_y2],
        radius=18,
        fill=(20, 20, 50, 140),
        outline=(120, 80, 255, 120),
        width=2,
    )
    img = Image.alpha_composite(img.convert("RGBA"), p_ov).convert("RGB")
    draw = ImageDraw.Draw(img)

    mid_x = (panel_x1 + panel_x2) // 2

    draw.text((mid_x, panel_y1 + 22), "LATENCY", font=font(15), fill=ACCENT, anchor="mm")
    draw.text((mid_x, panel_y1 + 65), f"{ping_ms:.0f}", font=font(44), fill=ORANGE, anchor="mm")
    draw.text((mid_x, panel_y1 + 110), "ms  Ping", font=font_reg(15), fill=GRAY, anchor="mm")

    draw.rectangle([panel_x1 + 20, panel_y1 + 135, panel_x2 - 20, panel_y1 + 137], fill=(80, 80, 120))

    draw.text((mid_x, panel_y1 + 158), f"{jitter_ms:.1f}", font=font(38), fill=(255, 120, 80), anchor="mm")
    draw.text((mid_x, panel_y1 + 198), "ms  Jitter", font=font_reg(15), fill=GRAY, anchor="mm")

    # Quality badge
    if ping_ms < 30 and download_mbps > 50:
        quality, qcol = "EXCELLENT", (80, 255, 160)
    elif ping_ms < 80 and download_mbps > 10:
        quality, qcol = "GOOD", (120, 200, 255)
    else:
        quality, qcol = "FAIR", (255, 160, 40)

    q_ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    qd = ImageDraw.Draw(q_ov)
    qd.rounded_rectangle(
        [panel_x1 + 14, panel_y1 + 215, panel_x2 - 14, panel_y1 + 250],
        radius=10,
        fill=(*qcol, 40),
        outline=(*qcol, 120),
        width=1,
    )
    img = Image.alpha_composite(img.convert("RGBA"), q_ov).convert("RGB")
    draw = ImageDraw.Draw(img)
    draw.text((mid_x, panel_y1 + 233), quality, font=font(13), fill=qcol, anchor="mm")

    # ── Bottom bar ──
    ts = time.strftime("%d %b %Y  |  %H:%M:%S IST")
    draw.text((W // 2, 462), ts, font=font_reg(14), fill=GRAY, anchor="mm")
    draw.text((W // 2, 482), "Powered by Toxic Pvt Network  |  Rajasthan, India", font=font_reg(11), fill=(80, 80, 120), anchor="mm")

    # ── Sparkle dots ──
    rng = random.Random(42)
    for _ in range(18):
        sx = rng.randint(55, 845)
        sy = rng.randint(35, 490)
        sr = rng.randint(1, 3)
        sa = rng.randint(60, 180)
        sp_ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sp_d = ImageDraw.Draw(sp_ov)
        sp_d.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=(255, 255, 255, sa))
        img = Image.alpha_composite(img.convert("RGBA"), sp_ov).convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


# ─────────────────────────── Speed test runner ──────────────────────────────

async def _run_speedtest():
    """
    HTTP-based speed test using Cloudflare's speed.cloudflare.com.
    Time-bound (2s per test) to ensure fast execution (5-6s total) and accuracy on Gigabit links.
    """
    import aiohttp
    import os

    CF_BASE   = "https://speed.cloudflare.com"
    # Download: Request a huge 200 MB file, but we will cancel it after 2 seconds
    DL_URL    = f"{CF_BASE}/__down?bytes=200000000"
    UL_URL    = f"{CF_BASE}/__up"
    PING_URL  = f"{CF_BASE}/__down?bytes=1"

    async with aiohttp.ClientSession() as session:

        # ── Ping (3 samples) ─────────────────────────────────────────────────
        pings = []
        for _ in range(3):
            t0 = time.monotonic()
            try:
                async with session.get(PING_URL, timeout=aiohttp.ClientTimeout(total=2)) as r:
                    await r.read()
                pings.append((time.monotonic() - t0) * 1000)
            except Exception:
                pass
        ping_ms   = sum(pings) / len(pings) if pings else 0.0
        jitter_ms = max(pings) - min(pings) if pings else 0.0

        # ── Download (max 2 seconds, 4 parallel streams) ─────────────────────
        dl_start = time.monotonic()
        dl_bytes = 0
        
        async def dl_worker():
            nonlocal dl_bytes
            try:
                # Cloudflare allows max ~50MB per request, so we use 50000000
                dl_req_url = f"{CF_BASE}/__down?bytes=50000000"
                async with session.get(dl_req_url, timeout=aiohttp.ClientTimeout(total=4)) as r:
                    async for chunk in r.content.iter_chunked(256 * 1024):
                        dl_bytes += len(chunk)
                        if time.monotonic() - dl_start >= 2.0:
                            break
            except Exception:
                pass

        await asyncio.gather(dl_worker(), dl_worker(), dl_worker(), dl_worker())
        
        dl_elapsed    = time.monotonic() - dl_start
        if dl_elapsed == 0: dl_elapsed = 0.001
        download_mbps = (dl_bytes * 8) / dl_elapsed / 1_000_000

        # ── Upload (max 2 seconds, 2 parallel streams) ───────────────────────
        ul_bytes = 0
        ul_start = time.monotonic()
        
        async def upload_generator():
            nonlocal ul_bytes
            chunk = os.urandom(256 * 1024) # 256KB chunks
            while time.monotonic() - ul_start < 2.0:
                yield chunk
                ul_bytes += len(chunk)

        async def ul_worker():
            try:
                async with session.post(
                    UL_URL,
                    data=upload_generator(),
                    headers={"Content-Type": "application/octet-stream"},
                    timeout=aiohttp.ClientTimeout(total=4),
                ) as r:
                    await r.read()
            except Exception:
                pass

        await asyncio.gather(ul_worker(), ul_worker())
            
        ul_elapsed  = time.monotonic() - ul_start
        if ul_elapsed == 0: ul_elapsed = 0.001
        upload_mbps = (ul_bytes * 8) / ul_elapsed / 1_000_000

    return download_mbps, upload_mbps, ping_ms, jitter_ms


# ─────────────────────────── Command handler ────────────────────────────────

@app.on_message(filters.command(["speedtest", "stest", "netspeed"]) & ~app.bl_users)
async def speedtest_handler(_, m: types.Message):

    sent = await m.reply_text(
        f"{_e(E_BOLT, '⚡')} <b>Running Speed Test…</b>\n\n"
        f"<blockquote>{_e(E_SEARCH, '🔍')} Connecting to best server…\n"
        f"{_e(E_DL, '📥')} Testing download speed…\n"
        f"{_e(E_UL, '📤')} Testing upload speed…\n\n"
        "<i>Please wait (~30 seconds).</i></blockquote>",
        parse_mode=enums.ParseMode.HTML,
    )

    try:
        dl, ul, ping, jitter = await _run_speedtest()

        caption = (
            f"{_e(E_BOLT, '⚡')} <b>Speed Test Results</b>\n\n"
            f"{_e(E_NETWORK, '🌐')} <b>Network :</b>  <code>Toxic Pvt Network</code>\n"
            f"{_e(E_LOCATION, '📍')} <b>Location :</b> <code>Rajasthan, India</code>\n\n"
            f"{_e(E_DL, '📥')} <b>Download :</b> <code>{dl:.2f} Mbps</code>\n"
            f"{_e(E_UL, '📤')} <b>Upload   :</b> <code>{ul:.2f} Mbps</code>\n"
            f"{_e(E_PING, '🔗')} <b>Ping     :</b> <code>{ping:.0f} ms</code>\n"
            f"{_e(E_WARN, '📡')} <b>Jitter   :</b> <code>{jitter:.1f} ms</code>"
        )

        img_buf = await asyncio.get_event_loop().run_in_executor(
            None, _draw_speedtest_image, dl, ul, ping, jitter
        )

        await sent.delete()
        await m.reply_photo(
            photo=img_buf,
            caption=caption,
            parse_mode=enums.ParseMode.HTML,
        )

    except Exception as e:
        await sent.edit_text(
            f"{_e(E_ERROR, '❌')} <b>Speed Test Failed</b>\n\n"
            f"<blockquote><b>Error:</b> <code>{e}</code>\n\n"
            f"Install speedtest-cli:\n"
            f"<code>pip install speedtest-cli</code></blockquote>",
            parse_mode=enums.ParseMode.HTML,
        )
