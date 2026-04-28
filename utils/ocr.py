import logging
import os
import re
from pathlib import Path
import cv2
import numpy as np

logger = logging.getLogger(__name__)

def _get_tesseract_cmd() -> str:
    """Return the best available tesseract_cmd path, evaluated lazily."""
    # 1. Explicit env override (set by _setup_tesseract in gui_app or .env)
    env = os.getenv('TESSERACT_CMD')
    if env and Path(env).exists():
        return env
    # 2. Whatever pytesseract already has configured (may have been set by gui_app._setup_tesseract)
    try:
        import pytesseract as _pt
        if _pt.pytesseract.tesseract_cmd and Path(_pt.pytesseract.tesseract_cmd).exists():
            return _pt.pytesseract.tesseract_cmd
    except Exception:
        pass
    # 3. Known installation paths (system-wide and user-local)
    _candidates = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        str(Path.home() / r'AppData\Local\Programs\Tesseract-OCR\tesseract.exe'),
    ]
    for c in _candidates:
        if Path(c).exists():
            return c
    # 4. Last resort: search bundled _internal directories (dev env)
    import glob as _glob
    for root in [Path.home() / 'Downloads', Path.home() / 'Desktop']:
        hits = sorted(_glob.glob(str(root / '*' / '_internal' / 'Tesseract-OCR' / 'tesseract.exe')),
                      key=os.path.getmtime, reverse=True)
        if hits:
            return hits[0]
    return r'C:\Program Files\Tesseract-OCR\tesseract.exe'


def ocr_image(path, scale: float = 3.0):
    """Run OCR on image path with preprocessing. Returns text or None."""
    try:
        import pytesseract
        from PIL import Image
        pytesseract.pytesseract.tesseract_cmd = _get_tesseract_cmd()
        easyocr_reader = None
    except Exception:
        pytesseract = None
        try:
            import easyocr
            easyocr_reader = easyocr.Reader(['en', 'vie', 'vi'], gpu=False)
        except Exception:
            easyocr_reader = None

    p = Path(path)
    if not p.exists():
        return None
    try:
        img = cv2.imread(str(p))
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        proc_path = p.parent / f'proc_{p.stem}.png'
        cv2.imwrite(str(proc_path), th)

        text = None
        if pytesseract:
            try:
                text = pytesseract.image_to_string(Image.open(str(proc_path)), config='--psm 6 --oem 3 -l vie+eng')
            except Exception:
                logger.debug('pytesseract failed', exc_info=True)
        if text is None and easyocr_reader:
            try:
                texts = easyocr_reader.readtext(str(proc_path), detail=0)
                text = '\n'.join(texts) if texts else None
            except Exception:
                logger.debug('easyocr failed', exc_info=True)

        # remove intermediate proc file if input was itself a proc_* file
        try:
            if p.stem.startswith('proc_'):
                proc_path.unlink(missing_ok=True)
        except Exception:
            logger.debug('failed to remove intermediate proc file: %s', proc_path)

        return text
    except Exception:
        logger.debug('ocr_image processing failed', exc_info=True)
    return None


def ocr_image_variants(path, scales=(3.0, 1.5, 4.0)):
    """Run OCR using multiple preprocessing scales and return a mapping scale->text (or None).

    This does not choose among results; caller can use these variants when validation
    of the primary OCR result fails.
    """
    results = {}
    for s in scales:
        try:
            results[float(s)] = ocr_image(path, scale=float(s))
        except Exception:
            logger.debug('ocr_image failed for scale %s', s, exc_info=True)
            results[float(s)] = None
    return results


def ocr_image_first_success(path, scales=(3.0, 1.5, 4.0)):
    """Try OCR at each scale and return the first non-empty result and its scale.

    Returns a tuple (text, scale) where text is None if nothing succeeded.
    """
    variants = ocr_image_variants(path, scales=scales)
    for s in scales:
        txt = variants.get(float(s))
        if txt:
            return txt, float(s)
    return None, None

