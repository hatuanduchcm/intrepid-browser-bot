import json

from sympy import re

from utils.window import get_intrepid_window
import logging
import time
import os
from pathlib import Path
import traceback
import cv2
import numpy as np

DEBUG_DIR = Path(__file__).resolve().parents[2] / 'assets' / 'debug_matches'
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)


def handle_copy_adjustment_event(event_payload):
    """If an adjustment tooltip/icon exists, click/hover the '?' icon and read the popup details.
    Returns a dict-like string with found lines, or raises if not found.
    """
    w = get_intrepid_window()
    if not w:
        raise RuntimeError('Intrepid window not found')

    # try to get tooltip data using layered strategies
    try:
        # first capture tooltip popup visually (hover/click) so we have images available
        shot_path, crop_path = _hover_and_capture_tooltip(w)

        # then attempt: control-level tooltip or Pane scan (may succeed without OCR)
        # text = get_tooltip_data(w)
        # if text:
        #     return text

        # finally, try OCR/template on captured images (prefer crop only; shot saved for archive)
        text = get_tooltip_data(_path=crop_path)
        if text:
            # return the parsed dict as-is so caller can handle formatting
            return text
    except Exception as e:
        logger.debug('copy_adjustment_failed: %s', e)

    raise RuntimeError('Adjustment details not found')


def _hover_and_capture_tooltip(window):
    """Locate the question icon visually, hover/click it and capture screenshots.
    Returns (shot_path, crop_path) where crop_path may be None.
    """
    try:
        import pyautogui
    except Exception:
        logger.debug('pyautogui not available')
        return (None, None)

    icon_path = Path(__file__).resolve().parents[2] / 'assets' / 'icons' / 'question.png'
    shot_path = None
    crop_path = None
    try:
        try:
            window.set_focus()
        except Exception:
            logger.debug('set_focus failed, proceeding without focusing window')

        # try to scroll the page to the adjustment using Ctrl+F
        try:
            pyautogui.keyDown('ctrl')
            pyautogui.press('f')
            pyautogui.keyUp('ctrl')
            time.sleep(1)
            pyautogui.typewrite('Order Adjustment')
            pyautogui.press('enter')
            time.sleep(1)
            shot_path = DEBUG_DIR / f'after_find_{int(time.time())}.png'
            pyautogui.screenshot(str(shot_path))
        except Exception as e:
            logger.debug('Ctrl+F search failed: %s', e)

        if icon_path.exists():
            try:
                matches = []
                # retry locating the icon a few times because it may appear shortly after load
                deadline = time.time() + 3.0
                while time.time() < deadline:
                    try:
                        matches = list(pyautogui.locateAllOnScreen(str(icon_path), confidence=0.8))
                        if matches:
                            break
                    except Exception as e:
                        logging.debug('locateAllOnScreen error, retrying: %s', e)
                    time.sleep(0.25)
                if matches:
                    chosen = max(matches, key=lambda m: m.top)
                    cx = chosen.left + chosen.width // 2
                    cy = chosen.top + chosen.height // 2
                    pyautogui.moveTo(cx, cy, duration=0.2)
                    pyautogui.click(cx, cy)
                    time.sleep(0.35)
                    shot_path = DEBUG_DIR / f'after_click_{int(time.time())}.png'
                    pyautogui.screenshot(str(shot_path))
                    time.sleep(0.6)
                    # crop region around cursor
                    try:
                        # make a larger crop around the click to include full popup
                        screen_w, screen_h = pyautogui.size()
                        pad_w = 700
                        pad_h = 800
                        x1 = int(max(0, cx - pad_w // 2))
                        y1 = int(max(0, cy - pad_h // 2))
                        w_region = int(min(pad_w, screen_w - x1))
                        h_region = int(min(pad_h, screen_h - y1))
                        crop_path = DEBUG_DIR / f'popup_crop_cursor_{int(time.time())}.png'
                        region = pyautogui.screenshot(region=(x1, y1, w_region, h_region))
                        region.save(str(crop_path))
                        # also save a downward-shifted crop in case popup is below the icon
                        shift_y = int(min(screen_h - 1, cy + 40))
                        y2 = int(max(0, shift_y - pad_h // 2))
                        h_region2 = int(min(pad_h, screen_h - y2))
                        crop_path2 = DEBUG_DIR / f'popup_crop_shifted_{int(time.time())}.png'
                        region2 = pyautogui.screenshot(region=(x1, y2, w_region, h_region2))
                        region2.save(str(crop_path2))
                        # prefer the primary crop, but return both via concatenation later (we'll set crop_path to primary)
                        # store extra path by returning tuple later via shot_path/crop_path handling
                        # attach attribute on DEBUG_DIR for consumer (simple approach: also write a marker file)
                        (DEBUG_DIR / 'last_extra_crop.txt').write_text(str(crop_path2))
                    except Exception:
                        crop_path = shot_path
                        logging.debug('Crop failed, using full screenshot as fallback')
            except Exception as e:
                logger.debug('image locate/click failed: %s', e)
        else:
            logger.debug('Question icon image not found')
    except Exception as e:
        logger.debug('hover_and_capture failed: %s', e)

    return (shot_path, crop_path)


def get_tooltip_data(_path=None):
    """Attempt to extract tooltip text using control, UI-tree inspection, then image/OCR fallback.

    If `shot_path` or `crop_path` are provided, use them for OCR/template matching.
    """
    # 1) Try to find ToolTip or Text controls directly
    # try:
    #     for t in window.descendants(control_type='ToolTip'):
    #         try:
    #             txt = t.window_text() or ''
    #         except Exception:
    #             txt = ''
    #         if txt:
    #             logger.debug('Found tooltip via ToolTip control')
    #             return txt
    # except Exception:
    #     logger.debug('ToolTip control scan failed')

    # 2) Inspect UI tree: search Pane/Text children for relevant keywords
    # try:
    #     for p in window.descendants(control_type='Pane'):
    #         try:
    #             text = p.window_text() or ''
    #         except Exception:
    #             text = ''
    #         if text and any(k in text.lower() for k in ('refund', 'voucher', 'total adjustment')):
    #             logger.debug('Found tooltip via Pane text')
    #             return text
    # except Exception:
    #     logger.debug('UI tree Pane scan failed')

    # 3) OCR/template fallback using provided images
    # prefer pytesseract + PIL, but fall back to easyocr if available
    # try:
    #     import pytesseract
    #     pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    #     from PIL import Image
    #     easyocr_reader = None
    # except Exception:
    #     logger.debug('pytesseract or PIL not available, trying easyocr')
    #     pytesseract = None
    #     try:
    #         import easyocr
    #         easyocr_reader = easyocr.Reader(['en'])
    #     except Exception:
    #         logger.debug('easyocr not available')
    #         easyocr_reader = None

    # use shared OCR helper from utils
    # try:
    #     from utils.ocr import ocr_image, parse_ocr_text
    # except Exception:
    #     ocr_image = None
    #     parse_ocr_text = None

    # Run OCR on crop only (prefer crop for OCR; shot is kept for archive)
    try:
        logger.debug('Extracted adjustment mapping from crop: %s', _path)
        result = extract_adjustment_mapping_from_crop(_path)
        if result:
            # validate Total Adjustment Amount if present
            try:
                check = validate_total_adjustment(result)
                if check is not None:
                    result['__total_check__'] = check
            except Exception:
                logger.debug('Total validation failed', exc_info=True)
            # persist a JSON-printable copy (convert enum keys to strings)
            try:
                printable = {str(k): v for k, v in result.items()} if isinstance(result, dict) else result
            except Exception:
                printable = result
                logging.debug('Failed to convert result to printable format', exc_info=True)
            (DEBUG_DIR / 'adjustment_result.json').write_text(json.dumps(printable, ensure_ascii=False, indent=2))
            return result
    except Exception as e:
        logger.debug('OCR/template fallback failed: %s', e)

    return None


def extract_adjustment_mapping_from_crop(_path):
    """Run OCR on `crop_path`, save debug text, and return parsed adjustment mapping or raw OCR text.

    Extracted and renamed to better reflect its purpose.
    """
    try:
        from utils.ocr import ocr_image, parse_ocr_text
    except Exception:
        ocr_image = None
        parse_ocr_text = None

    ocr_log = []
    if not _path:
        return None
    crop_ocr = ocr_image(_path) if ocr_image else None
    if not crop_ocr:
        return None
    ocr_log.append(('crop', crop_ocr))
    if any(k in crop_ocr.lower() for k in ('refund', 'voucher', 'total adjustment')):
        (DEBUG_DIR / 'ocr_text.txt').write_text('\n\n'.join(f"[{k}]\n{v}" for k, v in ocr_log))
        parsed = parse_lines_to_map(crop_ocr)
        return parsed
    return None

def parse_lines_to_map(text: str):
    """Parse OCR text lines into a mapping ColumnName -> numeric string.

    Uses the simplified `ADJUSTMENT_COLUMNS` (ColumnName -> list of Shopee labels).
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    mapping = {}

    # ADJUSTMENT_COLUMNS is now ColumnName -> list of shopee labels
    from gsheets.order_adjustment_sheet import ADJUSTMENT_COLUMNS, ColumnName

    # build label_map: ColumnName -> list(lowercase labels)
    label_map = {cname: [lbl.strip().lower() for lbl in labs if lbl and isinstance(lbl, str)] for cname, labs in ADJUSTMENT_COLUMNS.items()}

    import re as _re

    def split_text_and_number(line: str):
        nums = _re.findall(r"[\-₫đ]?\d[\d\.,\s]*\d", line)
        num = nums[-1].strip() if nums else ''
        text_only = _re.sub(r"[0-9\-₫đ,\.]+", " ", line)
        text_only = _re.sub(r"\s+", " ", text_only).strip().lower()
        return text_only, num

    from utils.amounts import trim_leading_integer_digits, process_amount_for_region

    # Iterate lines first, then check each column for a match
    for i, line in enumerate(lines):
        label_text, numeric = split_text_and_number(line)
        if not label_text:
            continue
        for cname, labs in label_map.items():
            # try direct substring match first
            matched = False
            for lab in labs:
                lab_l = lab.lower()
                if lab_l in label_text:
                    val = _re.sub(r"\s+", "", numeric or '')
                    mapping[cname] = process_amount_for_region(val, 'VN')
                    matched = True
                    break
            if matched:
                continue
            # token-subset fallback
            ltokens = set(t for t in _re.split(r"\W+", label_text) if t)
            for lab in labs:
                lab_tokens = set(t for t in _re.split(r"\W+", lab.lower()) if t)
                if lab_tokens and lab_tokens <= ltokens:
                    val = _re.sub(r"\s+", "", numeric or '')
                    mapping[cname] = process_amount_for_region(val, 'VN')
                    break

    return mapping


def validate_total_adjustment(parsed: dict):
    """If `parsed` contains `ColumnName.TOTAL_ADJUSTMENT_AMOUNT`, compute sum of others and
    return {'expected_sum': s, 'total_value': total_val, 'matches': bool} or None if not applicable."""
    try:
        from gsheets.order_adjustment_sheet import ColumnName
    except Exception:
        return None
    total_key = ColumnName.TOTAL_ADJUSTMENT_AMOUNT
    if not isinstance(parsed, dict) or total_key not in parsed:
        return None

    from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

    def to_num(s):
        if not s:
            return 0.0
        ss = str(s)
        # remove common separators, currency symbols and whitespace
        ss = ss.replace(',', '').replace('₫', '').replace('đ', '')
        import re as __re
        ss = __re.sub(r"\s+", "", ss)
        # apply region-specific trimming if helper available
        try:
            from utils.amounts import process_amount_for_region
            ss = process_amount_for_region(ss)
        except Exception:
            pass
        try:
            return Decimal(ss)
        except Exception:
            m = __re.search(r"-?\d+[\d\.]*", ss)
            try:
                return Decimal(m.group(0)) if m else Decimal(0)
            except Exception:
                return Decimal(0)

    # allow keys as enum, string(enum), or header string
    total_val = None
    if total_key in parsed:
        total_val = to_num(parsed.get(total_key))
    else:
        try:
            from gsheets.order_adjustment_sheet import GSHEET_COLUMN
            header = GSHEET_COLUMN.get(total_key)
        except Exception:
            header = None
        if str(total_key) in parsed:
            total_val = to_num(parsed.get(str(total_key)))
        elif header and header in parsed:
            total_val = to_num(parsed.get(header))
        else:
            total_val = to_num(parsed.get(total_key, '0'))
    s = Decimal(0)
    for k, v in parsed.items():
        if k == total_key:
            continue
        s += to_num(v)
    # money is integer (smallest currency unit); compare as integers
    try:
        s_int = int(s.to_integral_value(rounding=ROUND_HALF_UP))
        total_int = int(Decimal(total_val).to_integral_value(rounding=ROUND_HALF_UP))
    except Exception:
        s_int = int(s)
        total_int = int(total_val)
    return {'expected_sum': int(s_int), 'total_value': int(total_int), 'matches': s_int == total_int}