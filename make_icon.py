"""
Converts app_icon_design.png to app_icon.ico with multiple embedded sizes.
Run once before build_exe.bat: python make_icon.py
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

# Pillow ICO: dùng ảnh gốc lớn + sizes param (KHÔNG dùng append_images — đó là cho GIF)
src = Image.open(SRC_PNG).convert("RGBA")

SIZES = [(16,16), (24,24), (32,32), (48,48), (64,64), (128,128), (256,256)]

src.save(str(DST_ICO), format="ICO", sizes=SIZES)

# Verify
from PIL import IcoImagePlugin
with open(DST_ICO, "rb") as f:
    ico = IcoImagePlugin.IcoFile(f)
    actual = sorted(ico.sizes())
print(f"Icon saved -> {DST_ICO}")
print(f"Embedded sizes: {actual}")
