"""Small raster glyphs for the notification area and device list."""

from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw

APP_ICON = Path(__file__).with_name("assets") / "battery.ico"
DIGITS = (
    ("111", "101", "101", "101", "111"), ("010", "110", "010", "010", "111"),
    ("111", "001", "111", "100", "111"), ("111", "001", "111", "001", "111"),
    ("101", "101", "111", "001", "001"), ("111", "100", "111", "001", "111"),
    ("111", "100", "111", "101", "111"), ("111", "001", "010", "010", "010"),
    ("111", "101", "111", "101", "111"), ("111", "101", "111", "001", "111"),
)


def battery_color(level, threshold):
    if level is None:
        return "#929daf"
    if level < threshold:
        return "#f27986"
    if level < max(35, threshold + 8):
        return "#e7ad51"
    return "#49c997"


@lru_cache(maxsize=96)
def render_icon(kind, level=None, threshold=15, show_percent=False):
    image = Image.new("RGBA", (16, 16))
    draw = ImageDraw.Draw(image)
    color = battery_color(level, threshold)
    bottom = 8 if show_percent and level is not None else 14
    if kind == "mouse":
        draw.rounded_rectangle((4, 1, 11, bottom), radius=3, outline=color, width=2)
        draw.line((7, 2, 7, 4), fill=color)
    elif kind == "headset":
        draw.arc((2, 1, 13, 12), 180, 360, fill=color, width=2)
        draw.rectangle((2, 6, 4, bottom), fill=color)
        draw.rectangle((11, 6, 13, bottom), fill=color)
    else:
        top = 1 if bottom == 8 else 3
        draw.rounded_rectangle((1, top, 13, bottom), radius=2, outline=color, width=2)
        draw.line((14, top + 2, 14, bottom - 2), fill=color)
        if level is not None and level > 0:
            draw.rectangle((4, top + 3, 3 + max(1, round(level * 8 / 100)), bottom - 3), fill=color)
    if bottom == 8:
        number = str(level)
        left = (16 - (len(number) * 4 - 1)) // 2
        draw.rounded_rectangle((left - 1, 9, left + len(number) * 4 - 1, 15), 1, fill="#172334")
        for offset, digit in enumerate(number):
            for row, pixels in enumerate(DIGITS[int(digit)]):
                for col, pixel in enumerate(pixels):
                    if pixel == "1":
                        draw.point((left + offset * 4 + col, 10 + row), fill="#ffffff")
    return image.resize((32, 32), Image.Resampling.NEAREST)
