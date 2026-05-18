import os
import aiofiles
import aiohttp

from PIL import (
    Image,
    ImageDraw,
    ImageEnhance,
    ImageFilter,
    ImageFont
)

from py_yt import VideosSearch
from config import YOUTUBE_IMG_URL
from SONALI_MUSIC import app

CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)


# ---------------------------------------------------
# TEXT TRIM
# ---------------------------------------------------

def trim_to_width(text, font, max_width):

    ellipsis = "..."

    if font.getlength(text) <= max_width:
        return text

    for i in range(len(text), 0, -1):

        new = text[:i] + ellipsis

        if font.getlength(new) <= max_width:
            return new

    return ellipsis


# ---------------------------------------------------
# MAIN FUNCTION
# ---------------------------------------------------

async def get_thumb(videoid: str, player_username: str = None):

    if player_username is None:
        player_username = app.username

    cache_path = os.path.join(
        CACHE_DIR,
        f"{videoid}_shashank.png"
    )

    if os.path.exists(cache_path):
        return cache_path

    # ---------------------------------------------------
    # FETCH VIDEO DETAILS
    # ---------------------------------------------------

    try:

        results = VideosSearch(
            f"https://www.youtube.com/watch?v={videoid}",
            limit=1
        )

        search_result = await results.next()

        data = search_result.get("result", [])[0]

        title = data.get(
            "title",
            "Unknown Title"
        )

        artist = data.get(
            "channel",
            {}
        ).get(
            "name",
            "Unknown Artist"
        )

        duration = data.get(
            "duration",
            "00:00"
        )

        views = data.get(
            "viewCount",
            {}
        ).get(
            "short",
            "0 views"
        )

        thumbnail = data.get(
            "thumbnails",
            [{}]
        )[0].get(
            "url",
            YOUTUBE_IMG_URL
        )

    except Exception:

        title = "Unknown Title"
        artist = "Unknown Artist"
        duration = "03:51"
        views = "0 views"
        thumbnail = YOUTUBE_IMG_URL

    # ---------------------------------------------------
    # DOWNLOAD THUMBNAIL
    # ---------------------------------------------------

    thumb_path = os.path.join(
        CACHE_DIR,
        f"raw_{videoid}.jpg"
    )

    try:

        async with aiohttp.ClientSession() as s:

            async with s.get(thumbnail) as r:

                if r.status == 200:

                    async with aiofiles.open(
                        thumb_path,
                        "wb"
                    ) as f:

                        await f.write(await r.read())

    except:

        return YOUTUBE_IMG_URL

    # ---------------------------------------------------
    # IMAGE SETUP
    # ---------------------------------------------------

    W, H = 1280, 720

    img = Image.open(
        thumb_path
    ).convert("RGBA")

    # ---------------------------------------------------
    # WHITE FROSTED BACKGROUND
    # ---------------------------------------------------

    bg = img.resize((W, H))

    bg = bg.filter(
        ImageFilter.GaussianBlur(radius=40)
    )

    enhancer = ImageEnhance.Brightness(bg)

    bg = enhancer.enhance(1.4)

    white_layer = Image.new(
        "RGBA",
        (W, H),
        (255, 255, 255, 90)
    )

    bg = Image.alpha_composite(
        bg,
        white_layer
    )

    draw = ImageDraw.Draw(bg)

    # ---------------------------------------------------
    # LOAD FONTS
    # ---------------------------------------------------

    try:

        font_bold = "SONALI_MUSIC/assets/font2.ttf"
        font_med = "SONALI_MUSIC/assets/font.ttf"

        title_font = ImageFont.truetype(
            font_bold,
            58
        )

        artist_font = ImageFont.truetype(
            font_med,
            40
        )

        time_font = ImageFont.truetype(
            font_med,
            30
        )

    except:

        title_font = artist_font = time_font = ImageFont.load_default()

    # ---------------------------------------------------
    # ALBUM IMAGE
    # ---------------------------------------------------

    frame_w = 450
    frame_h = 450

    frame_x = 90
    frame_y = (H - frame_h) // 2

    album = img.resize(
        (frame_w, frame_h),
        Image.LANCZOS
    )

    # Rounded mask
    mask = Image.new(
        "L",
        (frame_w, frame_h),
        0
    )

    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, frame_w, frame_h),
        radius=45,
        fill=255
    )

    # White glow
    glow = Image.new(
        "RGBA",
        (frame_w + 70, frame_h + 70),
        (0, 0, 0, 0)
    )

    ImageDraw.Draw(glow).rounded_rectangle(
        (
            35,
            35,
            frame_w + 35,
            frame_h + 35
        ),
        radius=50,
        fill=(255, 255, 255, 130)
    )

    glow = glow.filter(
        ImageFilter.GaussianBlur(radius=30)
    )

    bg.paste(
        glow,
        (frame_x - 35, frame_y - 35),
        glow
    )

    # Paste album
    bg.paste(
        album,
        (frame_x, frame_y),
        mask
    )

    # Border
    draw.rounded_rectangle(
        (
            frame_x,
            frame_y,
            frame_x + frame_w,
            frame_y + frame_h
        ),
        radius=45,
        outline=(255, 255, 255, 190),
        width=5
    )

    # ---------------------------------------------------
    # GLASS CARD
    # ---------------------------------------------------

    text_x = 620

    glass_rect = [
        text_x - 40,
        frame_y,
        W - 70,
        frame_y + frame_h
    ]

    overlay = Image.new(
        "RGBA",
        (W, H),
        (0, 0, 0, 0)
    )

    d_overlay = ImageDraw.Draw(overlay)

    d_overlay.rounded_rectangle(
        glass_rect,
        radius=40,
        fill=(255, 255, 255, 75),
        outline=(255, 255, 255, 130),
        width=2
    )

    bg.alpha_composite(overlay)

    # ---------------------------------------------------
    # TEXT
    # ---------------------------------------------------

    title_color = (255, 70, 170)
    sub_color = (255, 120, 190)

    clean_title = trim_to_width(
        title,
        title_font,
        520
    )

    clean_artist = trim_to_width(
        f"By {artist}",
        artist_font,
        500
    )

    draw.text(
        (text_x, frame_y + 45),
        clean_title,
        font=title_font,
        fill=title_color
    )

    draw.text(
        (text_x, frame_y + 130),
        clean_artist,
        font=artist_font,
        fill=sub_color
    )

    draw.text(
        (text_x, frame_y + 205),
        f"Views: {views}",
        font=time_font,
        fill=sub_color
    )

    # ---------------------------------------------------
    # MUSIC BAR
    # ---------------------------------------------------

    bar_width = 500
    bar_height = 10

    bar_x = text_x
    bar_y = frame_y + 330

    # White line
    draw.rounded_rectangle(
        (
            bar_x,
            bar_y,
            bar_x + bar_width,
            bar_y + bar_height
        ),
        radius=10,
        fill=(255, 255, 255, 180)
    )

    # Pink progress
    progress = 0.40

    draw.rounded_rectangle(
        (
            bar_x,
            bar_y,
            bar_x + (bar_width * progress),
            bar_y + bar_height
        ),
        radius=10,
        fill=(255, 40, 150)
    )

    # Circle
    circle_r = 13

    cx = bar_x + (bar_width * progress)

    draw.ellipse(
        (
            cx - circle_r,
            bar_y - circle_r + 5,
            cx + circle_r,
            bar_y + circle_r + 5
        ),
        fill=(255, 255, 255)
    )

    # Time Text
    draw.text(
        (bar_x, bar_y + 32),
        "00:25",
        font=time_font,
        fill=(255, 40, 150)
    )

    draw.text(
        (bar_x + bar_width - 80, bar_y + 32),
        duration,
        font=time_font,
        fill=(255, 40, 150)
    )

    # ---------------------------------------------------
    # SAVE
    # ---------------------------------------------------

    bg = bg.convert("RGB")

    bg.save(
        cache_path,
        quality=95
    )

    try:
        os.remove(thumb_path)
    except:
        pass

    return cache_path
