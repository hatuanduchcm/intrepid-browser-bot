import logging
from pathlib import Path
import cv2

logger = logging.getLogger(__name__)


def ocr_image(path, tesseract_cmd=r"C:\Users\hang.truong\AppData\Local\Programs\Tesseract-OCR\tesseract.exe", scale: float = 3.0):
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
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
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


def ocr_image_variants(path, tesseract_cmd=r"C:\Users\hang.truong\AppData\Local\Programs\Tesseract-OCR\tesseract.exe", scales=(3.0, 1.5, 4.0)):
    """Run OCR using multiple preprocessing scales and return a mapping scale->text (or None).

    This does not choose among results; caller can use these variants when validation
    of the primary OCR result fails.
    """
    results = {}
    for s in scales:
        try:
            results[float(s)] = ocr_image(path, tesseract_cmd=tesseract_cmd, scale=float(s))
        except Exception:
            logger.debug('ocr_image failed for scale %s', s, exc_info=True)
            results[float(s)] = None
    return results


def ocr_image_first_success(path, tesseract_cmd=r"C:\Users\hang.truong\AppData\Local\Programs\Tesseract-OCR\tesseract.exe", scales=(3.0, 1.5, 4.0)):
    """Try OCR at each scale and return the first non-empty result and its scale.

    Returns a tuple (text, scale) where text is None if nothing succeeded.
    """
    variants = ocr_image_variants(path, tesseract_cmd=tesseract_cmd, scales=scales)
    for s in scales:
        txt = variants.get(float(s))
        if txt:
            return txt, float(s)
    return None, None

