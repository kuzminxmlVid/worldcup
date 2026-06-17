from pathlib import Path
from zoneinfo import ZoneInfo
import re
import tempfile
import urllib.request
import urllib.error

from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

LOCAL_FLAGS_DIR = Path(__file__).with_name("assets") / "flags"
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


def _font(path: str, size: int):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        try:
            return ImageFont.load_default(size=size)
        except TypeError:
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


def _fit_text(draw, text: str, max_width: int, start_size: int, min_size: int = 32):
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
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "worldcup-telegram-bot/1.0"},
                )
                with urllib.request.urlopen(req, timeout=8) as response:
                    data = response.read()

                if len(data) > 1000:
                    cache_path.write_bytes(data)
                    return cache_path
            except (urllib.error.URLError, TimeoutError, OSError):
                continue

    return None


def _flag_path(team_name: str) -> Path | None:
    # Сначала пробуем нормальный флаг из CDN-кэша.
    downloaded = _download_flag(team_name)
    if downloaded:
        return downloaded

    # Если Railway/сеть временно тупит, используем локальный fallback из assets/flags.
    return _local_flag_path(team_name)


def _draw_flag_image(img: Image.Image, team_name: str, box: tuple[int, int, int, int]):
    path = _flag_path(team_name)

    x1, y1, x2, y2 = box
    target_w = x2 - x1
    target_h = y2 - y1

    # shadow
    shadow = Image.new("RGBA", (target_w + 24, target_h + 24), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((12, 12, target_w + 12, target_h + 12), radius=18, fill=(0, 0, 0, 140))
    shadow = shadow.filter(ImageFilter.GaussianBlur(10))
    img.alpha_composite(shadow, (x1 - 12, y1 - 12))

    flag_canvas = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    mask = Image.new("L", (target_w, target_h), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((0, 0, target_w, target_h), radius=18, fill=255)

    if path and path.exists():
        flag = Image.open(path)
        flag = _crop_cover(flag, target_w, target_h).convert("RGBA")
        flag_canvas.alpha_composite(flag)
        flag_canvas.putalpha(mask)
    else:
        d = ImageDraw.Draw(flag_canvas)
        d.rounded_rectangle((0, 0, target_w, target_h), radius=18, fill=(35, 45, 65, 255))
        initials = "".join(word[0] for word in team_name.split()[:2]).upper()
        f = _font(FONT_BOLD, 50)
        tw = d.textlength(initials, font=f)
        d.text(((target_w - tw) / 2, target_h / 2 - 28), initials, font=f, fill=(255, 255, 255, 255))
        flag_canvas.putalpha(mask)

    img.alpha_composite(flag_canvas, (x1, y1))

    d = ImageDraw.Draw(img)
    d.rounded_rectangle((x1, y1, x2, y2), radius=18, outline=(235, 240, 248, 230), width=3)


def _panel(draw: ImageDraw.ImageDraw, box, fill, outline, radius=28, width=3):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def build_match_card(row, tz: ZoneInfo) -> str:
    width, height = 1600, 900
    img = Image.new("RGBA", (width, height), (10, 18, 34, 255))
    draw = ImageDraw.Draw(img)

    for y in range(height):
        ratio = y / max(height - 1, 1)
        r = int(8 + 22 * ratio)
        g = int(16 + 28 * ratio)
        b = int(34 + 52 * ratio)
        draw.line((0, y, width, y), fill=(r, g, b, 255))

    _panel(draw, (55, 55, width - 55, height - 55), (20, 36, 60, 120), (247, 247, 245, 255), radius=42, width=3)

    title_font = _font(FONT_BOLD, 38)
    info_font = _font(FONT_REGULAR, 30)
    stage_font = _font(FONT_BOLD, 28)
    vs_font = _font(FONT_BOLD, 52)
    venue_font = _font(FONT_REGULAR, 30)

    kickoff = row["kickoff_utc"].astimezone(tz)
    stage = _safe_group_label(row.get("group_name") or row.get("round_name"))

    _panel(draw, (95, 95, 1505, 185), (8, 22, 42, 210), (96, 130, 180, 255), radius=24, width=2)
    draw.text((125, 112), "WORLD CUP 2026", font=title_font, fill=(235, 240, 248, 255))
    draw.text((125, 148), kickoff.strftime("%d.%m.%Y   %H:%M"), font=info_font, fill=(195, 208, 228, 255))

    stage_w = draw.textlength(stage, font=stage_font)
    badge_w = int(stage_w + 56)
    _panel(draw, (1505 - badge_w - 24, 112, 1505 - 24, 166), (33, 54, 84, 255), (120, 155, 210, 255), radius=18, width=2)
    draw.text((1505 - badge_w - 24 + 28, 126), stage, font=stage_font, fill=(232, 240, 250, 255))

    _panel(draw, (110, 215, 1490, 785), (15, 33, 56, 120), (86, 120, 170, 255), radius=30, width=2)
    draw.line((800, 255, 800, 745), fill=(62, 90, 128, 255), width=3)
    draw.ellipse((710, 420, 890, 600), outline=(62, 90, 128, 255), width=3)

    left_box = (140, 265, 690, 675)
    right_box = (910, 265, 1460, 675)
    _panel(draw, left_box, (27, 52, 103, 255), (120, 160, 225, 255), radius=28, width=3)
    _panel(draw, right_box, (114, 37, 37, 255), (230, 130, 130, 255), radius=28, width=3)

    _draw_flag_image(img, str(row["home_team"]), (205, 315, 625, 505))
    _draw_flag_image(img, str(row["away_team"]), (975, 315, 1395, 505))

    left_name = _short(str(row["home_team"]))
    right_name = _short(str(row["away_team"]))
    team_font_left = _fit_text(draw, left_name, 470, 68)
    team_font_right = _fit_text(draw, right_name, 470, 68)
    left_w = draw.textlength(left_name, font=team_font_left)
    right_w = draw.textlength(right_name, font=team_font_right)
    draw.text((415 - left_w / 2, 560), left_name, font=team_font_left, fill=(255, 255, 255, 255))
    draw.text((1185 - right_w / 2, 560), right_name, font=team_font_right, fill=(255, 255, 255, 255))

    _panel(draw, (720, 450, 880, 560), (244, 191, 78, 255), (255, 224, 140, 255), radius=28, width=2)
    vs_w = draw.textlength("VS", font=vs_font)
    draw.text((800 - vs_w / 2, 479), "VS", font=vs_font, fill=(25, 25, 25, 255))

    venue = str(row.get("venue") or "Venue TBA")
    venue_text = f"STADIUM  •  {venue}"
    _panel(draw, (350, 805, 1250, 855), (8, 22, 42, 220), (96, 130, 180, 255), radius=22, width=2)
    venue_w = draw.textlength(venue_text, font=venue_font)
    draw.text((800 - venue_w / 2, 818), venue_text, font=venue_font, fill=(220, 232, 245, 255))

    temp = Path(tempfile.gettempdir()) / f"match_card_{row['fixture_id']}.png"
    img.convert("RGB").save(temp, format="PNG")
    return str(temp)
