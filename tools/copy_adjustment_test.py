import re

import cv2
from pathlib import Path
import time
import logging
from PIL import Image

DEBUG_DIR = Path(__file__).resolve().parents[1] / 'assets' / 'debug_matches'
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)


def ocr_image(path: str):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    img = cv2.imread(str(path))
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # upscale
    gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    # CLAHE for contrast
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
    gray = clahe.apply(gray)
    # bilateral filter to reduce noise while keeping edges
    gray = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)
    # unsharp mask
    blur = cv2.GaussianBlur(gray, (0,0), sigmaX=3)
    sharp = cv2.addWeighted(gray, 1.5, blur, -0.5, 0)
    # adaptive threshold / Otsu
    _, th = cv2.threshold(sharp, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    proc_path = DEBUG_DIR / f'proc_{path.stem}_{int(time.time())}.png'
    cv2.imwrite(str(proc_path), th)

    # try pytesseract first
    try:
        import pytesseract
        from pytesseract import pytesseract as _pyt
        _pyt.tesseract_cmd = r"C:\Users\hang.truong\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
        try:
            # general OCR
            text = pytesseract.image_to_string(Image.open(str(proc_path)), config='--psm 6 --oem 3')
            # additional amount-focused OCR pass with whitelist and single-line psm
            amount_cfg = "--psm 7 --oem 3 -c tessedit_char_whitelist=0123456789.,-₫"
            try:
                amt_text = pytesseract.image_to_string(Image.open(str(proc_path)), config=amount_cfg)
                # if amount_pass finds currency symbols, append it so downstream parsing can use it
                if any(c in amt_text for c in ('₫', 'đ')) or any(ch.isdigit() for ch in amt_text):
                    text = text + "\n" + amt_text
            except Exception:
                pass
            return text
        except Exception as e:
            # fall through to try subprocess call below
            pass
    except Exception as e:
        logger.debug('pytesseract failed: %s', e)

    # fallback easyocr
    try:
        import easyocr
        reader = easyocr.Reader(['en', 'vi'], gpu=False)
        texts = reader.readtext(str(proc_path), detail=0)
        return '\n'.join(texts)
    except Exception as e:
        logger.debug('easyocr failed: %s', e)
        # final fallback: try calling tesseract binary via subprocess (handles quoted path)
        try:
            import subprocess
            tesseract_bin = r"C:\Users\hang.truong\AppData\Local\Programs\Tesseract-OCR\tesseract"
            out_txt = str(proc_path) + '_tess_out'
            # use list form to avoid shell parsing issues
            cmd = [tesseract_bin, str(proc_path), out_txt, '-l', 'vie']
            subprocess.run(cmd, check=True)
            # read output
            with open(out_txt + '.txt', 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e2:
            logger.debug('subprocess tesseract failed: %s', e2)
            return None


def run(image_path: str):
    txt = ocr_image(image_path)
    # Post-process: map amounts to preceding labels and fix leading 9/4 -> ₫ for money labels
    if txt:
        lines = [l.strip() for l in txt.splitlines() if l.strip()]
        amt_re = re.compile(r"^-?\s*[₫đ]?\s*-?\d+[\d\.\s]*$")
        money_k = re.compile(r"refund|shipping|voucher|commission|service|adjustment", re.IGNORECASE)
        out_lines = []
        last_label_idx = None
        for line in lines:
            if amt_re.match(line):
                if last_label_idx is not None:
                    # apply heuristic fix if necessary
                    if money_k.search(out_lines[last_label_idx]):
                        t = line.strip()
                        if t and (t[0] == '9' or t[0] == '4') and not ('₫' in t or 'đ' in t):
                            t = '₫' + t[1:]
                        out_lines[last_label_idx] = f"{out_lines[last_label_idx]} {t}"
                    else:
                        out_lines[last_label_idx] = f"{out_lines[last_label_idx]} {line}"
                else:
                    out_lines.append(line)
            else:
                out_lines.append(line)
                last_label_idx = len(out_lines) - 1
        txt = "\n".join(out_lines)

    # apply currency text fix from user: convert leading 4 -> đ where appropriate
    def fix_currency_text(text: str) -> str:
        text = re.sub(r"(?<!\w)-4(\d{1,3}\.\d{3})", r"-đ\1", text)
        text = re.sub(r"(?<!\w)4(\d{1,3}\.\d{3})", r"đ\1", text)
        return text

    if txt:
        txt = fix_currency_text(txt)
    out = DEBUG_DIR / 'copy_adjustment_test_output.txt'
    out.write_text(txt or '', encoding='utf-8')
    print('Wrote', out)
    print('--- preview ---')
    print(txt)


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print('Usage: python tools/copy_adjustment_test.py <image-path>')
        raise SystemExit(2)
    run(sys.argv[1])
