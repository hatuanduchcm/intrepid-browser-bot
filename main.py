"""Repository entrypoint — runs the Invoice Adjustment bot from project root.
"""
from dotenv import load_dotenv
from pathlib import Path
from auth.handler_login import handle_login_event, handle_logout
from brand.handler_search_brand import handle_search_brand_event
from order.handler_order_flow import handle_order_flow_event
from gsheets.order_adjustment_sheet import extract_order_index_map, update_columns_for_order
import logging
from brand.handler_search_brand import handle_search_brand_event

logger = logging.getLogger(__name__)


def run_batch_process(sheet_id: str, sheet_name: str, orders_sheet_path: str = None, stats_queue=None):
    """Orchestrate batch processing:

    1. Extract order index map from the given sheet (order -> row/index and metadata).Browser
    
    2. Loop over each order_id and fetch adjustment info
    3. After processing, upload relevant adjustment info back to the sheet via `update_columns_for_order`.

    `sheet_id` and `sheet_name` identify the Google Sheet to read/write.
    """
    # 1) extract mapping
    _debug_dir = Path(__file__).parent / 'assets' / 'debug_matches'

    def _stat(event: str, **kw):
        if stats_queue is not None:
            try:
                stats_queue.put_nowait({'type': 'stat', 'event': event, **kw})
            except Exception:
                pass

    def _screenshot_error(order_id: str, venture: str, reason: str) -> str | None:
        """Take a full-screen screenshot, save to debug_matches, return path."""
        try:
            import pyautogui
            safe_reason = reason[:40].replace(' ', '_').replace('/', '-') if reason else 'error'
            shot_path = _debug_dir / f'error_{venture}_{order_id}_{safe_reason}.png'
            pyautogui.screenshot(str(shot_path))
            logger.debug('[%s] Error screenshot saved: %s', order_id, shot_path)
            return str(shot_path)
        except Exception as e:
            logger.debug('[%s] Failed to capture error screenshot: %s', order_id, e)
            return None

    def _latest_debug_image(order_id: str = '') -> str | None:
        """Return the most recently saved adjustment debug image for the given order_id.
        Falls back to the most recent image overall if no order_id match found."""
        # prefer files that contain order_id in the name (exact match)
        if order_id:
            order_candidates = [
                *_debug_dir.glob(f'adjustment_area_{order_id}_*.png'),
                *_debug_dir.glob(f'popup_crop_{order_id}_*.png'),
            ]
            if order_candidates:
                return str(max(order_candidates, key=lambda p: p.stat().st_mtime))
        # fallback: latest any adjustment image
        candidates = [
            *_debug_dir.glob('adjustment_area_*.png'),
            *_debug_dir.glob('popup_crop_*.png'),
        ]
        if not candidates:
            return None
        return str(max(candidates, key=lambda p: p.stat().st_mtime))

    mapping = extract_order_index_map(sheet_id, sheet_name, output_path=orders_sheet_path)
    logger.info('Found %d orders to process', len(mapping))

    # 2) iterate — sort by venture first, then platform to group logins together
    import os
    selected_ventures = os.getenv('SELECTED_VENTURES')
    selected_ventures_set = set(v.strip().upper() for v in selected_ventures.split(',')) if selected_ventures else None

    last_venture = None
    login_failed_ventures: set = set()   # ventures where login failed — skip all orders for these
    items = list(mapping.items())
    def _sort_key(item):
        _, meta = item
        v = meta.get('Venture') or meta.get('venture') or ''
        b = meta.get('Platform') or ''
        return (str(v).strip().upper(), str(b).strip().lower())
    items.sort(key=_sort_key)
    for order_id, meta in items:
        venture = (meta.get('Venture') or meta.get('venture') or '').strip().upper()
        # Lọc theo danh sách venture được chọn
        if selected_ventures_set is not None and venture not in selected_ventures_set:
            logger.info('[%s] SKIP — Venture %s không nằm trong danh sách được chọn', order_id, venture)
            _stat('skip', order_id=order_id, venture=venture)
            continue
        venture = ''  # ensure defined in except block
        platform = ''  # ensure defined in except block
        try:
            logger.info('─' * 60)
            logger.info('[%s] Start — row %s', order_id, meta.get('index'))

            # ── Skip if Total check == 0 ──────────────────────────────────
            total_check_raw = meta.get('Total check', '')
            try:
                total_check_val = float(str(total_check_raw).replace(',', '.').strip()) if total_check_raw else None
            except Exception:
                total_check_val = None
            if total_check_val is not None and total_check_val == 0:
                logger.info('[%s] SKIP — Total check = 0', order_id)
                _stat('skip', order_id=order_id,
                      venture=(meta.get('Venture') or meta.get('venture') or '').strip().upper())
                continue

            venture = (meta.get('Venture') or meta.get('venture') or '').strip().upper()
            logger.info('[%s] Venture: %s', order_id, venture)

            # ── Skip venture với login đã fail trước đó ──────────────────
            if venture and venture in login_failed_ventures:
                logger.error('[%s] SKIP — Login đã thất bại cho venture %s, bỏ qua order này', order_id, venture)
                _stat('error', order_id=order_id, venture=venture,
                      error=f'Login thất bại cho venture {venture} (bỏ qua)')
                continue

            # ── Login / re-login ──────────────────────────────────────────
            if venture and venture != last_venture:
                try:
                    if last_venture is not None:
                        logger.info('[%s] Venture changed %s → %s, logging out', order_id, last_venture, venture)
                        handle_logout()
                    logger.info('[%s] Logging in for %s', order_id, venture)
                    handle_login_event({'venture': venture})
                    last_venture = venture
                except Exception as e:
                    logger.error('[%s] ERROR — Login thất bại cho %s: %s', order_id, venture, e)
                    login_failed_ventures.add(venture)
                    _stat('error', order_id=order_id, venture=venture, brand=platform,
                          error=f'Login thất bại: {e}',
                          crop_path=_screenshot_error(order_id, venture, 'login_failed'))
                    continue

            # ── Platform search ──────────────────────────────────────────────
            platform = meta.get('Platform')
            if not platform or not str(platform).strip():
                logger.info('[%s] SKIP — Platform empty', order_id)
                _stat('skip', order_id=order_id, venture=venture, brand=platform)
                continue
            try:
                logger.info('[%s] Searching platform: %s', order_id, platform)
                found = handle_search_brand_event({'brand': platform})
                if not found:
                    logger.error('[%s] ERROR — Platform not found: %s', order_id, platform)
                    _stat('error', order_id=order_id, venture=venture, brand=platform,
                          error=f'Platform không tìm thấy: {platform}',
                          crop_path=_screenshot_error(order_id, venture, 'platform_not_found'))
                    continue
                logger.info('[%s] Platform found: %s', order_id, platform)
            except Exception as e:
                logger.error('[%s] ERROR — Platform search exception: %s', order_id, e)
                _stat('error', order_id=order_id, venture=venture, brand=platform,
                      error=f'Platform search lỗi: {e}',
                      crop_path=_screenshot_error(order_id, venture, 'platform_search_exc'))
                continue

            # ── Order flow ────────────────────────────────────────────────
            logger.info('[%s] Opening order page …', order_id)
            result = handle_order_flow_event({'order_id': order_id, 'brand': platform, 'venture': venture})

            if not result.get('opened'):
                logger.error('[%s] ERROR — Order page không mở được', order_id)
                _stat('error', order_id=order_id, venture=venture, brand=platform,
                      error='Không mở được trang order',
                      crop_path=_screenshot_error(order_id, venture, 'order_not_opened'))
                continue

            adj = result.get('adjustment_text')
            if adj is None:
                logger.error('[%s] ERROR — Không tìm thấy adjustment data', order_id)
                # prefer the debug image captured during adjustment search (shows the actual state)
                _no_adj_crop = _latest_debug_image(order_id) or _screenshot_error(order_id, venture, 'no_adjustment')
                _stat('error', order_id=order_id, venture=venture, brand=platform,
                    error='Không tìm thấy adjustment data',
                    crop_path=_no_adj_crop, ocr_lines=[], parsed_mapping=None)
                continue

            # ── Gather debug artefacts ────────────────────────────────────
            _ocr_lines = adj.get('__ocr_lines__', []) if isinstance(adj, dict) else []
            # Extract parsed mapping for debug (exclude __ keys)
            parsed_mapping = None
            if isinstance(adj, dict):
                parsed_mapping = {k: v for k, v in adj.items() if not str(k).startswith('__')}
            # Use the crop path embedded in the adj dict (per-order, set during OCR)
            # Fall back to latest debug image only if not available
            _crop_path = (adj.get('__crop_path__') if isinstance(adj, dict) else None) or _latest_debug_image(order_id)

            # ── Total mismatch check ──────────────────────────────────────
            check = adj.get('__total_check__') if isinstance(adj, dict) else None
            if isinstance(check, dict) and not check.get('matches'):
                exp = check.get('expected_sum', 0)
                got = check.get('total_value')
                if exp == 0:
                    # expected_sum==0 means OCR couldn't read the bold total row — not a real
                    # mismatch. Proceed with the adjustment item values found.
                    logger.warning('[%s] WARN — Total row OCR failed (expected=0, sum=%s); proceeding with item values', order_id, got)
                else:
                    logger.error('[%s] ERROR — Total mismatch: expected %s, sum of items %s', order_id, exp, got)
                    _shot = _screenshot_error(order_id, venture, 'total_mismatch')
                    _stat('error', order_id=order_id, venture=venture, brand=platform,
                          error=f'Total không khớp: expected {exp}, sum={got}',
                          crop_path=_crop_path or _shot, ocr_lines=_ocr_lines, parsed_mapping=parsed_mapping)
                    continue

            # ── Build gsheet update dict ───────────────────────────────────
            from gsheets.order_adjustment_sheet import GSHEET_COLUMN
            updates = {}
            if isinstance(adj, dict):
                for k, v in adj.items():
                    if str(k).startswith('__'):
                        continue
                    try:
                        key = GSHEET_COLUMN.get(k) if not isinstance(k, str) else None
                        if key:
                            updates[key] = str(v)
                    except Exception:
                        continue

            if not updates:
                logger.error('[%s] ERROR — Không build được updates từ adj: %s', order_id,
                         {str(k): v for k, v in adj.items() if not str(k).startswith('__')} if isinstance(adj, dict) else adj)
                _shot = _screenshot_error(order_id, venture, 'no_updates')
                _stat('error', order_id=order_id, venture=venture, brand=platform,
                    error='Không có data để ghi lên gsheet',
                    crop_path=_crop_path or _shot, ocr_lines=_ocr_lines, parsed_mapping=parsed_mapping)
                continue

            # ── Push to gsheet ────────────────────────────────────────────
            logger.info('[%s] Pushing to gsheet: %s', order_id, updates)
            try:
                update_columns_for_order(sheet_id, sheet_name, order_id, updates, row_number=meta.get('index'))
                logger.info('[%s] SUCCESS — gsheet updated: %s', order_id, updates)
                _stat('success', order_id=order_id, venture=venture, brand=platform)
            except Exception as e:
                logger.exception('[%s] ERROR — gsheet update failed: %s', order_id, e)
                _shot = _screenshot_error(order_id, venture, 'gsheet_fail')
                _stat('error', order_id=order_id, venture=venture, brand=platform,
                      error=f'gsheet update failed: {e}',
                      crop_path=_crop_path or _shot, ocr_lines=_ocr_lines)

        except Exception as e:
            _rc = _debug_dir / f'return_compensation_{venture}_{order_id}.png'
            _shot = _screenshot_error(order_id, venture, 'exception')
            _ecrop = str(_rc) if _rc.exists() else _shot
            logger.exception('[%s] EXCEPTION: %s', order_id, e)
            _stat('error', order_id=order_id, venture=venture, brand=platform,
                  error=str(e), crop_path=_ecrop, ocr_lines=[])

    # Logout after all orders processed
    try:
        logger.info('All orders done — logging out')
        handle_logout()
    except Exception as e:
        logger.warning('Logout failed: %s', e)

    logger.info('Batch processing complete')

import logging

# Configure root logger to show debug messages on console during development
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(name)s:%(message)s')

env_path = Path('.') / '.env'
load_dotenv(env_path)



def main():
    # clear validation errors from previous run once at startup
    try:
        _err_file = Path('.') / 'assets' / 'debug_matches' / 'adjustment_validation_errors.jsonl'
        if _err_file.exists():
            _err_file.unlink()
    except Exception:
        pass

    try:
        # handle_login_event({'venture': 'VN'})
        # Example: run brand search
        # handle_search_brand_event({'brand': 'OATSIDE'})

        # res = handle_order_flow_event({'order_id': '2603264PETUQB4'})
        # print('Order flow result:', res)
        # If SHEET_ID/SHEET_NAME provided in env, run batch process; otherwise run example flow
        import os
        sheet_id = os.getenv('GSHEET_ID')
        sheet_name = os.getenv('GSHEET_SHEET_NAME')
        if sheet_id and sheet_name:
            print('Running batch process for', sheet_id, sheet_name)
            run_batch_process(sheet_id, sheet_name)
        else:
            logging.info('GSHEET_ID or GSHEET_SHEET_NAME not set in environment; skipping batch process and running example flow')
            # handle_login_event({'venture': 'VN'})
            # # Example: run brand search
            # handle_search_brand_event({'brand': 'OATSIDE'})
            # res = handle_order_flow_event({'order_id': '2603264PETUQB4'})
            # print('Order flow result:', res)
    except Exception as e:
        print('Errors:', e)


if __name__ == '__main__':
    main()
