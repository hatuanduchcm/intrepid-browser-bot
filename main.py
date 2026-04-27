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

    mapping = extract_order_index_map(sheet_id, sheet_name, output_path=orders_sheet_path)
    logger.info('Found %d orders to process', len(mapping))

    # 2) iterate — sort by venture first, then brand to group logins together
    last_venture = None
    login_failed_ventures: set = set()   # ventures where login failed — skip all orders for these
    items = list(mapping.items())
    def _sort_key(item):
        _, meta = item
        v = meta.get('Venture') or meta.get('venture') or ''
        b = meta.get('Brand Name') or meta.get('Brand') or ''
        return (str(v).strip().upper(), str(b).strip().lower())
    items.sort(key=_sort_key)
    for order_id, meta in items:
        venture = ''  # ensure defined in except block
        brand = ''    # ensure defined in except block
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
                    _stat('error', order_id=order_id, venture=venture, brand=brand,
                          error=f'Login thất bại: {e}',
                          crop_path=_screenshot_error(order_id, venture, 'login_failed'))
                    continue

            # ── Brand search ──────────────────────────────────────────────
            brand = meta.get('Brand Name') or meta.get('Brand')
            if brand:
                try:
                    logger.info('[%s] Searching brand: %s', order_id, brand)
                    found = handle_search_brand_event({'brand': brand})
                    if not found:
                        logger.error('[%s] ERROR — Brand not found: %s', order_id, brand)
                        _stat('error', order_id=order_id, venture=venture, brand=brand,
                              error=f'Brand không tìm thấy: {brand}',
                              crop_path=_screenshot_error(order_id, venture, 'brand_not_found'))
                        continue
                    logger.info('[%s] Brand found: %s', order_id, brand)
                except Exception as e:
                    logger.error('[%s] ERROR — Brand search exception: %s', order_id, e)
                    _stat('error', order_id=order_id, venture=venture, brand=brand,
                          error=f'Brand search lỗi: {e}',
                          crop_path=_screenshot_error(order_id, venture, 'brand_search_exc'))
                    continue

            # ── Order flow ────────────────────────────────────────────────
            logger.info('[%s] Opening order page …', order_id)
            result = handle_order_flow_event({'order_id': order_id, 'brand': brand, 'venture': venture})

            if not result.get('opened'):
                logger.error('[%s] ERROR — Order page không mở được', order_id)
                _stat('error', order_id=order_id, venture=venture, brand=brand,
                      error='Không mở được trang order',
                      crop_path=_screenshot_error(order_id, venture, 'order_not_opened'))
                continue

            adj = result.get('adjustment_text')
            if adj is None:
                logger.error('[%s] ERROR — Không tìm thấy adjustment data', order_id)
                _stat('error', order_id=order_id, venture=venture, brand=brand,
                      error='Không tìm thấy adjustment data',
                      crop_path=_screenshot_error(order_id, venture, 'no_adjustment'), ocr_lines=[])
                continue

            # ── Gather debug artefacts ────────────────────────────────────
            _ocr_lines = adj.get('__ocr_lines__', []) if isinstance(adj, dict) else []
            _rc = _debug_dir / f'return_compensation_{venture}_{order_id}.png'
            if _rc.exists():
                _crop_path = str(_rc)
            else:
                _pc = sorted(_debug_dir.glob('popup_crop_*.png'),
                             key=lambda p: p.stat().st_mtime, reverse=True)
                _crop_path = str(_pc[0]) if _pc else None

            # ── Total mismatch check ──────────────────────────────────────
            check = adj.get('__total_check__') if isinstance(adj, dict) else None
            if isinstance(check, dict) and not check.get('matches'):
                exp = check.get('expected_sum')
                got = check.get('total_value')
                logger.error('[%s] ERROR — Total mismatch: expected %s, sum of items %s', order_id, exp, got)
                _shot = _screenshot_error(order_id, venture, 'total_mismatch')
                _stat('error', order_id=order_id, venture=venture, brand=brand,
                      error=f'Total không khớp: expected {exp}, sum={got}',
                      crop_path=_crop_path or _shot, ocr_lines=_ocr_lines)
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
                _stat('error', order_id=order_id, venture=venture, brand=brand,
                      error='Không có data để ghi lên gsheet',
                      crop_path=_crop_path or _shot, ocr_lines=_ocr_lines)
                continue

            # ── Push to gsheet ────────────────────────────────────────────
            logger.info('[%s] Pushing to gsheet: %s', order_id, updates)
            try:
                update_columns_for_order(sheet_id, sheet_name, order_id, updates)
                logger.info('[%s] SUCCESS — gsheet updated: %s', order_id, updates)
                _stat('success', order_id=order_id, venture=venture, brand=brand)
            except Exception as e:
                logger.exception('[%s] ERROR — gsheet update failed: %s', order_id, e)
                _shot = _screenshot_error(order_id, venture, 'gsheet_fail')
                _stat('error', order_id=order_id, venture=venture, brand=brand,
                      error=f'gsheet update failed: {e}',
                      crop_path=_crop_path or _shot, ocr_lines=_ocr_lines)

        except Exception as e:
            _rc = _debug_dir / f'return_compensation_{venture}_{order_id}.png'
            _shot = _screenshot_error(order_id, venture, 'exception')
            _ecrop = str(_rc) if _rc.exists() else _shot
            logger.exception('[%s] EXCEPTION: %s', order_id, e)
            _stat('error', order_id=order_id, venture=venture, brand=brand,
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
