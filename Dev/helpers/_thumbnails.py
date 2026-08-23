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
        self.W, self.H = 1280, 720
        bold_path = "Dev/helpers/Raleway-Bold.ttf"
        light_path = "Dev/helpers/Inter-Light.ttf"

        self.font_small = _load_font(light_path, 28)
        self.font_title = _load_font(bold_path, 42)
        self.font_heading = _load_font(bold_path, 60)
        self.font_regular = _load_font(light_path, 32)

    async def _fetch(self, url: str, path: str) -> None:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                with open(path, "wb") as f:
                    f.write(await r.read())

    @staticmethod
    def _round_img(img: Image.Image, radius: int = 24) -> Image.Image:
        img = img.convert("RGBA")
        mask = Image.new("L", img.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, img.width, img.height), radius=radius, fill=255)
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

    async def generate(self, song: Track, size=(1280, 640)) -> str:
        try:
            os.makedirs("cache", exist_ok=True)
            tmp = f"cache/tmp_{song.id}.jpg"
            out = f"cache/{song.id}.png"
            if os.path.exists(out):
                return out
            await self._fetch(song.thumbnail, tmp)
            import textwrap

            art = Image.open(tmp).convert("RGB")
            
            # Create Background
            image1 = ImageOps.fit(art, (self.W, self.H), method=Image.Resampling.LANCZOS)
            background = image1.filter(ImageFilter.GaussianBlur(10))
            enhancer = ImageEnhance.Brightness(background)
            background = enhancer.enhance(0.6)

            # Create Square Logo (Rounded)
            logo = ImageOps.fit(art, (460, 460), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
            logo = self._round_img(logo, radius=32)
            
            # Paste Logo (use logo as mask for transparency)
            background.paste(logo, (50, 130), logo)
            draw = ImageDraw.Draw(background)

            # Draw Texts
            title = song.title or "Unknown"
            duration = song.duration or "0:00"
            channel = song.channel_name or "Unknown Channel"

            draw.text((30, 30), "Toxic Bots @dotshv", fill="white", font=self.font_small)
            
            text_x = 580
            draw.text(
                (text_x, 150),
                "NOW PLAYING",
                fill="white",
                stroke_width=2,
                stroke_fill="black",
                font=self.font_heading,
            )

            # Wrap Title
            para = textwrap.wrap(title, width=28)
            j = 0
            for line in para:
                if j == 1:
                    draw.text(
                        (text_x, 320),
                        f"{line}",
                        fill="white",
                        stroke_width=1,
                        stroke_fill="black",
                        font=self.font_title,
                    )
                    j += 1
                elif j == 0:
                    draw.text(
                        (text_x, 260),
                        f"{line}",
                        fill="white",
                        stroke_width=1,
                        stroke_fill="black",
                        font=self.font_title,
                    )
                    j += 1

            draw.text(
                (text_x, 430),
                f"Channel : {channel[:26]}",
                (255, 255, 255),
                font=self.font_regular,
            )
            draw.text(
                (text_x, 490),
                f"Duration : {duration[:26]} Mins",
                (255, 255, 255),
                font=self.font_regular,
            )
            draw.text(
                (text_x, 550), 
                "Powered By : Toxic Bots", 
                (255, 255, 255), 
                font=self.font_regular
            )

            background.save(out, "PNG")
            try:
                os.remove(tmp)
            except Exception:
                pass
            return out
        except Exception:
            return config.DEFAULT_THUMB
