"""
Converts app_icon_design.png to app_icon.ico with multiple embedded sizes.
Run once before build_exe.bat: python make_icon.py

All sizes use the full image resized with LANCZOS — Windows picks the
appropriate embedded size automatically (256 for Explorer, 32 for taskbar, etc.)
"""
from PIL import Image
from pathlib import Path

SRC_PNG = Path("assets/app_icon_design.png")
DST_ICO = Path("assets/app_icon.ico")

if not SRC_PNG.exists():
    pngs = list(Path("assets/icons").rglob("*.png"))
    if pngs:
        SRC_PNG = pngs[0]
    else:
        raise FileNotFoundError("No PNG found. Place app_icon_design.png in assets/")

src = Image.open(SRC_PNG).convert("RGBA")
print(f"Source: {SRC_PNG}  size={src.size}")

SIZES = [256, 128, 64, 48, 32, 24, 16]
images = [src.resize((s, s), Image.LANCZOS) for s in SIZES]

images[0].save(
    str(DST_ICO),
    format="ICO",
    append_images=images[1:],
)

# Verify
from PIL import IcoImagePlugin
with open(DST_ICO, "rb") as f:
    ico = IcoImagePlugin.IcoFile(f)
    actual = sorted(ico.sizes())
print(f"Icon saved -> {DST_ICO}")
print(f"Embedded sizes: {actual}")
