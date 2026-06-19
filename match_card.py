
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

        for url in (f"https://flagcdn.com/w640/{code}.png", f"https://flagcdn.com/w320/{code}.png"):
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


def _panel(draw: ImageDraw.ImageDraw, box, fill, outline, radius=28, width=3):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _draw_flag_image(base_img: Image.Image, team_name: str, box: tuple[int, int, int, int], border_color):
    path = _flag_path(team_name)
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1

    shadow = Image.new("RGBA", (w + 36, h + 36), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((18, 18, w + 18, h + 18), radius=22, fill=(0, 0, 0, 150))
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    base_img.alpha_composite(shadow, (x1 - 18, y1 - 18))

    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    mask = _rounded_mask((w, h), 22)

    if path and path.exists():
        flag = Image.open(path)
        flag = _crop_cover(flag, w, h).convert("RGBA")
        canvas.alpha_composite(flag)
        canvas.putalpha(mask)
    else:
        cd = ImageDraw.Draw(canvas)
        cd.rounded_rectangle((0, 0, w, h), radius=22, fill=(40, 53, 80, 255))
        initials = "".join(word[0] for word in team_name.split()[:2]).upper()
        f = _font(FONT_BOLD, min(70, max(42, w // 5)))
        tw = cd.textlength(initials, font=f)
        cd.text(((w - tw) / 2, h / 2 - 34), initials, font=f, fill=(255, 255, 255, 255))
        canvas.putalpha(mask)

    base_img.alpha_composite(canvas, (x1, y1))
    d = ImageDraw.Draw(base_img)
    d.rounded_rectangle((x1, y1, x2, y2), radius=22, outline=border_color, width=4)


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


def _draw_simple_trophy(draw: ImageDraw.ImageDraw, box, gold):
    x1, y1, x2, y2 = box
    w = x2 - x1
    h = y2 - y1
    _panel(draw, box, (55, 42, 4, 230), gold, radius=22, width=2)
    cup = [
        (x1 + w * 0.28, y1 + h * 0.24),
        (x1 + w * 0.72, y1 + h * 0.24),
        (x1 + w * 0.62, y1 + h * 0.58),
        (x1 + w * 0.38, y1 + h * 0.58),
    ]
    draw.polygon(cup, fill=gold)
    draw.arc((x1 + w * 0.12, y1 + h * 0.28, x1 + w * 0.40, y1 + h * 0.56), 90, 270, fill=gold, width=4)
    draw.arc((x1 + w * 0.60, y1 + h * 0.28, x1 + w * 0.88, y1 + h * 0.56), 270, 90, fill=gold, width=4)
    draw.rectangle((x1 + w * 0.46, y1 + h * 0.58, x1 + w * 0.54, y1 + h * 0.73), fill=gold)
    draw.rounded_rectangle((x1 + w * 0.34, y1 + h * 0.73, x1 + w * 0.66, y1 + h * 0.82), radius=5, fill=gold)


def _draw_calendar_icon(draw, x, y, size, accent):
    draw.rounded_rectangle((x, y, x + size, y + size), radius=8, outline=accent, width=2, fill=(8, 25, 54, 255))
    draw.rectangle((x, y, x + size, y + size * 0.30), fill=accent)
    draw.line((x + size * 0.25, y - 5, x + size * 0.25, y + size * 0.17), fill=(235, 240, 248, 255), width=3)
    draw.line((x + size * 0.75, y - 5, x + size * 0.75, y + size * 0.17), fill=(235, 240, 248, 255), width=3)


def _draw_clock_icon(draw, x, y, size, accent):
    cx = x + size / 2
    cy = y + size / 2
    draw.ellipse((x, y, x + size, y + size), outline=accent, width=3, fill=(8, 25, 54, 255))
    draw.line((cx, cy, cx, y + size * 0.24), fill=(235, 240, 248, 255), width=3)
    draw.line((cx, cy, x + size * 0.72, y + size * 0.64), fill=(235, 240, 248, 255), width=3)



def _row_get(row, key, default=None):
    try:
        return row.get(key, default)
    except AttributeError:
        try:
            value = row[key]
            return value if value is not None else default
        except Exception:
            return default


def _score_label(row) -> tuple[str, str]:
    home_goals = _row_get(row, "home_goals")
    away_goals = _row_get(row, "away_goals")
    status_short = _row_get(row, "status_short")
    status_long = _row_get(row, "status_long")

    if home_goals is None or away_goals is None:
        if status_short in ("NS", "TBD") or not status_short:
            return "VS", "SCHEDULED"
        return "VS", str(status_long or status_short).upper()

    score = f"{home_goals}:{away_goals}"
    if status_short in ("FT", "AET", "PEN"):
        return score, "FULL TIME"
    if status_short in ("1H", "2H", "HT", "ET", "BT", "P", "LIVE"):
        return score, "LIVE"
    return score, str(status_long or status_short or "SCORE").upper()

def build_match_card(row, tz: ZoneInfo) -> str:
    width, height = 1600, 1200
    img = _vertical_gradient((width, height), (6, 17, 38), (3, 8, 22))
    draw = ImageDraw.Draw(img)

    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((-180, 300, 460, 980), fill=(0, 88, 210, 64))
    gd.ellipse((width - 460, 300, width + 180, 980), fill=(210, 35, 60, 58))
    gd.ellipse((620, 380, 980, 850), fill=(245, 185, 40, 30))
    glow = glow.filter(ImageFilter.GaussianBlur(80))
    img.alpha_composite(glow)

    gold = (231, 184, 73, 255)
    gold_soft = (255, 222, 135, 190)
    blue_line = (80, 135, 235, 255)
    red_line = (225, 90, 102, 255)
    white = (242, 245, 250, 255)

    _panel(draw, (26, 26, width - 26, height - 26), (4, 11, 26, 40), gold, radius=42, width=3)
    _panel(draw, (46, 46, width - 46, height - 46), (8, 18, 36, 88), (90, 120, 180, 150), radius=34, width=2)

    _panel(draw, (70, 70, width - 70, 250), (5, 15, 32, 226), (86, 126, 190, 255), radius=28, width=2)
    _draw_simple_trophy(draw, (96, 96, 178, 218), gold)

    title_font = _font(FONT_BOLD, 72)
    info_font = _font(FONT_REGULAR, 32)
    group_font = _font(FONT_BOLD, 34)
    draw.text((210, 92), "WORLD CUP 2026", font=title_font, fill=white)

    kickoff = row["kickoff_utc"].astimezone(tz)
    _panel(draw, (220, 178, 520, 228), (8, 25, 54, 255), (52, 158, 255, 255), radius=16, width=2)
    _panel(draw, (555, 178, 785, 228), (8, 25, 54, 255), (52, 158, 255, 255), radius=16, width=2)
    _draw_calendar_icon(draw, 238, 188, 30, (52, 158, 255, 255))
    _draw_clock_icon(draw, 573, 188, 30, (52, 158, 255, 255))
    draw.text((282, 186), kickoff.strftime("%d.%m.%Y"), font=info_font, fill=white)
    draw.text((618, 186), kickoff.strftime("%H:%M"), font=info_font, fill=white)

    center_label, status_label = _score_label(row)
    if status_label and center_label != "VS":
        status_font = _font(FONT_BOLD, 24)
        status_w = draw.textlength(status_label, font=status_font)
        status_box = (825, 178, 825 + int(status_w) + 44, 228)
        _panel(draw, status_box, (18, 24, 42, 255), gold, radius=16, width=2)
        draw.text((status_box[0] + 22, 190), status_label, font=status_font, fill=gold)

    stage = _safe_group_label(row.get("group_name") or row.get("round_name"))
    stage_w = draw.textlength(stage, font=group_font)
    stage_box = (width - 70 - int(stage_w) - 84, 122, width - 108, 202)
    _panel(draw, stage_box, (18, 24, 42, 255), gold, radius=20, width=2)
    draw.text((stage_box[0] + 34, stage_box[1] + 21), stage, font=group_font, fill=gold)

    draw.line((72, 266, width - 72, 266), fill=gold, width=3)
    draw.line((72, 270, width - 72, 270), fill=(255, 220, 120, 80), width=1)

    _panel(draw, (70, 290, width - 70, 1040), (4, 13, 28, 122), (76, 116, 180, 230), radius=32, width=2)

    mid_x = width // 2
    draw.line((mid_x, 315, mid_x, 1012), fill=(54, 91, 145, 150), width=3)
    draw.ellipse((mid_x - 145, 525 - 145, mid_x + 145, 525 + 145), outline=(54, 91, 145, 150), width=3)
    draw.ellipse((mid_x - 8, 525 - 8, mid_x + 8, 525 + 8), fill=gold)

    for offset in [0, 28, 56, 84]:
        draw.arc((250 - offset, 245 - offset, 805, 910), 292, 348, fill=(75, 135, 255, 115), width=2)
        draw.arc((795, 245 - offset, 1350 + offset, 910), 192, 248, fill=(235, 85, 100, 115), width=2)

    _panel(draw, (105, 460, 650, 885), (8, 18, 38, 188), blue_line, radius=30, width=3)
    _panel(draw, (950, 460, 1495, 885), (8, 18, 38, 188), red_line, radius=30, width=3)

    _draw_flag_image(img, str(row["home_team"]), (138, 500, 617, 775), border_color=(155, 195, 255, 255))
    _draw_flag_image(img, str(row["away_team"]), (983, 500, 1462, 775), border_color=(255, 160, 170, 255))

    left_name = _short(str(row["home_team"])).upper()
    right_name = _short(str(row["away_team"])).upper()
    name_font_left = _fit_text(draw, left_name, 500, 56)
    name_font_right = _fit_text(draw, right_name, 500, 56)
    lw = draw.textlength(left_name, font=name_font_left)
    rw = draw.textlength(right_name, font=name_font_right)
    draw.text((377 - lw / 2, 810), left_name, font=name_font_left, fill=white)
    draw.text((1222 - rw / 2, 810), right_name, font=name_font_right, fill=white)

    medal_size = 220 if center_label != "VS" else 184
    medal = Image.new("RGBA", (medal_size, medal_size), (0, 0, 0, 0))
    md = ImageDraw.Draw(medal)
    md.ellipse((0, 0, medal_size - 1, medal_size - 1), fill=(18, 26, 42, 255), outline=gold, width=6)
    md.ellipse((18, 18, medal_size - 19, medal_size - 19), outline=gold_soft, width=3)
    md.ellipse((46, 46, medal_size - 47, medal_size - 47), outline=(78, 115, 165, 255), width=2)

    center_font_size = 78 if center_label != "VS" else 70
    center_font = _font(FONT_BOLD, center_font_size)
    center_w = md.textlength(center_label, font=center_font)
    md.text((medal_size / 2 - center_w / 2, medal_size / 2 - center_font_size / 2 - 4), center_label, font=center_font, fill=gold)

    if center_label != "VS":
        status_small = status_label[:18]
        status_font = _font(FONT_BOLD, 22)
        status_w = md.textlength(status_small, font=status_font)
        md.text((medal_size / 2 - status_w / 2, medal_size / 2 + 52), status_small, font=status_font, fill=(242, 245, 250, 255))

    img.alpha_composite(medal, (mid_x - medal_size // 2, 525 - medal_size // 2))

    for dx, dy in [(0, -100), (0, 100), (-100, 0), (100, 0)]:
        draw.ellipse((mid_x + dx - 7, 525 + dy - 7, mid_x + dx + 7, 525 + dy + 7), fill=gold)

    venue = str(row.get("venue") or "Venue TBA")
    _panel(draw, (155, 925, 1445, 1010), (7, 18, 38, 235), (76, 116, 180, 255), radius=24, width=2)
    vfont = _font(FONT_REGULAR, 34)
    vbold = _font(FONT_BOLD, 34)
    draw.line((225, 968, 405, 968), fill=gold, width=3)
    draw.line((1195, 968, 1375, 968), fill=gold, width=3)

    label = "STADIUM"
    label_w = draw.textlength(label, font=vbold)
    venue_w = draw.textlength(venue, font=vfont)
    total_w = label_w + 28 + venue_w
    start_x = width / 2 - total_w / 2
    draw.text((start_x, 948), label, font=vbold, fill=white)
    draw.text((start_x + label_w + 28, 948), venue, font=vfont, fill=white)

    draw.line((135, 1120, 655, 1120), fill=gold, width=3)
    draw.line((945, 1120, 1465, 1120), fill=gold, width=3)
    draw.ellipse((752, 1080, 848, 1176), fill=(18, 26, 42, 255), outline=gold, width=3)
    mark_font = _font(FONT_BOLD, 32)
    mark = "WC"
    mw = draw.textlength(mark, font=mark_font)
    draw.text((800 - mw / 2, 1110), mark, font=mark_font, fill=gold)

    temp = Path(tempfile.gettempdir()) / f"match_card_{row['fixture_id']}.png"
    img.convert("RGB").save(temp, format="PNG")
    return str(temp)
