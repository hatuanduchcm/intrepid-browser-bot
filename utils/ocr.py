import logging
from pathlib import Path
import cv2

logger = logging.getLogger(__name__)


def ocr_image(path, tesseract_cmd=r"C:\Program Files\Tesseract-OCR\tesseract.exe"):
    """Run OCR on image path with preprocessing. Returns text or None."""
    try:
        import pytesseract
        from PIL import Image
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
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
        gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        proc_path = p.parent / f'proc_{p.stem}.png'
        cv2.imwrite(str(proc_path), th)
        if pytesseract:
            try:
                return pytesseract.image_to_string(Image.open(str(proc_path)), config='--psm 6 --oem 3')
            except Exception:
                logger.debug('pytesseract failed', exc_info=True)
        if easyocr_reader:
            try:
                texts = easyocr_reader.readtext(str(proc_path), detail=0)
                return '\n'.join(texts) if texts else None
            except Exception:
                logger.debug('easyocr failed', exc_info=True)
    except Exception:
        logger.debug('ocr_image processing failed', exc_info=True)
    return None


def parse_ocr_text(text):
    """Parse OCR text into adjustment mapping using tools.parse_adjustments helpers.
    Returns corrected mapping dict or None.
    """
    try:
        # tools.parse_adjustments is test code; import if available
        from tools.parse_adjustments import parse_lines_to_map, fix_values
    except Exception:
        try:
            from parse_adjustments import parse_lines_to_map, fix_values
        except Exception:
            # no parse_adjustments available in this environment
            return None
    try:
        mapping = parse_lines_to_map(text)
        corrected = fix_values(mapping)
        return corrected
    except Exception:
        logger.debug('parse_ocr_text failed', exc_info=True)
        return None
