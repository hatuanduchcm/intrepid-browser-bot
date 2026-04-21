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
import time
import pyautogui
from pathlib import Path
from typing import Optional
import re as _re

DEBUG_DIR = Path(__file__).resolve().parents[2] / 'assets' / 'debug_matches'
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)

def capture_debug_shots(cx: int, cy: int, pad_w: int = 700, pad_h: int = 1200):
    """Capture and return crop_path.

    We no longer save a full-shot; return crop_path.
    """
    crop_path = None
    try:
        # crop region around cursor (shifted where tooltips commonly appear)
        try:
            screen_w, screen_h = pyautogui.size()
            x1 = int(max(0, cx - pad_w // 2))
            # use shifted vertical region so popup is included
            shift_y = int(min(screen_h - 1, cy + 40))
            y2 = int(max(0, shift_y - pad_h // 2))
            w_region = int(min(pad_w, screen_w - x1))
            h_region2 = int(min(pad_h, screen_h - y2))
            crop_path = DEBUG_DIR / f'popup_crop_{int(time.time())}.png'
            region = pyautogui.screenshot(region=(x1, y2, w_region, h_region2))
            region.save(str(crop_path))
        except Exception:
            logging.debug('Crop capture failed')
            crop_path = None
    except Exception as e:
        logging.debug('screenshot capture failed: %s', e)

    # We do not keep a full-shot file; return crop_path
    return crop_path


def handle_copy_adjustment_event(event_payload):
    """If an adjustment tooltip/icon exists, click/hover the '?' icon and read the popup details.
    Returns a dict-like string with found lines, or raises if not found.
    """
    w = get_intrepid_window()
    if not w:
        raise RuntimeError('Intrepid window not found')

    venture = (event_payload.get('venture') or '').strip().upper()

    # try to get tooltip data using layered strategies
    try:
        # first capture tooltip popup visually (hover/click) so we have images available
        crop_path = _hover_and_capture_tooltip(w)

        # then attempt: control-level tooltip or Pane scan (may succeed without OCR)
        # text = get_tooltip_data(w)
        # if text:
        #     return text

        # finally, try OCR/template on captured images (prefer crop only)
        text = get_tooltip_data(_path=crop_path, venture=venture)
        if text:
            # return the parsed dict as-is so caller can handle formatting
            return text
    except Exception as e:
        logger.debug('copy_adjustment_failed: %s', e)

    raise RuntimeError('Adjustment details not found')


def _hover_and_capture_tooltip(window):
    """Locate the question icon visually, hover/click it and capture screenshots.
    Returns crop_path where crop_path may be None.
    """

    icon_path = Path(__file__).resolve().parents[2] / 'assets' / 'icons' / 'question.png'
    crop_path = None
    try:
        try:
            time.sleep(1)
            window.set_focus()
            time.sleep(1.5)
        except Exception:
            logger.debug('set_focus failed, proceeding without focusing window')

        # try to scroll the page to the adjustment using Ctrl+F
        # try:
        #     pyautogui.click(500, 500)
        #     time.sleep(0.8)
        #     pyautogui.hotkey('ctrl', 'f')
        #     time.sleep(0.5)
        #     pyautogui.typewrite('Order Adjustment', interval=0.05)

        #     pyautogui.press('enter')
        #     shot_path = DEBUG_DIR / f'after_find_{int(time.time())}.png'
        #     pyautogui.screenshot(str(shot_path))
        # except Exception as e:
        #     logger.debug('Ctrl+F search failed: %s', e)

        result = find_order_adjustment_block()

        if result:
            logger.info(f"Found at ({result['x']}, {result['y']})")
        else:
            logger.warning("Not found")

        if icon_path.exists():
            try:
                matches = []
                # retry locating the icon a few times because it may appear shortly after load
                deadline = time.time() + 3.0
                while time.time() < deadline:
                    try:
                        matches = list(pyautogui.locateAllOnScreen(str(icon_path), confidence=0.7))
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
                    # capture screenshots only when enabled via environment variable
                    try:
                        crop_path = capture_debug_shots(cx, cy)
                    except Exception:
                        crop_path = None
            except Exception as e:
                logger.debug('image locate/click failed: %s', e)
        else:
            logger.debug('Question icon image not found')
    except Exception as e:
        logger.debug('hover_and_capture failed: %s', e)

    return crop_path

def find_order_adjustment_block(
    max_scrolls: int = 30,
    confidence: float = 0.8,
    scroll_amount: int = -400,
    delay: float = 0.5
) -> Optional[dict]:
    """
    Scroll page and find Order Adjustment block using image recognition.
    Icon path is embedded inside function.
    """

    _icons_dir = Path(__file__).resolve().parents[2] / 'assets' / 'icons'
    _candidates = [
        _icons_dir / c for c in ['order-adjustment-block.png', 'order-adjustment-block-2.png', 'order-adjustment-block-3.png']
        if (_icons_dir / c).exists()
    ]

    if not _candidates:
        raise FileNotFoundError('No adjustment block icon found in assets/icons/')

    def _try_all_icons_at_current_position():
        """Try all candidate icons at the current scroll position. Returns result dict or None."""
        for _p in _candidates:
            try:
                match = pyautogui.locateOnScreen(str(_p), confidence=confidence, grayscale=True)
                if match:
                    pyautogui.scroll(-200)
                    center_x = match.left + match.width // 2
                    center_y = match.top + match.height // 2
                    pyautogui.click(center_x, center_y)
                    logger.debug('Found adjustment block via %s', _p.name)
                    return {"found": True, "x": center_x, "y": center_y}
            except Exception as e:
                logger.debug('locateOnScreen failed for %s: %s', _p.name, e)
        return None

    for i in range(max_scrolls):
        result = _try_all_icons_at_current_position()
        if result:
            result['attempt'] = i
            return result
        pyautogui.scroll(scroll_amount)
        time.sleep(delay)

    # retry from top
    try:
        logger.debug('Initial search failed; scrolling to top and retrying')
        pyautogui.scroll(10000)
        time.sleep(0.6)
        for i in range(max_scrolls):
            result = _try_all_icons_at_current_position()
            if result:
                result['attempt'] = i
                return result
            pyautogui.scroll(scroll_amount)
            time.sleep(delay)
    except Exception:
        logger.debug('Retry from top failed', exc_info=True)

    return None

def get_tooltip_data(_path=None, venture: str = ''):
    """Attempt to extract tooltip text using control, UI-tree inspection, then image/OCR fallback.

    Uses the provided crop path (`_path`) for OCR/template matching.
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
    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = r"C:\Users\hang.truong\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
        from PIL import Image
        easyocr_reader = None
    except Exception:
        logger.debug('pytesseract or PIL not available, trying easyocr')
        pytesseract = None
        try:
            import easyocr
            easyocr_reader = easyocr.Reader(['en'])
        except Exception:
            logger.debug('easyocr not available')
            easyocr_reader = None

    # use shared OCR helper from utils
    try:
        from utils.ocr import ocr_image, parse_ocr_text
    except Exception:
        ocr_image = None
        parse_ocr_text = None

    # Run OCR on crop only (prefer crop for OCR; shot is kept for archive)
    try:
        logger.debug('Extracted adjustment mapping from crop: %s', _path)
        result = extract_adjustment_mapping_from_crop(_path, venture=venture)
        if result:
            # validate Total Adjustment Amount if present
            try:
                check = validate_total_adjustment(result)
                if check is not None:
                    result['__total_check__'] = check
            except Exception:
                logger.debug('Total validation failed', exc_info=True)

            # persist only on validation failure to reduce debug clutter
            try:
                printable = {str(k): v for k, v in result.items()} if isinstance(result, dict) else result
            except Exception:
                printable = result
                logging.debug('Failed to convert result to printable format', exc_info=True)

            try:
                if isinstance(check, dict) and not check.get('matches'):
                    # write a persistent error JSON and ensure jsonl has the record
                    ts = int(time.time())
                    err_file = DEBUG_DIR / f'adjustment_result_error_{ts}.json'
                    err_file.write_text(json.dumps(printable, ensure_ascii=False, indent=2))
            except Exception:
                logger.exception('Failed to write adjustment_result error')

            # cleanup crop artifact when totals match to reduce files
            try:
                if isinstance(check, dict) and check.get('matches') and _path:
                    p = Path(_path)
                    if p.exists():
                        p.unlink()
            except Exception:
                logger.debug('Failed to remove crop artifact: %s', _path)

            return result
    except Exception as e:
        logger.debug('OCR/template fallback failed: %s', e)

    return None


def extract_adjustment_mapping_from_crop(_path, venture: str = ''):
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

    # primary OCR attempt
    crop_ocr = ocr_image(_path) if ocr_image else None
    if crop_ocr:
        ocr_log.append(('crop', crop_ocr))
    else:
        # primary OCR produced nothing; attempt alternate scales immediately
        try:
            from utils.ocr import ocr_image_variants
        except Exception:
            ocr_image_variants = None

        if ocr_image_variants:
            try:
                variants = ocr_image_variants(_path, scales=(3.0, 1.5, 4.0, 2.0))
            except Exception:
                variants = {}

            for s, txt in (variants or {}).items():
                ocr_log.append((f'scale_{s}', txt))
                if not txt:
                    continue
                # try parsing/validating this variant
                parsed_variant = None
                try:
                    parsed_variant = parse_lines_to_map(txt, venture=venture)
                except Exception:
                    parsed_variant = None
                if parsed_variant:
                    try:
                        # attach raw lines
                        if isinstance(parsed_variant, dict):
                            parsed_variant['__ocr_lines__'] = [l.strip() for l in txt.splitlines() if l.strip()]
                        chk = validate_total_adjustment(parsed_variant)
                        if isinstance(parsed_variant, dict):
                            parsed_variant['__total_check__'] = chk
                    except Exception:
                        logger.debug('Failed to attach validation to parsed variant', exc_info=True)
                    return parsed_variant

        return None

    # helper: parse text, attach ocr lines, validate totals; return parsed if valid or parsed anyway
    def _try_parse_and_validate(text):
        try:
            parsed = parse_lines_to_map(text, venture=venture)
        except Exception as e:
            logger.debug('parse_lines_to_map failed for text variant', exc_info=True)
            try:
                (DEBUG_DIR / 'ocr_parse_error.txt').write_text(str(e))
            except Exception:
                logger.debug('Failed to write ocr_parse_error.txt')
            return None

        # attach raw OCR lines
        try:
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            if isinstance(parsed, dict):
                parsed['__ocr_lines__'] = lines
        except Exception:
            logger.debug('Failed to attach OCR lines to parsed mapping')

        # validate totals; if matches True return parsed
        try:
            check = validate_total_adjustment(parsed)
            if isinstance(check, dict) and check.get('matches'):
                return parsed
        except Exception:
            logger.debug('validate_total_adjustment raised for parsed mapping', exc_info=True)

        return parsed

    # try primary parsed result first
    primary_parsed = _try_parse_and_validate(crop_ocr)
    if primary_parsed:
        try:
            chk = validate_total_adjustment(primary_parsed)
            if isinstance(primary_parsed, dict):
                primary_parsed['__total_check__'] = chk
        except Exception:
            logger.debug('Failed to attach total check to primary_parsed', exc_info=True)
        return primary_parsed

    # if validation failed, attempt alternate OCR scales
    try:
        from utils.ocr import ocr_image_variants
    except Exception:
        ocr_image_variants = None

    if ocr_image_variants:
        try:
            variants = ocr_image_variants(_path, scales=(3.0, 1.5, 4.0, 2.0))
        except Exception:
            variants = {}

        for s, txt in (variants or {}).items():
            ocr_log.append((f'scale_{s}', txt))
            if not txt:
                continue
            parsed_variant = _try_parse_and_validate(txt)
            if parsed_variant:
                try:
                    chk = validate_total_adjustment(parsed_variant)
                    if isinstance(parsed_variant, dict):
                        parsed_variant['__total_check__'] = chk
                except Exception:
                    logger.debug('Failed to attach total check to parsed_variant', exc_info=True)
                try:
                    (DEBUG_DIR / 'ocr_text.txt').write_text('\n\n'.join(f"[{k}]\n{v}" for k, v in ocr_log if v))
                except Exception:
                    logger.debug('Failed to write ocr_text.txt')
                return parsed_variant

    # persist OCR log for inspection and return the best-effort parsed mapping (may be None)
    try:
        (DEBUG_DIR / 'ocr_text.txt').write_text('\n\n'.join(f"[{k}]\n{v}" for k, v in ocr_log if v))
    except Exception:
        logger.debug('Failed to write ocr_text.txt')

    # attach validation result to primary_parsed before returning
    try:
        if primary_parsed and isinstance(primary_parsed, dict):
            chk = validate_total_adjustment(primary_parsed)
            primary_parsed['__total_check__'] = chk
    except Exception:
        logger.debug('Failed to attach total check to primary_parsed at end', exc_info=True)

    return primary_parsed

def parse_lines_to_map(text: str, venture: str = ''):
    """Parse OCR text lines into a mapping ColumnName -> numeric string.

    Uses the simplified `ADJUSTMENT_COLUMNS` (ColumnName -> list of Shopee labels).
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    mapping = {}

    # ADJUSTMENT_COLUMNS is now ColumnName -> list of shopee labels
    from gsheets.order_adjustment_sheet import ADJUSTMENT_COLUMNS, ColumnName

    # build label_map: ColumnName -> list(lowercase labels)
    label_map = {cname: [lbl.strip().lower() for lbl in labs if lbl and isinstance(lbl, str)] for cname, labs in ADJUSTMENT_COLUMNS.items()}

    from utils.amounts import clean_amount

    # Iterate lines first, then check each column for a match
    for i, line in enumerate(lines):
        label_text, numeric = split_text_and_number(line)
        if not label_text or not numeric:
            continue
        for cname, labs in label_map.items():
            # try direct substring match first
            matched = False
            for lab in labs:
                lab_l = lab.lower()
                if lab_l in label_text:
                    # val = _re.sub(r"\s+", "", numeric or '')
                    # mapping[cname] = clean_amount(numeric) if venture.upper() == 'VN' else numeric
                    mapping[cname] = clean_amount(numeric)
                    # matched = True
                    break
            # if matched:
            #     continue
            # token-subset fallback
            # ltokens = set(t for t in _re.split(r"\W+", label_text) if t)
            # for lab in labs:
            #     lab_tokens = set(t for t in _re.split(r"\W+", lab.lower()) if t)
            #     if lab_tokens and lab_tokens <= ltokens:
            #         # val = _re.sub(r"\s+", "", numeric or '')
            #         mapping[cname] = drop_first_after_cleanup(numeric)
            #         break

    return mapping


def split_text_and_number(line: str):
    if not line:
        return "", ""
    
    # Remove special | character that may interfere with OCR parsing, replacing it with a space to preserve word boundaries
    line = line.replace('|', '')

    # match number-like block (keep raw format including $, ₫, -, ., etc.)
    # allow an optional single currency-like char or single letter immediately
    # before the digit sequence; also accept an optional sign and separators (., and spaces)
    # This lets OCR outputs like 'd9 329' be captured as a single match which
    # we then collapse to 'd9329'. Exclude '|' from the prefix group.
    num_pattern = r"(?:(?<=^)|(?<=\s))[-+]?\s*(?:[^\w\s\|]|\w)?\s*\d[\d\.,\s]*"

    nums = _re.findall(num_pattern, line)

    # collapse internal whitespace in numeric token so 'd9 329' -> 'd9329'
    num = _re.sub(r"\s+", "", nums[-1]).strip() if nums else ''

    # remove number block from text
    text_only = _re.sub(num_pattern, " ", line)

    # normalize whitespace only
    text_only = text_only.strip().lower()

    return text_only, num

def validate_total_adjustment(parsed: dict):
    """Return comparison using TOTAL_ADJUSTMENT_AMOUNT directly (no recompute sum)."""
    try:
        from gsheets.order_adjustment_sheet import ColumnName
    except Exception:
        return None

    total_key = ColumnName.TOTAL_ADJUSTMENT_AMOUNT

    if not isinstance(parsed, dict) or total_key not in parsed:
        return None

    from decimal import Decimal, ROUND_HALF_UP

    def to_num(s):
        if not s:
            return Decimal(0)
        ss = str(s)
        # remove common thousand separators and currency letters
        ss = ss.replace(',', '').replace('.', '').replace('₫', '').replace('đ', '')
        import re as __re
        ss = __re.sub(r"\s+", "", ss)

        try:
            from utils.amounts import process_amount_for_region
            ss = process_amount_for_region(ss)
        except Exception:
            pass

        try:
            return Decimal(ss)
        except Exception:
            m = __re.search(r"-?\d+[\d\.]*", ss)
            return Decimal(m.group(0)) if m else Decimal(0)

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
    # also build per-key converted map for logging
    converted_map = {}
    for k, v in parsed.items():
        try:
            nv = to_num(v)
        except Exception:
            nv = Decimal(0)
        key_str = str(k)
        # skip internal/debug keys (like __ocr_lines__, __total_check__) from logging and summing
        if not key_str.startswith('__'):
            converted_map[key_str] = int(nv.to_integral_value(rounding=ROUND_HALF_UP))

        # skip the authoritative total key and any debug keys when summing
        try:
            is_total_key = (k == total_key)
        except Exception:
            is_total_key = False

        if is_total_key or key_str.startswith('__'):
            continue

        s += nv
    # money is integer (smallest currency unit); compare as integers
    try:
        sum_others_int = int(s.to_integral_value(rounding=ROUND_HALF_UP))
        total_val_int = int(Decimal(total_val).to_integral_value(rounding=ROUND_HALF_UP))
    except Exception:
        sum_others_int = int(s)
        total_val_int = int(total_val)

    # expected_sum should come from TOTAL_ADJUSTMENT_AMOUNT; compare with sum of other values
    matches = (total_val_int == sum_others_int)

    if not matches:
        # persist mismatch record (append JSON lines)
        try:
            record = {
                'ts': int(time.time()),
                'raw_parsed': {str(k): v for k, v in parsed.items()},
                'converted_map': converted_map,
                'expected_sum': int(total_val_int),
                'total_value': int(sum_others_int),
                'matches': matches,
            }
            out_p = DEBUG_DIR / 'adjustment_validation_errors.jsonl'
            with out_p.open('a', encoding='utf-8') as f:
                # write a human-readable JSON block per record and separate records with ---
                f.write(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
                f.write("---\n")
        except Exception:
            logger.exception('Failed to write adjustment validation error')

    return {'expected_sum': int(total_val_int), 'total_value': int(sum_others_int), 'matches': matches}