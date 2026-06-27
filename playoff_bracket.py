from __future__ import annotations

from pathlib import Path
from zoneinfo import ZoneInfo
import math
import tempfile
from collections import OrderedDict

from PIL import Image, ImageDraw, ImageFont, ImageFilter


ASSETS_DIR = Path(__file__).with_name("assets")
FONTS_DIR = ASSETS_DIR / "fonts"
FONT_REGULAR = FONTS_DIR / "DejaVuSans.ttf"
FONT_BOLD = FONTS_DIR / "DejaVuSans-Bold.ttf"


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


def _row_get(row, key: str, default=None):
    try:
        value = row.get(key, default)
        return default if value is None else value
    except AttributeError:
        try:
            value = row[key]
            return default if value is None else value
        except Exception:
            return default


def _vertical_gradient(size, top_rgb, bottom_rgb):
    w, h = size
    img = Image.new("RGBA", size)
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(h - 1, 1)
        r = int(top_rgb[0] * (1 - t) + bottom_rgb[0] * t)
        g = int(top_rgb[1] * (1 - t) + bottom_rgb[1] * t)
        b = int(top_rgb[2] * (1 - t) + bottom_rgb[2] * t)
        draw.line((0, y, w, y), fill=(r, g, b, 255))
    return img


def _panel(draw, box, fill, outline, radius=24, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _fit_text(draw, text: str, max_width: int, start_size: int, min_size: int = 16, bold: bool = True):
    size = start_size
    font_path = FONT_BOLD if bold else FONT_REGULAR
    while size >= min_size:
        font = _font(font_path, size)
        if draw.textlength(text, font=font) <= max_width:
            return font
        size -= 1
    return _font(font_path, min_size)


def _stage_key(row) -> tuple[int, str]:
    name = str(_row_get(row, "round_name", "") or "").lower()
    kickoff = _row_get(row, "kickoff_utc")

    if "1/16" in name or "round of 32" in name:
        return 1, "1/16 финала"
    if "1/8" in name or "round of 16" in name:
        return 2, "1/8 финала"
    if "1/4" in name or "quarter" in name:
        return 3, "1/4 финала"
    if "1/2" in name or "semi" in name:
        return 4, "1/2 финала"
    if ("3" in name and "мест" in name) or "third" in name:
        return 6, "Матч за 3-е место"
    if "финал" in name or "final" in name:
        return 5, "Финал"

    # Date fallback for ESPN if round_name is weak or absent.
    if kickoff:
        day = kickoff.date()
        if day <= day.replace(year=2026, month=7, day=1):
            return 1, "1/16 финала"
        if day <= day.replace(year=2026, month=7, day=7):
            return 2, "1/8 финала"
        if day <= day.replace(year=2026, month=7, day=12):
            return 3, "1/4 финала"
        if day <= day.replace(year=2026, month=7, day=15):
            return 4, "1/2 финала"
        if day <= day.replace(year=2026, month=7, day=18):
            return 5, "Финал"

    return 99, _row_get(row, "round_name", "Плей-офф") or "Плей-офф"


def _group_rows(rows):
    grouped = OrderedDict()
    for row in sorted(rows, key=lambda r: _row_get(r, "kickoff_utc")):
        key, label = _stage_key(row)
        if key == 6:
            # Draw third-place match separately.
            grouped.setdefault((key, label), []).append(row)
        else:
            grouped.setdefault((key, label), []).append(row)
    return grouped


def _match_label(row, tz: ZoneInfo):
    home = str(_row_get(row, "home_team", "TBD"))
    away = str(_row_get(row, "away_team", "TBD"))
    kickoff = _row_get(row, "kickoff_utc")
    date_line = kickoff.astimezone(tz).strftime("%d.%m • %H:%M") if kickoff else "Дата уточняется"

    hg = _row_get(row, "home_goals")
    ag = _row_get(row, "away_goals")
    if hg is not None and ag is not None:
        title = f"{home} {hg}:{ag} {away}"
    else:
        title = f"{home} — {away}"

    return title, date_line


def _draw_match_box(img, box, row, tz, accent, muted, gold):
    draw = ImageDraw.Draw(img)
    x1, y1, x2, y2 = box
    _panel(draw, box, (7, 20, 45, 232), accent, radius=16, width=2)

    title, date_line = _match_label(row, tz)
    title_font = _fit_text(draw, title, x2 - x1 - 28, 24, 14, bold=True)
    date_font = _font(FONT_REGULAR, 17)

    draw.text((x1 + 14, y1 + 11), title, font=title_font, fill=(242, 245, 250, 255))
    draw.text((x1 + 14, y1 + 43), date_line, font=date_font, fill=(195, 210, 232, 255))

    fixture_id = _row_get(row, "fixture_id")
    if fixture_id is not None:
        link = f"/match_{fixture_id}"
        link_font = _font(FONT_REGULAR, 14)
        lw = draw.textlength(link, font=link_font)
        draw.text((x2 - lw - 14, y2 - 22), link, font=link_font, fill=gold)


def _draw_connector(draw, left_box, right_box, color):
    lx = left_box[2]
    ly = (left_box[1] + left_box[3]) / 2
    rx = right_box[0]
    ry = (right_box[1] + right_box[3]) / 2
    mid = (lx + rx) / 2
    draw.line((lx, ly, mid, ly), fill=color, width=2)
    draw.line((mid, ly, mid, ry), fill=color, width=2)
    draw.line((mid, ry, rx, ry), fill=color, width=2)


def build_playoff_bracket(rows, tz: ZoneInfo) -> str:
    rows = list(rows or [])

    width, height = 1800, 1200
    img = _vertical_gradient((width, height), (5, 14, 32), (2, 7, 18))
    draw = ImageDraw.Draw(img)

    gold = (232, 185, 75, 255)
    blue = (90, 155, 245, 255)
    blue_soft = (80, 125, 190, 210)
    red_soft = (220, 85, 100, 210)
    white = (242, 246, 252, 255)
    muted = (180, 195, 220, 255)

    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((-220, 200, 540, 1100), fill=(0, 90, 220, 54))
    gd.ellipse((width - 540, 200, width + 220, 1100), fill=(210, 45, 80, 42))
    gd.ellipse((680, 220, 1120, 760), fill=(232, 185, 75, 34))
    glow = glow.filter(ImageFilter.GaussianBlur(90))
    img.alpha_composite(glow)

    _panel(draw, (24, 24, width - 24, height - 24), (5, 13, 29, 70), gold, radius=38, width=3)
    _panel(draw, (48, 48, width - 48, 165), (7, 18, 40, 230), blue_soft, radius=28, width=2)

    title_font = _font(FONT_BOLD, 72)
    sub_font = _font(FONT_REGULAR, 30)
    title = "Плей-офф ЧМ 2026"
    tw = draw.textlength(title, font=title_font)
    draw.text((width / 2 - tw / 2, 55), title, font=title_font, fill=white)

    subtitle = "Актуальная сетка на момент запроса"
    sw = draw.textlength(subtitle, font=sub_font)
    draw.text((width / 2 - sw / 2, 125), subtitle, font=sub_font, fill=muted)
    draw.line((360, 142, 650, 142), fill=gold, width=2)
    draw.line((1150, 142, 1440, 142), fill=gold, width=2)

    if not rows:
        msg_font = _font(FONT_BOLD, 40)
        small_font = _font(FONT_REGULAR, 26)
        msg = "Матчей плей-офф пока нет в базе"
        mw = draw.textlength(msg, font=msg_font)
        draw.text((width / 2 - mw / 2, 515), msg, font=msg_font, fill=white)

        small = "Нажми /sync позже: пары появятся, когда внешний источник опубликует их."
        sw = draw.textlength(small, font=small_font)
        draw.text((width / 2 - sw / 2, 575), small, font=small_font, fill=muted)

        out = Path(tempfile.gettempdir()) / "worldcup_playoff_bracket.png"
        img.convert("RGB").save(out, format="PNG")
        return str(out)

    grouped = _group_rows(rows)
    third_place = []
    stages = []
    for (key, label), items in grouped.items():
        if key == 6:
            third_place.extend(items)
        elif key != 99:
            stages.append((key, label, items))
    stages.sort(key=lambda item: item[0])

    # 2026 knockout has 5 main columns: R32, R16, QF, SF, Final.
    stage_labels = {
        1: "1/16 финала",
        2: "1/8 финала",
        3: "1/4 финала",
        4: "1/2 финала",
        5: "Финал",
    }
    stage_rows = {key: [] for key in stage_labels}
    for key, label, items in stages:
        stage_rows.setdefault(key, []).extend(items)

    col_x = {
        1: 60,
        2: 410,
        3: 760,
        4: 1110,
        5: 1450,
    }
    box_w = 290
    box_h = 72
    top_y = 230
    bottom_y = 965

    boxes_by_stage = {}

    for key in [1, 2, 3, 4, 5]:
        label = stage_labels[key]
        x = col_x[key]
        label_font = _font(FONT_BOLD, 22)
        _panel(draw, (x, 190, x + box_w, 230), (15, 35, 70, 238), blue_soft, radius=18, width=2)
        lw = draw.textlength(label, font=label_font)
        draw.text((x + box_w / 2 - lw / 2, 198), label, font=label_font, fill=white)

        items = stage_rows.get(key, [])
        count = max(1, len(items))
        available = bottom_y - top_y
        gap = available / count

        boxes = []
        for idx, row in enumerate(items):
            cy = top_y + gap * idx + gap / 2
            y1 = int(cy - box_h / 2)
            box = (x, y1, x + box_w, y1 + box_h)
            accent = gold if key == 5 else blue_soft
            _draw_match_box(img, box, row, tz, accent, muted, gold)
            boxes.append(box)

        boxes_by_stage[key] = boxes

    # Draw approximate connectors by pairing adjacent stages.
    for key in [1, 2, 3, 4]:
        left = boxes_by_stage.get(key, [])
        right = boxes_by_stage.get(key + 1, [])
        if not left or not right:
            continue
        for idx, lbox in enumerate(left):
            rbox = right[min(idx // 2, len(right) - 1)]
            _draw_connector(draw, lbox, rbox, gold if key >= 3 else (95, 155, 245, 180))

    if third_place:
        row = sorted(third_place, key=lambda r: _row_get(r, "kickoff_utc"))[0]
        heading = "Матч за 3-е место"
        hf = _font(FONT_BOLD, 26)
        hw = draw.textlength(heading, font=hf)
        draw.text((width / 2 - hw / 2, 1020), heading, font=hf, fill=gold)
        _draw_match_box(img, (width // 2 - 220, 1058, width // 2 + 220, 1135), row, tz, blue_soft, muted, gold)

    footer = "Пары и счёт обновляются из внешнего источника при /sync"
    ff = _font(FONT_REGULAR, 22)
    fw = draw.textlength(footer, font=ff)
    draw.text((width / 2 - fw / 2, height - 52), footer, font=ff, fill=muted)

    out = Path(tempfile.gettempdir()) / "worldcup_playoff_bracket.png"
    img.convert("RGB").save(out, format="PNG")
    return str(out)
