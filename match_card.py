
from pathlib import Path
from zoneinfo import ZoneInfo
import re
import tempfile
import urllib.request
import urllib.error

from PIL import Image, ImageDraw, ImageFont, ImageFilter

ASSETS_DIR = Path(__file__).with_name("assets")
FONTS_DIR = ASSETS_DIR / "fonts"
FONT_REGULAR = FONTS_DIR / "DejaVuSans.ttf"
FONT_BOLD = FONTS_DIR / "DejaVuSans-Bold.ttf"

LOCAL_FLAGS_DIR = ASSETS_DIR / "flags"
CACHE_FLAGS_DIR = Path(tempfile.gettempdir()) / "worldcup_flags_hd"

TEAM_FLAG_CODES = {
    "Algeria": ["dz"],
    "Argentina": ["ar"],
    "Australia": ["au"],
    "Austria": ["at"],
    "Belgium": ["be"],
    "Bosnia & Herzegovina": ["ba"],
    "Brazil": ["br"],
    "Canada": ["ca"],
    "Cape Verde": ["cv"],
    "Colombia": ["co"],
    "Croatia": ["hr"],
    "Curaçao": ["cw"],
    "Czech Republic": ["cz"],
    "DR Congo": ["cd"],
    "Ecuador": ["ec"],
    "Egypt": ["eg"],
    "England": ["gb-eng", "gb"],
    "France": ["fr"],
    "Germany": ["de"],
    "Ghana": ["gh"],
    "Haiti": ["ht"],
    "Iran": ["ir"],
    "Iraq": ["iq"],
    "Ivory Coast": ["ci"],
    "Japan": ["jp"],
    "Jordan": ["jo"],
    "Mexico": ["mx"],
    "Morocco": ["ma"],
    "Netherlands": ["nl"],
    "New Zealand": ["nz"],
    "Norway": ["no"],
    "Panama": ["pa"],
    "Paraguay": ["py"],
    "Portugal": ["pt"],
    "Qatar": ["qa"],
    "Saudi Arabia": ["sa"],
    "Scotland": ["gb-sct", "gb"],
    "Senegal": ["sn"],
    "South Africa": ["za"],
    "South Korea": ["kr"],
    "Spain": ["es"],
    "Sweden": ["se"],
    "Switzerland": ["ch"],
    "Tunisia": ["tn"],
    "Turkey": ["tr"],
    "USA": ["us"],
    "Uruguay": ["uy"],
    "Uzbekistan": ["uz"],
}


def _font(path, size: int):
    candidates = [path]
    try:
        name = Path(path).name
        candidates += [name, f"/usr/share/fonts/truetype/dejavu/{name}"]
    except Exception:
        pass

    for candidate in candidates:
        try:
            return ImageFont.truetype(str(candidate), size)
        except Exception:
            continue

    return ImageFont.load_default()


def _slug(name: str) -> str:
    s = name.lower().replace("&", "and")
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def _short(name: str) -> str:
    mapping = {
        "Bosnia & Herzegovina": "Bosnia & Herz.",
        "Czech Republic": "Czech Republic",
        "Saudi Arabia": "Saudi Arabia",
        "South Africa": "South Africa",
        "South Korea": "South Korea",
        "New Zealand": "New Zealand",
        "Ivory Coast": "Ivory Coast",
        "Cape Verde": "Cape Verde",
    }
    return mapping.get(name, name)


def _safe_group_label(value: str | None) -> str:
    if not value:
        return "NEXT MATCH"
    m = re.search(r"([A-L])$", str(value))
    if "Группа" in str(value) and m:
        return f"GROUP {m.group(1)}"
    return str(value).upper()


def _fit_text(draw, text: str, max_width: int, start_size: int, min_size: int = 28):
    size = start_size
    while size >= min_size:
        font = _font(FONT_BOLD, size)
        if draw.textlength(text, font=font) <= max_width:
            return font
        size -= 2
    return _font(FONT_BOLD, min_size)


def _crop_cover(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    img = img.convert("RGB")
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w = int(src_w * scale)
    new_h = int(src_h * scale)
    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))


def _local_flag_path(team_name: str) -> Path | None:
    path = LOCAL_FLAGS_DIR / f"{_slug(team_name)}.png"
    if path.exists() and path.stat().st_size > 1000:
        return path
    return None


def _download_flag(team_name: str) -> Path | None:
    CACHE_FLAGS_DIR.mkdir(parents=True, exist_ok=True)
    codes = TEAM_FLAG_CODES.get(team_name, [])
    if not codes:
        return None

    for code in codes:
        cache_path = CACHE_FLAGS_DIR / f"{_slug(team_name)}_{code}.png"
        if cache_path.exists() and cache_path.stat().st_size > 1000:
            return cache_path
        urls = [
            f"https://flagcdn.com/w640/{code}.png",
            f"https://flagcdn.com/w320/{code}.png",
        ]
        for url in urls:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "worldcup-telegram-bot/1.0"})
                with urllib.request.urlopen(req, timeout=8) as response:
                    data = response.read()
                if len(data) > 1000:
                    cache_path.write_bytes(data)
                    return cache_path
            except (urllib.error.URLError, TimeoutError, OSError):
                continue
    return None


def _flag_path(team_name: str) -> Path | None:
    return _download_flag(team_name) or _local_flag_path(team_name)


def _rounded_mask(size, radius):
    mask = Image.new("L", size, 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    return mask


def _draw_flag_image(base_img: Image.Image, team_name: str, box: tuple[int, int, int, int], border_color=(230, 235, 244, 255)):
    path = _flag_path(team_name)
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1

    shadow = Image.new("RGBA", (w + 24, h + 24), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((12, 12, w + 12, h + 12), radius=18, fill=(0, 0, 0, 140))
    shadow = shadow.filter(ImageFilter.GaussianBlur(10))
    base_img.alpha_composite(shadow, (x1 - 12, y1 - 12))

    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    mask = _rounded_mask((w, h), 18)

    if path and path.exists():
        flag = Image.open(path)
        flag = _crop_cover(flag, w, h).convert("RGBA")
        canvas.alpha_composite(flag)
        canvas.putalpha(mask)
    else:
        cd = ImageDraw.Draw(canvas)
        cd.rounded_rectangle((0, 0, w, h), radius=18, fill=(40, 53, 80, 255))
        initials = "".join(word[0] for word in team_name.split()[:2]).upper()
        f = _font(FONT_BOLD, min(58, max(40, w // 5)))
        tw = cd.textlength(initials, font=f)
        cd.text(((w - tw) / 2, h / 2 - 26), initials, font=f, fill=(255, 255, 255, 255))
        canvas.putalpha(mask)

    base_img.alpha_composite(canvas, (x1, y1))
    d = ImageDraw.Draw(base_img)
    d.rounded_rectangle((x1, y1, x2, y2), radius=18, outline=border_color, width=3)


def _panel(draw: ImageDraw.ImageDraw, box, fill, outline, radius=28, width=3):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _vertical_gradient(size, top_rgb, bottom_rgb):
    w, h = size
    img = Image.new("RGBA", size)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(h - 1, 1)
        r = int(top_rgb[0] * (1 - t) + bottom_rgb[0] * t)
        g = int(top_rgb[1] * (1 - t) + bottom_rgb[1] * t)
        b = int(top_rgb[2] * (1 - t) + bottom_rgb[2] * t)
        d.line((0, y, w, y), fill=(r, g, b, 255))
    return img


def build_match_card(row, tz: ZoneInfo) -> str:
    width, height = 1120, 1400
    img = _vertical_gradient((width, height), (7, 18, 40), (3, 9, 24))
    draw = ImageDraw.Draw(img)

    # Background glows
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((-120, 240, 320, 760), fill=(0, 80, 180, 70))
    gd.ellipse((width - 320, 240, width + 120, 760), fill=(180, 0, 30, 70))
    gd.ellipse((380, 360, 740, 860), fill=(245, 185, 40, 35))
    glow = glow.filter(ImageFilter.GaussianBlur(70))
    img.alpha_composite(glow)

    gold = (230, 182, 72, 255)
    blue_line = (70, 120, 220, 255)
    red_line = (210, 80, 90, 255)
    white = (242, 245, 250, 255)
    muted = (190, 205, 230, 255)

    # Outer frame
    _panel(draw, (18, 18, width - 18, height - 18), (4, 11, 26, 55), gold, radius=38, width=2)
    _panel(draw, (32, 32, width - 32, height - 32), (8, 18, 36, 90), (90, 120, 180, 130), radius=32, width=1)

    # Header
    _panel(draw, (40, 42, width - 40, 240), (5, 15, 32, 220), (85, 118, 175, 255), radius=28, width=2)
    title_font = _font(FONT_BOLD, 66)
    info_font = _font(FONT_REGULAR, 30)
    group_font = _font(FONT_BOLD, 28)
    draw.text((170, 78), "WORLD CUP 2026", font=title_font, fill=white)

    # Simple gold trophy marker without emoji
    _panel(draw, (70, 72, 130, 184), (55, 40, 0, 180), gold, radius=20, width=2)
    cup_font = _font(FONT_BOLD, 26)
    draw.text((82, 112), "WC", font=cup_font, fill=(30, 20, 0, 255))

    kickoff = row['kickoff_utc'].astimezone(tz)
    date_box = (175, 158, 410, 208)
    time_box = (435, 158, 620, 208)
    _panel(draw, date_box, (8, 25, 54, 255), (52, 158, 255, 255), radius=16, width=2)
    _panel(draw, time_box, (8, 25, 54, 255), (52, 158, 255, 255), radius=16, width=2)
    draw.text((195, 171), kickoff.strftime('%d.%m.%Y'), font=info_font, fill=white)
    draw.text((470, 171), kickoff.strftime('%H:%M'), font=info_font, fill=white)

    stage = _safe_group_label(row.get('group_name') or row.get('round_name'))
    stage_w = draw.textlength(stage, font=group_font)
    stage_box = (width - 40 - int(stage_w) - 70, 96, width - 72, 168)
    _panel(draw, stage_box, (16, 22, 40, 255), gold, radius=18, width=2)
    draw.text((stage_box[0] + 28, stage_box[1] + 20), stage, font=group_font, fill=gold)

    draw.line((42, 242, width - 42, 242), fill=gold, width=2)
    draw.line((42, 244, width - 42, 244), fill=(255, 220, 120, 80), width=1)

    # Main field area
    _panel(draw, (40, 255, width - 40, 1160), (5, 14, 28, 110), (76, 116, 180, 255), radius=32, width=2)
    # pitch hints
    draw.line((width // 2, 255, width // 2, 1160), fill=(50, 82, 130, 140), width=3)
    draw.ellipse((width//2 - 110, 610 - 110, width//2 + 110, 610 + 110), outline=(50,82,130,140), width=3)
    draw.ellipse((width//2 - 10, 610 - 10, width//2 + 10, 610 + 10), fill=gold)

    # Light beams
    for offset in [0, 22, 44, 66]:
        draw.arc((-120-offset, 320-offset, 500, 920), 292, 350, fill=(80,130,230,100), width=2)
        draw.arc((width-500, 320-offset, width+120+offset, 920), 190, 248, fill=(180,70,80,100), width=2)

    left_panel = (70, 470, 440, 948)
    right_panel = (680, 470, 1050, 948)
    _panel(draw, left_panel, (8, 18, 38, 150), blue_line, radius=30, width=3)
    _panel(draw, right_panel, (8, 18, 38, 150), red_line, radius=30, width=3)

    # Rectangular flags
    _draw_flag_image(img, str(row['home_team']), (88, 500, 422, 705), border_color=(150, 190, 250, 255))
    _draw_flag_image(img, str(row['away_team']), (698, 500, 1032, 705), border_color=(250, 165, 170, 255))

    name_font_left = _fit_text(draw, _short(str(row['home_team'])), 320, 46)
    name_font_right = _fit_text(draw, _short(str(row['away_team'])), 320, 46)
    left_name = _short(str(row['home_team'])).upper()
    right_name = _short(str(row['away_team'])).upper()
    lw = draw.textlength(left_name, font=name_font_left)
    rw = draw.textlength(right_name, font=name_font_right)
    draw.text((255 - lw/2, 805), left_name, font=name_font_left, fill=white)
    draw.text((865 - rw/2, 805), right_name, font=name_font_right, fill=white)

    # VS medallion
    medal = Image.new('RGBA', (170, 170), (0,0,0,0))
    md = ImageDraw.Draw(medal)
    md.ellipse((0,0,169,169), fill=(18, 26, 42, 255), outline=gold, width=5)
    md.ellipse((14,14,155,155), outline=(255, 235, 170, 120), width=2)
    vs_font = _font(FONT_BOLD, 62)
    md.text((45, 51), 'VS', font=vs_font, fill=gold)
    medal = medal.filter(ImageFilter.GaussianBlur(0.2))
    img.alpha_composite(medal, (width//2 - 85, 610 - 85))
    # glow dots
    for dx, dy in [(0, -92), (0, 92), (-92, 0), (92, 0)]:
        draw.ellipse((width//2+dx-5, 610+dy-5, width//2+dx+5, 610+dy+5), fill=(255,210,120,255))

    # Stadium bar
    venue = str(row.get('venue') or 'Venue TBA')
    _panel(draw, (70, 1015, 1050, 1095), (7, 18, 38, 230), (76, 116, 180, 255), radius=22, width=2)
    vfont = _font(FONT_REGULAR, 26)
    vfont_bold = _font(FONT_BOLD, 26)
    draw.line((115, 1055, 245, 1055), fill=gold, width=2)
    draw.line((875, 1055, 1005, 1055), fill=gold, width=2)
    label = 'STADIUM'
    venue_w = draw.textlength(venue, font=vfont)
    label_w = draw.textlength(label, font=vfont_bold)
    total_w = label_w + 18 + venue_w
    start_x = width/2 - total_w/2
    draw.text((start_x, 1036), label, font=vfont_bold, fill=white)
    draw.text((start_x + label_w + 18, 1036), venue, font=vfont, fill=white)

    # Bottom accent
    draw.line((80, 1340, 460, 1340), fill=gold, width=2)
    draw.line((660, 1340, 1040, 1340), fill=gold, width=2)
    draw.ellipse((523, 1312, 597, 1386), fill=(18,26,42,255), outline=gold, width=3)
    ball_font = _font(FONT_BOLD, 28)
    draw.text((546, 1333), 'FC', font=ball_font, fill=gold)

    temp = Path(tempfile.gettempdir()) / f"match_card_{row['fixture_id']}.png"
    img.convert('RGB').save(temp, format='PNG')
    return str(temp)
