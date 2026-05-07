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

    # try to get tooltip data using layered strategies, retry up to 3 times
    last_exception = None
    for attempt in range(3):
        logger.debug(f'handle_copy_adjustment_event: attempt={attempt}')
        try:
            crop_path = _hover_and_capture_tooltip(w, venture=venture, order_id=order_id)
            crop_path = crop_path if isinstance(crop_path, str) else None

            # OCR / parse pipeline handles all label types via ADJUSTMENT_COLUMNS
            text = get_tooltip_data(_path=crop_path, venture=venture)
            logger.debug(f'handle_copy_adjustment_event: attempt={attempt}, text={bool(text)}')
            if text:
                if attempt > 0:
                    logger.info(f"Adjustment found after {attempt+1} attempts")
                return text
        except Exception as e:
            last_exception = e
            logger.debug(f'copy_adjustment_failed (attempt {attempt+1}): %s', e)
        time.sleep(0.6 + 0.2 * attempt)  # Slightly longer wait each retry

    raise RuntimeError(f'Adjustment details not found after 3 attempts: {last_exception}')

from utils.split_text_and_number import split_text_and_number
from utils.amounts import add_negative_candidates

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
                    logger.debug('Found adjustment block via %s at (%s, %s)', _p.name, center_x, center_y)

                    # Scroll down until total_adjustment_amount_line is visible on screen.
                    # The ? icon only renders once the total row is in viewport.
                    total_tpl = _icons_dir / 'total_adjustment_amount_line.png'
                    if total_tpl.exists():
                        for _s in range(15):  # max 15 small steps (~450px)
                            try:
                                if pyautogui.locateOnScreen(str(total_tpl), confidence=0.75, grayscale=True):
                                    logger.debug('total_adjustment_amount_line visible after %d extra scrolls', _s)
                                    break
                            except Exception:
                                pass
                            pyautogui.scroll(-30)
                            time.sleep(0.12)
                    else:
                        # Fallback: one small nudge like before
                        pyautogui.scroll(-80)
                        time.sleep(0.15)

                    # Re-locate block header to get updated position after scrolling
                    try:
                        match2 = pyautogui.locateOnScreen(str(_p), confidence=confidence, grayscale=True)
                        if match2:
                            center_x = match2.left + match2.width // 2
                            center_y = match2.top + match2.height // 2
                    except Exception:
                        pass

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
                        if isinstance(parsed_variant, dict):
                            parsed_variant['__ocr_lines__'] = [l.strip() for l in txt.splitlines() if l.strip()]
                        chk = validate_total_adjustment_with_negatives(parsed_variant)
                        if isinstance(parsed_variant, dict):
                            parsed_variant['__total_check__'] = chk
                        # Only return if validation passed
                        if isinstance(chk, dict) and chk.get('matches'):
                            if isinstance(parsed_variant, dict) and '__source__' not in parsed_variant:
                                parsed_variant['__source__'] = 'ocr'
                            return parsed_variant
                    except Exception:
                        logger.debug('Failed to attach validation to parsed variant', exc_info=True)

        # OCR totally failed or all variants have matches=False — try Gemini AI fallback
        logger.debug('OCR produced no matched result for %s, trying Gemini fallback', _path)
        return _gemini_fallback(_path, venture=venture)

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
            check = validate_total_adjustment_with_negatives(parsed)
            if isinstance(parsed, dict):
                parsed['__total_check__'] = check
            if isinstance(check, dict) and check.get('matches'):
                if isinstance(parsed, dict) and '__source__' not in parsed:
                    parsed['__source__'] = 'ocr'
                return parsed
        except Exception:
            logger.debug('validate_total_adjustment_with_negatives raised for parsed mapping', exc_info=True)

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
                if isinstance(parsed_variant, dict) and '__source__' not in parsed_variant:
                    parsed_variant['__source__'] = 'ocr'
                return parsed_variant

    # persist OCR log for inspection
    try:
        (DEBUG_DIR / 'ocr_text.txt').write_text('\n\n'.join(f"[{k}]\n{v}" for k, v in ocr_log if v))
    except Exception:
        logger.debug('Failed to write ocr_text.txt')

    # --- Gemini AI fallback: OCR failed to produce a matched result ---
    gemini_result = _gemini_fallback(_path, venture=venture)
    if gemini_result is not None:
        logger.info('extract_adjustment_mapping_from_crop: using Gemini AI fallback result')
        return gemini_result

    # return best-effort fallback (validation + __total_check__ already attached)
    if isinstance(_best_effort[0], dict) and '__source__' not in _best_effort[0]:
        _best_effort[0]['__source__'] = 'ocr'
    return _best_effort[0]

def parse_lines_to_map(text: str, venture: str = ''):
    """Parse OCR text lines into a mapping ColumnName -> numeric string.

    Uses the simplified `ADJUSTMENT_COLUMNS` (ColumnName -> list of Shopee labels).
    """
    # Normalize known OCR typos before label matching
    _ocr_typos = [
        ('adiustment', 'adjustment'),
        ('adiust',     'adjust'),
        ('totai',      'total'),
        ('reiease',    'release'),
        ('amouni',     'amount'),
    ]
    normalized_lines = []
    for raw_line in text.splitlines():
        low = raw_line.lower()
        for wrong, right in _ocr_typos:
            low = low.replace(wrong, right)
        normalized_lines.append(low)
    # Re-build text preserving original case for number extraction, but use normalized for label
    lines = [l.strip() for l in normalized_lines if l.strip()]
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
            # Get all plausible candidates for this amount
            cleaned_candidates = clean_amount(numeric, venture=venture)
            mapping[best_cname] = cleaned_candidates

    return mapping


def _gemini_fallback(_path: Optional[str], venture: str = '') -> Optional[dict]:
    """Call Gemini AI to extract adjustment data when OCR fails or produces mismatched totals.

    Converts Gemini's JSON output (extracted_items + total_adjustment_amount_in_image)
    into the same ColumnName-keyed dict format used by the rest of the pipeline,
    with __ocr_lines__, __total_check__ attached.
    """
    if not _path:
        return None
    try:
        from utils.google_gemini_invoice import extract_shopee_invoice
        from gsheets.order_adjustment_sheet import ADJUSTMENT_COLUMNS, ColumnName
        from utils.amounts import clean_amount
    except Exception as e:
        logger.debug('Gemini fallback: import failed: %s', e)
        return None

    try:
        gemini_data = extract_shopee_invoice(_path)
    except Exception as e:
        logger.debug('Gemini fallback: extract_shopee_invoice failed: %s', e)
        return None

    if not isinstance(gemini_data, dict):
        return None

    extracted_items = gemini_data.get('extracted_items', [])
    total_in_image  = gemini_data.get('total_adjustment_amount_in_image')
    is_match        = gemini_data.get('is_match', False)

    if not extracted_items:
        return None

    # Build label -> ColumnName lookup (lowercase, longest-match-wins same as parse_lines_to_map)
    label_map = {
        cname: [lbl.strip().lower() for lbl in labs if lbl and isinstance(lbl, str)]
        for cname, labs in ADJUSTMENT_COLUMNS.items()
    }

    mapping = {}
    for item in extracted_items:
        item_name = (item.get('item_name') or '').strip().lower()
        amount    = item.get('amount')
        if not item_name or amount is None:
            continue
        # Match to ColumnName using longest label match
        best_cname, best_len = None, 0
        for cname, labs in label_map.items():
            for lab in labs:
                if lab in item_name and len(lab) > best_len:
                    best_cname, best_len = cname, len(lab)
        if best_cname is not None:
            # Gemini already returns clean numbers; store as string list for compatibility
            mapping[best_cname] = [str(amount)]

    if not mapping:
        return None

    # Attach Total Adjustment Amount
    if total_in_image is not None:
        mapping[ColumnName.TOTAL_ADJUSTMENT_AMOUNT] = [str(total_in_image)]

    # Attach __ocr_lines__ (synthesized from Gemini items for traceability)
    mapping['__ocr_lines__'] = [
        f"{item.get('item_name', '')} {item.get('amount', '')}"
        for item in extracted_items
    ]
    mapping['__gemini__'] = True  # mark as Gemini-sourced
    mapping['__source__'] = 'gemini'

    # Validate totals using same logic as OCR path
    try:
        check = validate_total_adjustment_with_negatives(mapping)
        mapping['__total_check__'] = check
    except Exception as e:
        logger.debug('Gemini fallback: validate_total_adjustment failed: %s', e)
        # Gemini already verified is_match; use it as fallback
        if total_in_image is not None:
            mapping['__total_check__'] = {
                'expected_sum': int(total_in_image),
                'total_value':  int(total_in_image),
                'matches':      bool(is_match),
            }

    return mapping


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


    def to_num(s, venture=None):
        if not s:
            return Decimal(0)
        ss = str(s)
        # For PH: only remove commas, keep dot as decimal separator
        # For others: remove both dot and comma
        if venture and str(venture).upper() == 'PH':
            ss = ss.replace(',', '').replace('₫', '').replace('đ', '')
        else:
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

    # Try to get venture from parsed if available, else default to None
    venture = parsed.get('__venture__', None)
    # Helper: for PH, convert decimal string to integer centavos (multiply by 100)
    def to_int_cents(val, venture):
        if venture and str(venture).upper() == 'PH':
            return int((Decimal(val) * 100).to_integral_value(rounding=ROUND_HALF_UP))
        return int(Decimal(val).to_integral_value(rounding=ROUND_HALF_UP))

    # allow keys as enum, string(enum), or header string
    # Try to get venture from parsed if available, else default to None
    venture = parsed.get('__venture__', None)

    # Step 1: Build total_candidates list (all possible total values)
    total_val_raw = parsed.get(total_key)
    if isinstance(total_val_raw, list):
        total_candidates = [to_num(v, venture) for v in total_val_raw]
    elif total_key in parsed:
        total_candidates = [to_num(total_val_raw, venture)]
    else:
        try:
            from gsheets.order_adjustment_sheet import GSHEET_COLUMN
            header = GSHEET_COLUMN.get(total_key)
        except Exception:
            header = None
        if str(total_key) in parsed:
            total_candidates = [to_num(parsed.get(str(total_key)), venture)]
        elif header and header in parsed:
            total_candidates = [to_num(parsed.get(header), venture)]
        else:
            total_candidates = [to_num(parsed.get(total_key, '0'), venture)]
    # Use first candidate as default (for fallback reporting)
    total_val = total_candidates[0] if total_candidates else Decimal(0)

    # Step 2: Build candidate lists for each key (excluding total and debug keys)
    from itertools import product
    candidate_keys = []
    candidate_lists = []
    for k, v in parsed.items():
        key_str = str(k)
        # skip internal/debug keys and total key
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
        # v is a list of candidates or a string
        if isinstance(v, list):
            candidate_lists.append(v)
        else:
            candidate_lists.append([v])
        candidate_keys.append(k)

    # Step 3: Try all combinations of item candidates × total candidates
    found = False
    best_combo = None
    matched_total_val = total_val
    for total_candidate in total_candidates:
        for combo in product(*candidate_lists):
            s = Decimal(0)
            for idx, val in enumerate(combo):
                try:
                    nv = to_num(val, venture)
                except Exception:
                    nv = Decimal(0)
                s += nv
            try:
                sum_others_int = to_int_cents(s, venture)
                total_val_int = to_int_cents(total_candidate, venture)
            except Exception:
                sum_others_int = int(s)
                total_val_int = int(total_candidate)
            if total_val_int == sum_others_int:
                found = True
                best_combo = combo
                matched_total_val = total_candidate
                break
        if found:
            break

    # Step 4: If found, update parsed with the chosen values
    if found and best_combo is not None:
        for idx, k in enumerate(candidate_keys):
            parsed[k] = best_combo[idx]
        # update total key to the matched candidate
        parsed[total_key] = str(matched_total_val) if not isinstance(total_val_raw, list) else str(matched_total_val)
        sum_others_int = to_int_cents(sum([to_num(v, venture) for v in best_combo]), venture)
        total_val_int = to_int_cents(matched_total_val, venture)
        return {'expected_sum': int(total_val_int), 'total_value': int(sum_others_int), 'matches': True}

    # If not found, log as before (using first candidate for each key)
    s = Decimal(0)
    converted_map = {}
    for idx, k in enumerate(candidate_keys):
        v = candidate_lists[idx][0]
        try:
            nv = to_num(v, venture)
        except Exception:
            nv = Decimal(0)
        converted_map[str(k)] = to_int_cents(nv, venture)
        s += nv
    try:
        sum_others_int = to_int_cents(s, venture)
        total_val_int = to_int_cents(total_val, venture)
    except Exception:
        sum_others_int = int(s)
        total_val_int = int(total_val)
    matches = (total_val_int == sum_others_int)
    if not matches:
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
                f.write(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
                f.write("---\n")
        except Exception:
            logger.exception('Failed to write adjustment validation error')
    return {'expected_sum': int(total_val_int), 'total_value': int(sum_others_int), 'matches': matches}

def validate_total_adjustment_with_negatives(parsed: dict):
    """
    Gọi validate_total_adjustment. Nếu không matches, thử sinh thêm số âm cho từng candidate list rồi validate lại.
    Trả về dict kết quả validate (có thể đã matches sau khi thêm số âm).
    """
    check = validate_total_adjustment(parsed)
    if isinstance(check, dict) and not check.get('matches'):
        changed = False
        for k, v in parsed.items():
            if isinstance(v, list):
                new_v = add_negative_candidates(v)
                if len(new_v) > len(v):
                    parsed[k] = new_v
                    changed = True
        if changed:
            check2 = validate_total_adjustment(parsed)
            return check2
    return check