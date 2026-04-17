from PIL import Image
from pathlib import Path
import sys


def zoom_image(in_path: str, out_path: str = None, factor: float = 2.0):
    p = Path(in_path)
    if not p.exists():
        raise FileNotFoundError(in_path)
    img = Image.open(in_path)
    w, h = img.size
    nw, nh = int(w * factor), int(h * factor)
    img2 = img.resize((nw, nh), resample=Image.BICUBIC)
    if out_path is None:
        out_path = p.parent / f'{p.stem}_x{int(factor)}{p.suffix}'
    out_path = Path(out_path)
    img2.save(out_path)
    print('Saved', out_path)
    return str(out_path)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python tools/zoom_image.py <input> [factor] [out_path]')
        raise SystemExit(2)
    inp = sys.argv[1]
    factor = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
    out = sys.argv[3] if len(sys.argv) > 3 else None
    zoom_image(inp, out, factor)
