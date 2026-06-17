from pathlib import Path
from zoneinfo import ZoneInfo
import re
import tempfile

from PIL import Image, ImageDraw, ImageFont


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


def _fit_text(draw, text: str, max_width: int, start_size: int, min_size: int = 38):
    size = start_size
    while size >= min_size:
        font = _font(FONT_BOLD, size)
        if draw.textlength(text, font=font) <= max_width:
            return font
        size -= 4
    return _font(FONT_BOLD, min_size)


def _draw_flag_image(img: Image.Image, team_name: str, box: tuple[int, int, int, int]):
    path = ASSETS_DIR / f"{_slug(team_name)}.png"
    x1, y1, x2, y2 = box
    if not path.exists():
        return

    flag = Image.open(path).convert("RGB")
    target_w = x2 - x1
    target_h = y2 - y1
    flag.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)

    fx = x1 + (target_w - flag.width) // 2
    fy = y1 + (target_h - flag.height) // 2
    img.paste(flag, (fx, fy))


def build_match_card(row, tz: ZoneInfo) -> str:
    width, height = 1600, 900
    img = Image.new("RGB", (width, height), (10, 18, 34))
    draw = ImageDraw.Draw(img)

    for y in range(height):
        ratio = y / max(height - 1, 1)
        r = int(10 + 18 * ratio)
        g = int(18 + 35 * ratio)
        b = int(34 + 46 * ratio)
        draw.line((0, y, width, y), fill=(r, g, b))

    draw.rounded_rectangle((60, 60, width - 60, height - 60), radius=42, outline=(255, 255, 255), width=3)
    draw.rounded_rectangle((90, 120, width - 90, height - 120), radius=34, outline=(110, 140, 180), width=2)

    draw.rounded_rectangle((150, 190, width - 150, height - 190), radius=24, outline=(58, 85, 120), width=3)
    draw.line((width // 2, 190, width // 2, height - 190), fill=(58, 85, 120), width=3)
    draw.ellipse((width // 2 - 90, height // 2 - 90, width // 2 + 90, height // 2 + 90), outline=(58, 85, 120), width=3)

    title_font = _font(FONT_BOLD, 38)
    stage_font = _font(FONT_REGULAR, 34)
    meta_font = _font(FONT_REGULAR, 36)
    vs_font = _font(FONT_BOLD, 58)

    kickoff = row["kickoff_utc"].astimezone(tz)
    stage = row["group_name"] or row["round_name"] or "Стадия не указана"

    draw.text((120, 95), "WORLD CUP 2026", font=title_font, fill=(220, 232, 255))
    draw.text((120, 145), kickoff.strftime("%d.%m.%Y  •  %H:%M"), font=stage_font, fill=(176, 196, 225))
    stage_w = draw.textlength(stage, font=stage_font)
    draw.text((width - 120 - stage_w, 95), stage, font=stage_font, fill=(176, 196, 225))

    left_name = _short(str(row["home_team"]))
    right_name = _short(str(row["away_team"]))

    left_box = (140, 265, 690, 675)
    right_box = (910, 265, 1460, 675)
    draw.rounded_rectangle(left_box, radius=28, fill=(19, 45, 88), outline=(86, 130, 200), width=3)
    draw.rounded_rectangle(right_box, radius=28, fill=(88, 34, 34), outline=(219, 116, 116), width=3)

    _draw_flag_image(img, str(row["home_team"]), (210, 315, 620, 500))
    _draw_flag_image(img, str(row["away_team"]), (980, 315, 1390, 500))

    left_font = _fit_text(draw, left_name, 470, 66)
    right_font = _fit_text(draw, right_name, 470, 66)
    left_w = draw.textlength(left_name, font=left_font)
    right_w = draw.textlength(right_name, font=right_font)

    draw.text((415 - left_w / 2, 550), left_name, font=left_font, fill=(255, 255, 255))
    draw.text((1185 - right_w / 2, 550), right_name, font=right_font, fill=(255, 255, 255))

    vs_w = draw.textlength("VS", font=vs_font)
    draw.rounded_rectangle((width // 2 - 85, height // 2 - 58, width // 2 + 85, height // 2 + 58), radius=30, fill=(244, 191, 78))
    draw.text((width // 2 - vs_w / 2, height // 2 - 34), "VS", font=vs_font, fill=(20, 20, 20))

    venue = row.get("venue") or "Стадион уточняется"
    venue_text = f"STADIUM  •  {venue}"
    venue_w = draw.textlength(venue_text, font=meta_font)
    draw.text((width / 2 - venue_w / 2, 760), venue_text, font=meta_font, fill=(220, 232, 255))

    temp = Path(tempfile.gettempdir()) / f"match_card_{row['fixture_id']}.png"
    img.save(temp, format="PNG")
    return str(temp)
