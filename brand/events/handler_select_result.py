from utils.window import get_intrepid_window
import time
import logging
from pathlib import Path
import pyautogui
import json

def enter_brand_in_search_box(event_payload):
    query = event_payload.get('query')
    try:
        w = get_intrepid_window()
        if not w:
            raise RuntimeError('Intrepid window not found')

        # Primary: try control-based lookup
        # try:
        #     item = w.child_window(title_re=f'.*{query}.*', control_type='Text')
        #     if item and item.exists():
        #         try:
        #             parent = item.parent()
        #             parent.click_input()
        #         except Exception:
        #             item.click_input()
        #         time.sleep(0.3)
        #         # type the query into the focused search box (best-effort)
        #         pyautogui.write(query, interval=0.02)
        #         pyautogui.press('enter')
        #         _click_brand_icon()
        #         time.sleep(0.2)
        #         return True
        # except Exception:
        #     logging.debug('Control lookup for select_result failed, falling back to image search')

        base_icons = Path(__file__).resolve().parents[2] / 'assets' / 'icons'
        # Try default image first, then a larger-size fallback if available
        img_candidates = [base_icons / 'brand_search_box.png', base_icons / 'brand_search_box_big_size.png']

        deadline = time.time() + 2.0
        while time.time() < deadline:
            logging.debug('Attempting image search fallback for select_result, query="%s"', query)
            for img in img_candidates:
                logging.debug('Trying image %s for brand search box', img.name)
                try:
                    if not img.exists():
                        logging.debug('%s not found, skipping', img.name)
                        continue
                    loc = pyautogui.locateCenterOnScreen(str(img), confidence=0.8)
                    if loc:
                        logging.debug('Found brand search result image (%s) at %s, clicking', img.name, loc)
                        # ensure window is focused before interacting
                        try:
                            w.set_focus()
                        except Exception:
                            logging.debug('Failed to set focus to Intrepid window before clicking image')
                        # move to point then click to reduce misses
                        try:
                            pyautogui.moveTo(loc.x, loc.y, duration=0.12)
                            pyautogui.click(loc.x, loc.y)
                        except Exception:
                            pyautogui.click(loc.x, loc.y)
                            logging.debug('Failed to move to image location, performed direct click instead')

                        try:
                            from utils.debug_click import save_last_search_click
                            save_last_search_click(loc.x, loc.y)
                        except Exception as ex:
                            logging.debug('Failed to write debug click coordinates via util: %s', ex)

                        time.sleep(0.5)
                        # type the query into the box
                        try:
                            pyautogui.write(query, interval=0.02)
                            pyautogui.press('enter')
                            time.sleep(0.2)
                        except Exception:
                            logging.debug('Failed to type query after image click')
                        return True
                    else:
                        logging.debug('%s not found on screen', img.name)
                except Exception as e:
                    logging.debug('Error during image locate/click fallback for %s: %s', img.name, e)
            time.sleep(0.2)

        logging.debug('Image fallback failed to find brand_search_box')
        # save full-screen debug screenshot for analysis
        try:
            from datetime import datetime
            debug_dir = Path(__file__).resolve().parents[3] / 'assets' / 'debug_matches'
            debug_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            shot_path = debug_dir / f'select_result_brand_search_box_fail_{ts}.png'
            try:
                img_full = pyautogui.screenshot()
                img_full.save(str(shot_path))
                logging.debug('Wrote debug screenshot to %s', shot_path)
            except Exception as e:
                logging.debug('Failed to save debug screenshot: %s', e)
        except Exception:
            pass

        return False
    except Exception as e:
        raise RuntimeError(f'select_result failed: {e}')

# helpers relocated to brand/events/search_helpers.py