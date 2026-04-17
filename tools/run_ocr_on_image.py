from pathlib import Path
import sys
import pathlib as _pl

# Ensure repository root is on sys.path so `tools` package imports work when run as script
repo_root = _pl.Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from tools.ocr_common import ocr_image_and_write


def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/run_ocr_on_image.py <image_path> [out_path]")
        return 2
    img = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else 'assets/debug_matches/ocr_text_cleaned.txt'
    cleaned = ocr_image_and_write(img, out)
    print('Wrote cleaned OCR to', out)
    print('--- preview ---')
    print(cleaned)


if __name__ == '__main__':
    raise SystemExit(main())
