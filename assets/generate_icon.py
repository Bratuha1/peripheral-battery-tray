"""Generate the application icon from its original vector-like geometry."""

from pathlib import Path

from PIL import Image, ImageDraw

image = Image.new("RGBA", (256, 256))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((8, 8, 247, 247), radius=57, fill="#193456")
draw.rounded_rectangle((40, 71, 200, 184), radius=24, outline="#d8edff", width=14)
draw.rounded_rectangle((206, 107, 220, 148), radius=5, fill="#d8edff")
draw.polygon(((126, 91), (88, 136), (115, 136), (108, 165), (153, 118), (124, 118)),
             fill="#57dfab")
image.save(Path(__file__).with_name("battery.ico"), sizes=[(n, n) for n in (16, 24, 32, 48, 64, 128, 256)])
