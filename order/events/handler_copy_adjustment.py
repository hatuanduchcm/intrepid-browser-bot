import json

from utils.window import get_intrepid_window
import logging
import time
from pathlib import Path
import pyautogui
from typing import Optional
import re as _re

DEBUG_DIR = Path(__file__).resolve().parents[2] / 'assets' / 'debug_matches'
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)

def capture_debug_shots(cx: int, cy: int, pad_w: int = 450, pad_h: int = 600):
    """Capture and return crop_path using mss for physical-pixel accuracy (DPI-aware).

    Captures the region above the cursor where the adjustment popup appears.
    """
    crop_path = None
    try:
        try:
            screen_w, screen_h = pyautogui.size()
            x1 = int(max(0, cx - pad_w // 2))
            w_region = int(min(pad_w, screen_w - x1))
            # popup appears ABOVE the cursor — capture upward from cursor position
            y2 = int(max(0, cy - pad_h))
            h_region2 = int(min(pad_h, cy))
            crop_path = DEBUG_DIR / f'popup_crop_{int(time.time())}.png'
            try:
                import mss
                import mss.tools
                with mss.mss() as sct:
                    monitor = {'left': x1, 'top': y2, 'width': w_region, 'height': h_region2}
                    shot = sct.grab(monitor)
                    mss.tools.to_png(shot.rgb, shot.size, output=str(crop_path))
            except Exception:
                logging.debug('mss capture failed, falling back to pyautogui')
                region = pyautogui.screenshot(region=(x1, y2, w_region, h_region2))
                region.save(str(crop_path))
        except Exception:
            logging.debug('Crop capture failed')
            crop_path = None
    except Exception as e:
        logging.debug('screenshot capture failed: %s', e)

    return str(crop_path) if crop_path is not None else None


def handle_copy_adjustment_event(event_payload):
    """If an adjustment tooltip/icon exists, click/hover the '?' icon and read the popup details.
    Returns a dict-like string with found lines, or raises if not found.
    """
    w = get_intrepid_window()
    if not w:
        raise RuntimeError('Intrepid window not found')

    venture = (event_payload.get('venture') or '').strip().upper()
    order_id = (event_payload.get('order_id') or event_payload.get('order') or '').strip()

    # try to get tooltip data using layered strategies
    try:
        # hover/click question icon or capture adjustment area if icon absent
        crop_path = _hover_and_capture_tooltip(w, venture=venture, order_id=order_id)
        crop_path = crop_path if isinstance(crop_path, str) else None

        # OCR / parse pipeline handles all label types via ADJUSTMENT_COLUMNS
        text = get_tooltip_data(_path=crop_path, venture=venture)
        if text:
            return text
    except Exception as e:
        logger.debug('copy_adjustment_failed: %s', e)

    raise RuntimeError('Adjustment details not found')


def _hover_and_capture_tooltip(window, venture: str = '', order_id: str = ''):
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

        result = find_order_adjustment_block()

        if result:
            logger.info(f"Found at ({result['x']}, {result['y']})")
        else:
            logger.warning("Order Adjustment block not found")

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
                    # Wait for popup to render before capturing
                    time.sleep(0.5)
                    # Popup mode: capture above the ? icon, spread left/right
                    crop_path = _capture_adjustment_area(cx=cx, cy=cy, popup_mode=True, order_id=order_id)
                else:
                    # No question icon — capture the visible adjustment block area for OCR
                    logger.debug('question icon not found, capturing adjustment block area for OCR')
                    ref_x = result['x'] if result else None
                    ref_y = result['y'] if result else None
                    crop_path = _capture_adjustment_area(ref_x, ref_y, order_id=order_id)
            except Exception as e:
                logger.debug('image locate/click failed: %s', e)
        else:
            logger.debug('Question icon image not found')
            # capture adjustment block area for OCR (handles all label types)
            ref_x = result['x'] if result else None
            ref_y = result['y'] if result else None
            crop_path = _capture_adjustment_area(ref_x, ref_y, order_id=order_id)
    except Exception as e:
        logger.debug('hover_and_capture failed: %s', e)

    return crop_path


def _find_table_bounds(total_row_tpl, reason_row_tpl, ref_y: int = None, screen_h: int = 900):
    """Find total_row and reason_row matches, filtered by ref_y if given.

    Returns (top_match, bottom_match) where:
    - top_match  = adjustment_reason_row (header) — defines y_top
    - bottom_match = total_adjustment_row — defines y_bottom

    Either may be None if not found.
    If ref_y is given, only matches on the same side of ref_y as expected are kept:
    - both templates must be BELOW ref_y (inline mode: ref_y = block header cy)
    - popup mode: ref_y = None, pick match-pair closest to each other
    """
    def _locate(tpl, confidence=0.75):
        if not tpl.exists():
            return []
        try:
            return list(pyautogui.locateAllOnScreen(str(tpl), confidence=confidence))
        except Exception as e:
            logger.debug('locateAllOnScreen %s failed: %s', tpl.name, e)
            return []

    total_matches  = _locate(total_row_tpl)
    reason_matches = _locate(reason_row_tpl)

    if ref_y is not None:
        # Inline mode: keep only matches below the block header
        total_matches  = [m for m in total_matches  if m.top > ref_y] or total_matches
        reason_matches = [m for m in reason_matches if m.top > ref_y] or reason_matches

    # Pick best total_match
    if not total_matches:
        return None, None
    if ref_y is not None:
        # Inline mode: pick total_match closest below the block header
        total_match = min(total_matches, key=lambda m: abs(m.top - ref_y))
        # Pick reason_match that is just above total_match (closest above)
        reason_match = None
        candidates_above = [m for m in reason_matches if m.top < total_match.top]
        if candidates_above:
            reason_match = max(candidates_above, key=lambda m: m.top)
    else:
        # Popup mode: find the (reason, total) PAIR with smallest vertical gap —
        # that's the compact floating popup, not the full inline table which spans
        # much of the page height.
        best_pair = (None, None)
        best_gap = float('inf')
        for tm in total_matches:
            candidates = [m for m in reason_matches if m.top < tm.top]
            if not candidates:
                continue
            rm = max(candidates, key=lambda m: m.top)  # closest above tm
            gap = tm.top - rm.top
            if gap < best_gap:
                best_gap = gap
                best_pair = (rm, tm)
        reason_match, total_match = best_pair
        # Fallback: if no paired reason found, just use total closest to center
        if total_match is None:
            center_y = screen_h // 2
            total_match = min(total_matches, key=lambda m: abs((m.top + m.height // 2) - center_y))
            reason_match = None

    return reason_match, total_match


def _capture_adjustment_area(cx: int = None, cy: int = None, popup_mode: bool = False, order_id: str = '') -> Optional[str]:
    """Capture the adjustment table with pixel-precise boundaries.

    Uses two templates as anchors:
    - adjustment_reason_row.png  → top boundary
    - total_adjustment_row.png   → bottom boundary

    popup_mode=True (after clicking ? icon at cx,cy):
      Capture a region ABOVE the icon, spread left/right — simple and reliable.

    inline mode (cx/cy given, popup_mode=False):
      Table is below block header → use templates filtered below cy.

    No cx/cy: template-only mode, pick pair closest to screen center.
    """
    _icons_dir = Path(__file__).resolve().parents[2] / 'assets' / 'icons'
    total_row_tpl       = _icons_dir / 'total_adjustment_row.png'
    reason_row_tpl      = _icons_dir / 'adjustment_reason_row.png'
    released_amt_tpl    = _icons_dir / 'released_amount_col.png'

    def _locate_released_amount_col():
        """Try to locate the Released Amount column header; return match or None."""
        if not released_amt_tpl.exists():
            return None
        try:
            return pyautogui.locateOnScreen(str(released_amt_tpl), confidence=0.75)
        except Exception as e:
            logger.debug('released_amount_col locate failed: %s', e)
            return None

    try:
        import mss, mss.tools
        screen_w, screen_h = pyautogui.size()

        # ── Popup mode: capture above the ? icon ────────────────────────────
        if popup_mode and cx is not None and cy is not None:
            pad_w = 450   # spread left/right from icon center (reduced from 500)
            pad_h = 550   # height above icon (popup appears above)
            x1 = max(0, cx - pad_w // 2)
            w1 = min(pad_w, screen_w - x1)
            y1 = max(0, cy - pad_h)
            h1 = min(pad_h, cy)
            _oid = f'_{order_id}' if order_id else ''
            crop_path = DEBUG_DIR / f'adjustment_area{_oid}_{int(time.time())}.png'
            try:
                with mss.mss() as sct:
                    mon = {'left': int(x1), 'top': int(y1), 'width': int(w1), 'height': int(h1)}
                    shot = sct.grab(mon)
                    mss.tools.to_png(shot.rgb, shot.size, output=str(crop_path))
            except Exception:
                shot = pyautogui.screenshot(region=(int(x1), int(y1), int(w1), int(h1)))
                shot.save(str(crop_path))
            logger.debug('popup capture above icon: x=%s y=%s w=%s h=%s -> %s', x1, y1, w1, h1, crop_path)
            return str(crop_path)

        ref_y = cy  # None for template-only mode, block-header y for inline mode
        reason_match, total_match = _find_table_bounds(total_row_tpl, reason_row_tpl,
                                                       ref_y=ref_y, screen_h=screen_h)

        # If inline mode found nothing with ref_y restriction, retry unrestricted
        # (handles TH / other ventures where coordinates may be slightly off)
        if not total_match and ref_y is not None:
            logger.debug('inline template search missed; retrying without ref_y restriction')
            reason_match, total_match = _find_table_bounds(total_row_tpl, reason_row_tpl,
                                                           ref_y=None, screen_h=screen_h)

        # ── Try to locate Released Amount column header for right boundary ──
        released_match = _locate_released_amount_col()
        if released_match:
            logger.debug('released_amount_col found: left=%s w=%s', released_match.left, released_match.width)

        def _right_boundary(left_x: int) -> int:
            """Return right edge: use released_amount_col right edge if available,
            otherwise fall back to 900px from left or screen edge."""
            if released_match:
                return min(released_match.left + released_match.width + 20, screen_w - 5)
            return left_x + min(900, screen_w - left_x - 20)

        if total_match and reason_match:
            # ── Best case: both anchors found → pixel-precise crop ────────
            y      = max(0, reason_match.top - 4)
            bottom = min(total_match.top + total_match.height + 6, screen_h)
            h      = bottom - y
            x      = max(50, min(reason_match.left, total_match.left))
            right  = _right_boundary(x)
            w      = right - x
            logger.debug('precise crop (both templates): x=%s y=%s w=%s h=%s', x, y, w, h)

        elif total_match:
            # ── Only total row found → estimate top via row height ─────────
            row_h  = max(total_match.height, 30)
            y      = max(0, total_match.top - row_h * 12)
            bottom = min(total_match.top + total_match.height + 6, screen_h)
            h      = bottom - y
            x      = max(50, total_match.left)
            right  = _right_boundary(x)
            w      = right - x
            logger.debug('partial crop (total only): x=%s y=%s w=%s h=%s', x, y, w, h)

        else:
            # ── No template found → generic fallback ──────────────────────
            logger.debug('no template match, using generic fallback')
            if released_match:
                # Use released_amount_col to pin the right edge; start 900px to its left
                right = released_match.left + released_match.width + 20
                x = max(50, right - 900)
                w = right - x
            elif cy is not None:
                x = max(50, cx - 50 if cx else 380)
                w = min(screen_w - x - 10, 800)
            else:
                x = 380
                w = screen_w - x - 10
            if cy is not None:
                # Capture from slightly above the block header (cy) to include the
                # table header row, then 650px downward
                y = max(0, cy - 20)
                h = min(650, screen_h - y)
            else:
                y = max(0, screen_h // 4)
                h = min(600, screen_h - y)

        _oid = f'_{order_id}' if order_id else ''
        crop_path = DEBUG_DIR / f'adjustment_area{_oid}_{int(time.time())}.png'
        try:
            with mss.mss() as sct:
                mon = {'left': int(x), 'top': int(y), 'width': int(w), 'height': int(h)}
                shot = sct.grab(mon)
                mss.tools.to_png(shot.rgb, shot.size, output=str(crop_path))
        except Exception:
            shot = pyautogui.screenshot(region=(int(x), int(y), int(w), int(h)))
            shot.save(str(crop_path))

        logger.debug('Captured adjustment area -> %s', crop_path)
        return str(crop_path)
    except Exception as e:
        logger.debug('_capture_adjustment_area failed: %s', e)
        return None
    
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
                    # Record coordinates BEFORE any scroll so they are accurate
                    center_x = match.left + match.width // 2
                    center_y = match.top + match.height // 2
                    # Scroll slightly so the table rows below become visible
                    pyautogui.scroll(-200)
                    time.sleep(0.15)
                    # Re-locate to get updated on-screen position after scroll
                    match2 = pyautogui.locateOnScreen(str(_p), confidence=confidence, grayscale=True)
                    if match2:
                        center_x = match2.left + match2.width // 2
                        center_y = match2.top + match2.height // 2
                    logger.debug('Found adjustment block via %s at (%s, %s)', _p.name, center_x, center_y)
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
    """Extract adjustment data from the captured image via OCR.

    Uses the provided crop path (`_path`) for OCR pipeline.
    Deletes the capture file when totals match, no total found (clean success),
    or when OCR produced no result. Keeps the file only on total mismatch.
    """
    # use shared OCR helper from utils
    try:
        from utils.ocr import ocr_image, parse_ocr_text
    except Exception:
        ocr_image = None
        parse_ocr_text = None

    def _cleanup_path():
        try:
            if _path:
                p = Path(_path)
                if p.exists():
                    p.unlink()
        except Exception:
            logger.debug('Failed to remove crop artifact: %s', _path)

    # Run OCR on crop only (prefer crop for OCR; shot is kept for archive)
    try:
        logger.debug('Extracted adjustment mapping from crop: %s', _path)
        result = extract_adjustment_mapping_from_crop(_path, venture=venture)
        if result:
            # __total_check__ is already attached by extract_adjustment_mapping_from_crop
            check = result.get('__total_check__') if isinstance(result, dict) else None

            # Attach crop path so callers can reference the exact image for this result
            if isinstance(result, dict) and _path:
                result['__crop_path__'] = _path

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

            # Delete capture file when:
            # - totals match (success)
            # - no total key in parsed (no validation = clean)
            # Keep ONLY on explicit total mismatch (for debugging)
            should_delete = (
                (isinstance(check, dict) and check.get('matches'))
                or check is None
            )
            if should_delete:
                _cleanup_path()

            return result

        # OCR produced no result — keep the capture file so error detail can display it
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

    # best-effort fallback: first parsed result even if validation failed
    _best_effort = [None]

    # helper: parse text, attach ocr lines, validate totals; return parsed ONLY if matched
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

        # validate totals; return parsed only when matched
        try:
            check = validate_total_adjustment(parsed)
            if isinstance(parsed, dict):
                parsed['__total_check__'] = check
            if isinstance(check, dict) and check.get('matches'):
                return parsed
        except Exception:
            logger.debug('validate_total_adjustment raised for parsed mapping', exc_info=True)

        # no match: save as best-effort fallback, signal caller to try next variant
        if _best_effort[0] is None:
            _best_effort[0] = parsed
        return None

    # try primary parsed result first
    primary_parsed = _try_parse_and_validate(crop_ocr)
    if primary_parsed:
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
                    (DEBUG_DIR / 'ocr_text.txt').write_text('\n\n'.join(f"[{k}]\n{v}" for k, v in ocr_log if v))
                except Exception:
                    logger.debug('Failed to write ocr_text.txt')
                return parsed_variant

    # persist OCR log for inspection
    try:
        (DEBUG_DIR / 'ocr_text.txt').write_text('\n\n'.join(f"[{k}]\n{v}" for k, v in ocr_log if v))
    except Exception:
        logger.debug('Failed to write ocr_text.txt')

    # return best-effort fallback (validation + __total_check__ already attached)
    return _best_effort[0]

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

    # Iterate lines first, then check each column for a match.
    # Use longest-match-wins so "AMS Commission Fee" matches AMS_COMMISSION_FEE
    # (label len 18) instead of COMMISSION_FEE (label len 14).
    for i, line in enumerate(lines):
        label_text, numeric = split_text_and_number(line)
        if not label_text or not numeric:
            continue
        best_cname = None
        best_len = 0
        for cname, labs in label_map.items():
            for lab in labs:
                if lab in label_text and len(lab) > best_len:
                    best_cname = cname
                    best_len = len(lab)
        if best_cname is not None:
            mapping[best_cname] = clean_amount(numeric, venture=venture)

    return mapping


# OCR letter → digit substitution table (for cases like "Bt" = "฿1")
_OCR_LETTER_TO_DIGIT = str.maketrans({
    't': '1', 'T': '1',
    'l': '1', 'I': '1',
    'O': '0', 'o': '0',
    'S': '5', 's': '5',
    'Z': '2', 'z': '2',
    'G': '6', 'g': '9',
    'B': '8',
})

# Currency prefixes that OCR often renders as a single letter
_CURRENCY_LETTER_PREFIXES = _re.compile(r'^[-+]?\s*[฿₱B$€£¥₫đdPRr]\s*', _re.IGNORECASE)

# OCR misread normalization: (pattern, replacement) applied before number extraction.
# Handles Philippine Peso ₱ being read as 'P°', '#', etc.
_OCR_CURRENCY_NORMALIZE = [
    (_re.compile(r'P°', _re.IGNORECASE), '₱'),                   # P° → ₱
    (_re.compile(r"P['\u2018\u2019\u02bc\u0060\u00b4]"), '₱'),   # P' P' P` P´ → ₱
    (_re.compile(r'(?<![\w])#(?=\d)'), '₱'),                     # # before digit → ₱
    (_re.compile(r'(?<!\w)P(?=[-\d])'), '₱'),                    # bare P before digit/minus → ₱ (e.g. P35.00, P-57.00)
    (_re.compile(r'[-+]?₱-(?=\d)'), lambda m: '-₱'),             # collapse double-sign: -₱- or ₱- → -₱
    # Bold-text OCR: '/' misread as '7' immediately after currency prefix
    # e.g. "Rp/7.000" → "Rp77.000", "Rp/77.000" → "Rp777.000"
    (_re.compile(r'(Rp|RM|R\$)\s*/\s*(?=\d)', _re.IGNORECASE), lambda m: m.group(1) + '7'),
]


def _try_ocr_currency_token(token: str):
    """If `token` looks like a currency letter + OCR-confused digits (e.g. 'Bt'),
    return the corrected numeric string (e.g. 'B1'), else return None.

    Preserves the leading currency letter so clean_amount can strip it.
    """
    sign = ''
    t = token.strip()
    if t.startswith('-'):
        sign = '-'
        t = t[1:].lstrip()
    # Must start with a known currency-like letter
    m = _CURRENCY_LETTER_PREFIXES.match(t)
    if not m:
        return None
    currency_part = m.group(0)
    rest = t[m.end():]
    if not rest:
        return None
    # Heuristic: if rest has NO real digit, letters like O/o are misreads of 9 (not 0).
    # Rationale: OCR correctly outputs the digit '0' when it sees a zero; the LETTER 'O'
    # in numeric position means OCR confused the shape of '9' with 'O'.
    # When real digits exist alongside letters (e.g. '8so'), O→0 is still correct.
    if not _re.search(r'\d', rest):
        _token_map = str.maketrans({'O': '9', 'o': '9', 'S': '5', 's': '5',
                                    't': '1', 'T': '1', 'l': '1', 'I': '1',
                                    'Z': '2', 'z': '2', 'G': '6', 'g': '9', 'B': '8'})
    else:
        _token_map = _OCR_LETTER_TO_DIGIT
    corrected = rest.translate(_token_map)
    # Accept only if result is all digits (optionally with separators)
    if _re.fullmatch(r'[\d\.,]+', corrected):
        return sign + currency_part + corrected
    return None


def split_text_and_number(line: str):
    if not line:
        return "", ""

    # Normalize OCR-confused currency symbols before any parsing
    for _norm_pat, _norm_rep in _OCR_CURRENCY_NORMALIZE:
        line = _norm_pat.sub(_norm_rep, line)

    # Remove special | character that may interfere with OCR parsing, replacing it with a space to preserve word boundaries
    line = line.replace('|', '')

    # match number-like block (keep raw format including $, ₫, -, ., etc.)
    # Supports multi-char currency prefixes (Rp, RM, S$) as well as single-char
    # prefixes (฿, đ, d, ...) immediately before the digit sequence.
    # Also handles OCR spacing like 'd9 329' → collapsed to 'd9329'.
    # Extended char class after first digit: also allow oO (OCR zero→O confusion)
    # and sS (OCR digit→letter confusion in bold text like Rp80.000 → Rp8so.O00).
    num_pattern = r"(?:(?<=^)|(?<=\s))[-+]?\s*(?:Rp|RM|S\$|[^\w\s\|]|\w)?\s*\d[\d\.,\s oOsS]*"

    nums = _re.findall(num_pattern, line)

    # collapse internal whitespace in numeric token so 'd9 329' -> 'd9329'
    num = _re.sub(r"\s+", "", nums[-1]).strip() if nums else ''

    # Apply OCR letter→digit correction on the captured numeric token:
    # o/O → 0 (most common bold-text confusion), s/S → 5 then strip residual non-numeric.
    # E.g. "Rp8so.O00" → collapse spaces → "Rp8so.O00" → correct → "Rp850.000"
    #      "Rp8o.O00"  → correct → "Rp80.000" (most common case)
    # After correction, remove any remaining non-numeric chars (noise letters) so
    # "Rp8s0.000" (s was noise, not a real 5) still gives valid digits.
    if num:
        _pfx_m = _re.match(r'^([-+]?\s*(?:Rp|RM|S\$|B|[^\w\s])?\s*)', num)
        _pfx = _pfx_m.group(0) if _pfx_m else ''
        _body = num[len(_pfx):]
        # Bold-text OCR: a single "0" is sometimes read as two characters "so" or "sO".
        # Pattern: digit immediately followed by "s/S" then "o/O" → the "s" is OCR noise
        # for that zero. E.g. "8so" → "8o" → translate o→0 → "80".
        # This must run BEFORE the s→5 translate so we don't turn the noise "s" into "5".
        _body = _re.sub(r'(\d)[sS]([oO])', r'\1\2', _body)
        # Heuristic: if body has NO real digit, O/o are misreads of 9 (not 0).
        # OCR reads the digit '0' correctly; letter 'O' in numeric context = shape of '9'.
        # When real digits exist alongside O/o (e.g. '8o.O00'), keep O→0.
        if not _re.search(r'\d', _body):
            _body = _body.translate(str.maketrans({'o': '9', 'O': '9', 's': '5', 'S': '5'}))
        else:
            _body = _body.translate(str.maketrans({'o': '0', 'O': '0', 's': '5', 'S': '5'}))
        # strip any remaining non-numeric noise (but keep . , -)
        _body = _re.sub(r'[^\d.,\-]', '', _body)
        if _body:
            num = _pfx.strip() + _body

    # remove number block from text
    text_only = _re.sub(num_pattern, " ", line)

    # Fallback: primary regex missed because OCR confused digits with letters (e.g. "Bt" = "฿1").
    # Scan remaining words in text_only for a currency-prefixed OCR-confused token.
    if not num:
        for word in _re.split(r'\s+', line.strip()):
            corrected = _try_ocr_currency_token(word)
            if corrected:
                num = corrected
                text_only = line.replace(word, ' ')
                break

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
            is_total_key = (
                k == total_key
                or getattr(k, 'value', None) == getattr(total_key, 'value', object())
                or key_str == str(total_key)
            )
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
                'ocr_lines': parsed.get('__ocr_lines__', []) if isinstance(parsed, dict) else [],
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