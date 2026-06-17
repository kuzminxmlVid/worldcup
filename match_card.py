from pathlib import Path
from zoneinfo import ZoneInfo
import tempfile

from PIL import Image, ImageDraw, ImageFont

from formatting import TEAM_FLAGS

FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"


def _font(path: str, size: int):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


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


def _draw_flag(draw: ImageDraw.ImageDraw, x: int, y: int, emoji: str):
    if not emoji:
        return
    font = _font(FONT_EMOJI, 92)
    try:
        draw.text((x, y), emoji, font=font, embedded_color=True)
    except Exception:
        draw.text((x, y), emoji, font=_font(FONT_REGULAR, 48), fill=(255, 255, 255))


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

    title_font = _font(FONT_BOLD, 34)
    stage_font = _font(FONT_REGULAR, 28)
    team_font = _font(FONT_BOLD, 68)
    meta_font = _font(FONT_REGULAR, 34)
    vs_font = _font(FONT_BOLD, 54)

    kickoff = row["kickoff_utc"].astimezone(tz)
    stage = row["group_name"] or row["round_name"] or "Стадия не указана"

    draw.text((120, 95), "WORLD CUP 2026", font=title_font, fill=(220, 232, 255))
    draw.text((120, 140), kickoff.strftime("%d.%m.%Y  •  %H:%M"), font=stage_font, fill=(176, 196, 225))
    stage_w = draw.textlength(stage, font=stage_font)
    draw.text((width - 120 - stage_w, 95), stage, font=stage_font, fill=(176, 196, 225))

    left_name = _short(str(row["home_team"]))
    right_name = _short(str(row["away_team"]))
    left_flag = TEAM_FLAGS.get(str(row["home_team"]), "")
    right_flag = TEAM_FLAGS.get(str(row["away_team"]), "")

    left_box = (140, 280, 690, 660)
    right_box = (910, 280, 1460, 660)
    draw.rounded_rectangle(left_box, radius=28, fill=(19, 45, 88), outline=(86, 130, 200), width=3)
    draw.rounded_rectangle(right_box, radius=28, fill=(88, 34, 34), outline=(219, 116, 116), width=3)

    _draw_flag(draw, 180, 320, left_flag)
    _draw_flag(draw, 950, 320, right_flag)

    draw.multiline_text((180, 430), left_name, font=team_font, fill=(255, 255, 255), spacing=6)
    draw.multiline_text((950, 430), right_name, font=team_font, fill=(255, 255, 255), spacing=6)

    vs_w = draw.textlength("VS", font=vs_font)
    draw.rounded_rectangle((width // 2 - 80, height // 2 - 55, width // 2 + 80, height // 2 + 55), radius=28, fill=(244, 191, 78))
    draw.text((width // 2 - vs_w / 2, height // 2 - 32), "VS", font=vs_font, fill=(20, 20, 20))

    venue = row.get("venue") or "Стадион уточняется"
    venue_text = f"🏟  {venue}"
    venue_w = draw.textlength(venue_text, font=meta_font)
    draw.text((width / 2 - venue_w / 2, 760), venue_text, font=meta_font, fill=(220, 232, 255))

    temp = Path(tempfile.gettempdir()) / f"match_card_{row['fixture_id']}.png"
    img.save(temp, format="PNG")
    return str(temp)
