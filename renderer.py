#!/usr/bin/env python3
"""
renderer.py
Рендерит карточки двух стилей:
 - classic: карточка в тёмной полупрозрачной панели, маленький аватар, многострочный текст.
 - spanch: стиль как в примере (размытый фон, крупный текст справа от большого круглого аватара).
Поддерживает выбор фона: имя файла в assets/backgrounds/, абсолютный/отрелативный путь или случайный.
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import requests
from io import BytesIO
import os
import random
from datetime import datetime

HERE = os.path.dirname(__file__)
ASSETS_DIR = os.path.join(HERE, "assets")
FONTS_DIR = os.path.join(ASSETS_DIR, "fonts")
BACKGROUNDS_DIR = os.path.join(ASSETS_DIR, "backgrounds")

# --- Helpers -----------------------------------------------------------------
def load_font(filename, size):
    path = os.path.join(FONTS_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Font not found: {path}")
    return ImageFont.truetype(path, size)

def fetch_image(path_or_url, size=None):
    if path_or_url is None:
        return None
    try:
        if str(path_or_url).startswith("http://") or str(path_or_url).startswith("https://"):
            r = requests.get(path_or_url, timeout=10)
            r.raise_for_status()
            img = Image.open(BytesIO(r.content)).convert("RGBA")
        else:
            img = Image.open(path_or_url).convert("RGBA")
        if size:
            img = img.resize(size, Image.LANCZOS)
        return img
    except Exception as e:
        print("fetch_image:", e)
        return None

def circle_avatar(img, size, border=6, border_color=(255,255,255,255)):
    avatar = img.resize((size, size), Image.LANCZOS).convert("RGBA")
    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)
    md.ellipse((0,0,size,size), fill=255)
    avatar.putalpha(mask)
    out_size = (size + border*2, size + border*2)
    out = Image.new("RGBA", out_size, (0,0,0,0))
    d = ImageDraw.Draw(out)
    d.ellipse((0,0,out_size[0], out_size[1]), fill=border_color)
    out.paste(avatar, (border, border), avatar)
    return out

def pick_background(bg_spec, target_size):
    W,H = target_size
    if not bg_spec:
        return Image.new("RGBA", target_size, (40,40,40,255))
    # if user passed name only, look into BACKGROUNDS_DIR
    maybe = bg_spec
    candidate = os.path.join(BACKGROUNDS_DIR, bg_spec)
    if os.path.exists(candidate):
        maybe = candidate
    try:
        bg = Image.open(maybe).convert("RGBA")
        bg = ImageOps.fit(bg, target_size, Image.LANCZOS, centering=(0.5,0.5))
        return bg
    except Exception as e:
        print("pick_background:", e)
        return Image.new("RGBA", target_size, (40,40,40,255))

def list_backgrounds():
    if not os.path.isdir(BACKGROUNDS_DIR):
        return []
    return sorted([f for f in os.listdir(BACKGROUNDS_DIR) if os.path.isfile(os.path.join(BACKGROUNDS_DIR, f))])

# --- Text wrapping helper ----------------------------------------------------
def wrap_text_to_width(text, font, max_width, draw):
    words = text.split()
    lines = []
    cur = ""
    for w in words:
        test = (cur + " " + w).strip()
        bbox = draw.textbbox((0,0), test, font=font)
        if bbox[2] <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines

# --- Render styles -----------------------------------------------------------
def render_classic(output_path, avatar, username, text, date, bg_spec, size=(1200,600), watermark=True):
    W,H = size
    canvas = Image.new("RGBA", (W,H), (0,0,0,255))
    bg = pick_background(bg_spec, (W,H))
    # Slight dark overlay for readability
    overlay = Image.new("RGBA", (W,H), (0,0,0,120))
    base = Image.alpha_composite(bg, overlay)
    draw = ImageDraw.Draw(base)

    padding = int(W * 0.05)
    avatar_size = int(min(W,H) * 0.18)
    content_x = padding + avatar_size + int(W * 0.03)
    content_w = W - content_x - padding

    # Panel (soft dark rounded rectangle) behind content to mimic classic card
    panel_w = W - 2*padding
    panel_h = H - 2*padding
    panel = Image.new("RGBA", (panel_w, panel_h), (20,20,20,200))
    # Rounded mask
    mask = Image.new("L", (panel_w, panel_h), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0,0,panel_w,panel_h], radius=24, fill=255)
    base.paste(panel, (padding, padding), mask)

    # Avatar
    av_img = fetch_image(avatar) if avatar else None
    if av_img:
        av_round = circle_avatar(av_img, avatar_size, border=4)
    else:
        placeholder = Image.new("RGBA", (avatar_size, avatar_size), (110,110,110,255))
        av_round = circle_avatar(placeholder, avatar_size, border=4)
    av_x = padding + 8
    av_y = padding + 8
    base.paste(av_round, (av_x, av_y), av_round)

    # Fonts
    try:
        font_name = load_font("Inter-Bold.ttf", size=int(H*0.06))
        font_text = load_font("Inter-Regular.ttf", size=int(H*0.045))
        font_time = load_font("Inter-Regular.ttf", size=int(H*0.035))
        wm_font = load_font("Inter-Regular.ttf", size=int(H*0.03))
    except FileNotFoundError:
        # fallback to default PIL font
        from PIL import ImageFont
        font_name = ImageFont.load_default()
        font_text = ImageFont.load_default()
        font_time = ImageFont.load_default()
        wm_font = ImageFont.load_default()

    # Name
    name_y = av_y + 6
    draw.text((content_x, name_y), username, font=font_name, fill=(255,255,255,255))

    # Text
    text_y = name_y + font_name.getsize(username)[1] + 8
    lines = wrap_text_to_width(text, font_text, content_w - 40, draw)
    max_lines = 8
    line_h = font_text.getsize("A")[1] + 6
    for i, line in enumerate(lines[:max_lines]):
        draw.text((content_x, text_y + i*line_h), line, font=font_text, fill=(230,230,230,255))

    # Time
    if not date:
        date = datetime.now().strftime("%H:%M")
    time_y = H - padding - font_time.getsize(date)[1]
    draw.text((content_x, time_y), date, font=font_time, fill=(200,200,200,220))

    # watermark
    if watermark:
        wm_text = "b.y spanch"
        tb = draw.textbbox((0,0), wm_text, font=wm_font)
        draw.text((W - padding - (tb[2]-tb[0]), padding+8), wm_text, font=wm_font, fill=(255,255,255,70))

    base.convert("RGB").save(output_path, "PNG", quality=95)
    return output_path

def render_spanch(output_path, avatar, username, text, date, bg_spec, size=(1280,720), watermark_text="Автор доработки: @gose222", watermark=True):
    W,H = size
    bg = pick_background(bg_spec, (W,H))

    # Blur + dark overlay
    blurred = bg.filter(ImageFilter.GaussianBlur(radius=12))
    overlay = Image.new("RGBA", (W,H), (0,0,0,100))
    base = Image.alpha_composite(blurred, overlay)
    draw = ImageDraw.Draw(base)

    # Avatar large circle left
    avatar_size = int(H * 0.36)
    avatar_margin_left = int(W * 0.04)
    avatar_center_y = H // 2
    av_img = fetch_image(avatar) if avatar else None
    if av_img:
        av = circle_avatar(av_img, avatar_size, border=6)
    else:
        placeholder = Image.new("RGBA", (avatar_size, avatar_size), (120,120,120,255))
        av = circle_avatar(placeholder, avatar_size, border=6)
    av_x = avatar_margin_left
    av_y = avatar_center_y - av.size[1]//2
    base.paste(av, (av_x, av_y), av)

    # Fonts (scale with height)
    try:
        title_font = load_font("Inter-Bold.ttf", size=int(H * 0.12))
        author_font = load_font("Inter-Regular.ttf", size=int(H * 0.06))
        wm_font = load_font("Inter-Regular.ttf", size=int(H * 0.035))
    except FileNotFoundError:
        from PIL import ImageFont
        title_font = ImageFont.load_default()
        author_font = ImageFont.load_default()
        wm_font = ImageFont.load_default()

    # Content area to right
    content_x = av_x + av.size[0] + int(W * 0.05)
    content_w = W - content_x - int(W * 0.06)
    tmp_draw = ImageDraw.Draw(base)

    # Wrap large text, try to keep 1-3 lines; reduce font if too many lines
    cur_font = title_font
    wrapped = wrap_text_to_width(text, cur_font, content_w, tmp_draw)
    while len(wrapped) > 3:
        # reduce size 90%
        new_size = max(12, int(cur_font.size * 0.9))
        try:
            cur_font = load_font("Inter-Bold.ttf", size=new_size)
        except FileNotFoundError:
            break
        wrapped = wrap_text_to_width(text, cur_font, content_w, tmp_draw)

    # compute vertical start
    total_h = sum([tmp_draw.textbbox((0,0), l, font=cur_font)[3] - tmp_draw.textbbox((0,0), l, font=cur_font)[1] for l in wrapped])
    author_h = tmp_draw.textbbox((0,0), "A", font=author_font)[3]
    spacing = int(H * 0.02)
    start_y = avatar_center_y - (total_h + spacing + author_h)//2

    # Draw lines
    y = start_y
    for line in wrapped:
        draw.text((content_x, y), line, font=cur_font, fill=(255,255,255,255))
        hb = tmp_draw.textbbox((0,0), line, font=cur_font)
        line_h = hb[3] - hb[1]
        y += line_h + int(H * 0.01)

    # author + time
    if not date:
        date = datetime.now().strftime("%H:%M")
    author_line = f"— {username} [{date}]"
    author_y = y + int(H * 0.01)
    draw.text((content_x, author_y), author_line, font=author_font, fill=(230,230,230,230))

    # watermark bottom-right
    if watermark:
        wm_padding = int(W * 0.04)
        tb = draw.textbbox((0,0), watermark_text, font=wm_font)
        wm_x = W - (tb[2]-tb[0]) - wm_padding
        wm_y = H - (tb[3]-tb[1]) - int(H * 0.04)
        draw.text((wm_x, wm_y), watermark_text, font=wm_font, fill=(255,255,255,110))

    base.convert("RGB").save(output_path, "JPEG", quality=92)
    return output_path

# --- Public API --------------------------------------------------------------
def render(output_path,
           style="auto",
           avatar=None,
           username="Username",
           text="Текст сообщения...",
           date=None,
           bg=None,
           size=(1280,720),
           watermark=True):
    # style: "classic", "spanch", "auto"
    if style == "auto":
        # heuristic: if height > width -> classic, else spanch; or prefer spanch
        # default to spanch for wide aspect
        _, H = size
        if size[0] / size[1] > 1.3:
            chosen = "spanch"
        else:
            chosen = "classic"
    else:
        chosen = style

    # If bg == "random", pick random background
    if bg == "random":
        bgs = list_backgrounds()
        if bgs:
            bg = random.choice(bgs)
        else:
            bg = None

    if chosen == "classic":
        return render_classic(output_path, avatar, username, text, date, bg, size=size, watermark=watermark)
    else:
        return render_spanch(output_path, avatar, username, text, date, bg, size=size, watermark_text="Автор доработки: @gose222", watermark=watermark)

if __name__ == "__main__":
    # quick smoke test
    out = render("out_card.jpg", style="spanch", avatar=None, username="Тестовый", text="а на какой город градусы показывает?", date="16:15", bg="pepper.png", size=(1280,720))
    print("Saved:", out)
