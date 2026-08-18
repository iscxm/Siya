import os
import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from Dev import config
from Dev.helpers._dataclass import Track


def _load_font(path: str, size: int):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


class Thumbnail:
    def __init__(self):
        # Canvas: same 16:9 ratio as reference
        self.W, self.H = 1280, 640

        # Album art: left side, square, vertically centered
        self.ART_SIZE = 580
        self.ART_X    = 40
        self.ART_Y    = (self.H - self.ART_SIZE) // 2   # 30px top/bottom margin

        # Text zone: right of artwork
        self.TX = self.ART_X + self.ART_SIZE + 60
        self.TW = self.W - self.TX - 50

        bold_path  = "Dev/helpers/Raleway-Bold.ttf"
        light_path = "Dev/helpers/Inter-Light.ttf"

        self.f_siya    = _load_font(light_path, 22)   # "Siya" italic tag
        self.f_title   = _load_font(bold_path,  56)   # Song title
        self.f_artist  = _load_font(light_path, 30)   # Artist name
        self.f_time    = _load_font(light_path, 24)   # Timestamps
        self.f_ctrl    = _load_font(bold_path,  54)   # Playback symbols

    # ─── helpers ──────────────────────────────────────────────────────────────
    async def _fetch(self, url: str, path: str) -> None:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                with open(path, "wb") as f:
                    f.write(await r.read())

    @staticmethod
    def _round_img(img: Image.Image, radius: int = 24) -> Image.Image:
        img = img.convert("RGBA")
        mask = Image.new("L", img.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, img.width, img.height), radius=radius, fill=255
        )
        img.putalpha(mask)
        return img

    def _fit_text(self, draw, text: str, font, max_w: int) -> str:
        if not text:
            return ""
        while text:
            try:
                bb = draw.textbbox((0, 0), text, font=font)
                if (bb[2] - bb[0]) <= max_w:
                    return text
            except Exception:
                return text[:40]
            text = text[:-1]
        return ""

    # ─── main ─────────────────────────────────────────────────────────────────
    async def generate(self, song: Track, size=(1280, 640)) -> str:
        try:
            os.makedirs("cache", exist_ok=True)
            tmp = f"cache/tmp_{song.id}.jpg"
            out = f"cache/{song.id}.png"

            if os.path.exists(out):
                return out

            await self._fetch(song.thumbnail, tmp)
            art = Image.open(tmp).convert("RGB")

            # ── Background: pure near-black (like the iPhone screenshot) ──────
            # Sample average dark color from art edges for a slight tint
            thumb_small = art.resize((8, 8)).convert("RGB")
            avg_r = sum(p[0] for p in thumb_small.getdata()) // 64
            avg_g = sum(p[1] for p in thumb_small.getdata()) // 64
            avg_b = sum(p[2] for p in thumb_small.getdata()) // 64
            # Mix with near-black (reference bg is ~#111)
            bg_r = max(0, min(30, avg_r // 6))
            bg_g = max(0, min(30, avg_g // 6))
            bg_b = max(0, min(30, avg_b // 6))
            canvas = Image.new("RGB", (self.W, self.H), (bg_r, bg_g, bg_b))

            draw = ImageDraw.Draw(canvas)

            # ── Artwork: square, rounded, left side ───────────────────────────
            art_sq = ImageOps.fit(
                art, (self.ART_SIZE, self.ART_SIZE),
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5)
            )
            art_r = self._round_img(art_sq, radius=18)
            canvas.paste(art_r, (self.ART_X, self.ART_Y), art_r)

            # ── Right-side text ───────────────────────────────────────────────
            W   = (255, 255, 255)
            GRY = (160, 160, 160)
            TX, TW = self.TX, self.TW
            TY = self.ART_Y + 10

            # "Siya  🎧" row — italic small text (reference: "iPhone 🎧")
            # Use actual Unicode headphone char U+1F3A7
            siya_tag = "\u273f  \u1d10\u1d0e\u1d1b\u1d1e\u1d0f  \U0001f3a7"  # "✿  Siya  🎧" style
            # Simpler & reliable: just plain italic-looking tag
            siya_tag = "Siya  \U0001f3a7"
            draw.text((TX, TY), siya_tag, font=self.f_siya, fill=GRY)
            TY += 34

            # Song title (large bold)
            title = self._fit_text(draw, song.title or "Unknown", self.f_title, TW)
            draw.text((TX, TY), title, font=self.f_title, fill=W)
            TY += 70

            # Artist / channel
            artist = self._fit_text(draw, (song.channel_name or "")[:35], self.f_artist, TW)
            draw.text((TX, TY), artist, font=self.f_artist, fill=GRY)
            TY += 55

            # ── Progress bar (reference style: thick dots on left/right + bar) ──
            TY += 10
            BAR_H = 6
            BAR_FILL = (80, 80, 80)    # dark track
            BAR_PROG  = (220, 220, 220) # white/light progress
            BAR_DOT   = W

            draw.rounded_rectangle(
                [TX, TY, TX + TW, TY + BAR_H], radius=3, fill=BAR_FILL
            )
            pw = int(TW * 0.44)   # ~44% progress (matches reference ~1:27/3:20)
            draw.rounded_rectangle(
                [TX, TY, TX + pw, TY + BAR_H], radius=3, fill=BAR_PROG
            )
            # Scrubber dot (reference: small filled circle at progress point)
            cx = TX + pw
            draw.ellipse([cx - 6, TY - 3, cx + 6, TY + BAR_H + 3], fill=BAR_DOT)
            TY += BAR_H + 14

            # Timestamps: "1:27" left, "-1:53" right
            dur = song.duration or "0:00"
            draw.text((TX, TY), "0:01", font=self.f_time, fill=GRY)
            try:
                dbb = draw.textbbox((0, 0), f"-{dur}", font=self.f_time)
                draw.text((TX + TW - (dbb[2] - dbb[0]), TY), f"-{dur}", font=self.f_time, fill=GRY)
            except Exception:
                pass
            TY += 46

            # ── Playback controls (reference: |◀◀  ⏸  ▶▶|  AirPlay) ───────────
            # Use same character style as reference image
            ctrl_syms  = ["\u23ee", "\u23f8", "\u23ed", "\U0001f4f6"]  # prev pause next airplay
            ctrl_sizes = [self.f_ctrl, self.f_ctrl, self.f_ctrl, self.f_time]
            ctrl_alpha = [180, 255, 180, 140]  # center (pause) is brightest

            seg = TW // (len(ctrl_syms) + 1)
            for i, (sym, font, alpha) in enumerate(zip(ctrl_syms, ctrl_sizes, ctrl_alpha)):
                sx = TX + (i + 1) * seg
                try:
                    bb = draw.textbbox((0, 0), sym, font=font)
                    sw = bb[2] - bb[0]
                    sh = bb[3] - bb[1]
                except Exception:
                    sw, sh = 40, 40
                col = (*W, alpha)
                draw.text((sx - sw // 2, TY), sym, font=font, fill=col)
            TY += 72

            # ── Volume bar (reference: small speaker icons + thin bar) ─────────
            # Left speaker icon
            draw.text((TX, TY + 2), "\U0001f508", font=self.f_time, fill=(120, 120, 120))
            VS = TX + 30
            VE = TX + TW - 30
            draw.rounded_rectangle([VS, TY + 7, VE, TY + 11], radius=2, fill=(60, 60, 60))
            draw.rounded_rectangle(
                [VS, TY + 7, VS + int((VE - VS) * 0.62), TY + 11],
                radius=2, fill=(180, 180, 180)
            )
            # Right speaker icon
            draw.text((VE + 6, TY + 2), "\U0001f50a", font=self.f_time, fill=(120, 120, 120))

            # ── Save ──────────────────────────────────────────────────────────
            canvas.save(out, "PNG")
            try:
                os.remove(tmp)
            except Exception:
                pass

            return out

        except Exception:
            import traceback
            traceback.print_exc()
            return config.DEFAULT_THUMB
