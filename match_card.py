from pathlib import Path
from zoneinfo import ZoneInfo
import math
import re
import tempfile

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

ASSETS_DIR = Path(__file__).with_name("assets") / "flags"


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
    m = re.search(r'([A-L])$', str(value))
    if 'Группа' in str(value) and m:
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


def _wave_flag(flag: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Pseudo waving flag, visually closer to a fabric banner.
    It uses column-wise vertical displacement, variable column scaling,
    directional shading and a soft shadow so the result looks like the sample reference.
    """
    src = flag.convert('RGBA')
    src_ratio = src.width / max(src.height, 1)

    inner_w = int(target_w * 0.90)
    inner_h = min(int(inner_w / src_ratio), int(target_h * 0.78))
    if inner_h <= 0:
        inner_h = max(1, int(target_h * 0.7))
    src = src.resize((inner_w, inner_h), Image.Resampling.LANCZOS)

    result = Image.new('RGBA', (target_w, target_h), (0, 0, 0, 0))
    shadow = Image.new('RGBA', (target_w, target_h), (0, 0, 0, 0))

    ox = (target_w - inner_w) // 2
    oy = (target_h - inner_h) // 2

    period = max(90, inner_w // 3)
    amp_y = max(10, target_h // 18)
    stretch = 0.09

    for x in range(src.width):
        phase = (x / period) * math.tau
        y_shift = math.sin(phase) * amp_y
        scale = 1.0 + math.sin(phase + 0.35) * stretch
        brightness = 0.84 + 0.22 * ((math.cos(phase - 0.15) + 1) / 2)

        col = src.crop((x, 0, x + 1, src.height))
        new_h = max(1, int(src.height * scale))
        col = col.resize((1, new_h), Image.Resampling.BICUBIC)
        col = ImageEnhance.Brightness(col).enhance(brightness)

        dy = oy + int(y_shift) - (new_h - src.height) // 2
        dx = ox + x

        # soft shadow behind the fabric
        sh = col.copy()
        shadow.alpha_composite(sh, (dx + 8, dy + 12))
        result.alpha_composite(col, (dx, dy))

    shadow = shadow.filter(ImageFilter.GaussianBlur(10))

    # rounded clipping mask, so edges look cleaner on the card
    mask = Image.new('L', (target_w, target_h), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((18, 14, target_w - 18, target_h - 14), radius=16, fill=255)

    combined = Image.new('RGBA', (target_w, target_h), (0, 0, 0, 0))
    combined.alpha_composite(shadow)
    combined.alpha_composite(result)
    combined.putalpha(mask)

    # cloth gloss at the top
    gloss = Image.new('RGBA', (target_w, target_h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(gloss)
    for i in range(10):
        alpha = max(0, 38 - i * 3)
        gd.rounded_rectangle((16 + i, 14 + i, target_w - 16 - i, target_h * 0.32 + i), radius=18, outline=(255, 255, 255, alpha), width=1)
    combined.alpha_composite(gloss)

    return combined


def _draw_flag_image(img: Image.Image, team_name: str, box: tuple[int, int, int, int]):
    path = ASSETS_DIR / f"{_slug(team_name)}.png"
    x1, y1, x2, y2 = box
    target_w = x2 - x1
    target_h = y2 - y1
    area = Image.new('RGBA', (target_w, target_h), (0, 0, 0, 0))

    # backdrop panel to make the flag stand out and hide any missing content nicely
    d = ImageDraw.Draw(area)
    d.rounded_rectangle((8, 8, target_w - 8, target_h - 8), radius=20, fill=(7, 18, 34, 70), outline=(220, 228, 238, 80), width=2)

    if path.exists():
        flag = Image.open(path)
        waved = _wave_flag(flag, target_w - 16, target_h - 16)
        area.alpha_composite(waved, (8, 8))
    else:
        initials = ''.join(word[0] for word in team_name.split()[:2]).upper()
        f = _font(FONT_BOLD, 44)
        tw = d.textlength(initials, font=f)
        d.text(((target_w - tw) / 2, target_h / 2 - 24), initials, font=f, fill=(255, 255, 255, 255))

    img.alpha_composite(area, (x1, y1))


def _panel(draw: ImageDraw.ImageDraw, box, fill, outline, radius=28, width=3):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def build_match_card(row, tz: ZoneInfo) -> str:
    width, height = 1600, 900
    img = Image.new('RGBA', (width, height), (10, 18, 34, 255))
    draw = ImageDraw.Draw(img)

    # smooth background gradient
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

    kickoff = row['kickoff_utc'].astimezone(tz)
    stage = _safe_group_label(row.get('group_name') or row.get('round_name'))

    _panel(draw, (95, 95, 1505, 185), (8, 22, 42, 210), (96, 130, 180, 255), radius=24, width=2)
    draw.text((125, 112), 'WORLD CUP 2026', font=title_font, fill=(235, 240, 248, 255))
    draw.text((125, 148), kickoff.strftime('%d.%m.%Y   %H:%M'), font=info_font, fill=(195, 208, 228, 255))

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

    _draw_flag_image(img, str(row['home_team']), (172, 305, 658, 498))
    _draw_flag_image(img, str(row['away_team']), (942, 305, 1428, 498))

    left_name = _short(str(row['home_team']))
    right_name = _short(str(row['away_team']))
    team_font_left = _fit_text(draw, left_name, 470, 68)
    team_font_right = _fit_text(draw, right_name, 470, 68)
    left_w = draw.textlength(left_name, font=team_font_left)
    right_w = draw.textlength(right_name, font=team_font_right)
    draw.text((415 - left_w / 2, 556), left_name, font=team_font_left, fill=(255, 255, 255, 255))
    draw.text((1185 - right_w / 2, 556), right_name, font=team_font_right, fill=(255, 255, 255, 255))

    _panel(draw, (720, 450, 880, 560), (244, 191, 78, 255), (255, 224, 140, 255), radius=28, width=2)
    vs_w = draw.textlength('VS', font=vs_font)
    draw.text((800 - vs_w / 2, 479), 'VS', font=vs_font, fill=(25, 25, 25, 255))

    venue = str(row.get('venue') or 'Venue TBA')
    venue_text = f'STADIUM  •  {venue}'
    _panel(draw, (350, 805, 1250, 855), (8, 22, 42, 220), (96, 130, 180, 255), radius=22, width=2)
    venue_w = draw.textlength(venue_text, font=venue_font)
    draw.text((800 - venue_w / 2, 818), venue_text, font=venue_font, fill=(220, 232, 245, 255))

    temp = Path(tempfile.gettempdir()) / f"match_card_{row['fixture_id']}.png"
    img.convert('RGB').save(temp, format='PNG')
    return str(temp)
