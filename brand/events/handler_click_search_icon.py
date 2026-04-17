from utils.window import get_intrepid_window
import time
from pywinauto import mouse
import os
import pyautogui
import logging
import traceback

logger = logging.getLogger(__name__)


def click_image(template_path: str, confidence: float = 0.8, retries: int = 3, delay: float = 0.2) -> bool:
    """Locate `template_path` on screen using pyautogui and click its center.
    Returns True if clicked, False otherwise. Retries a few times.
    """
    if not os.path.exists(template_path):
        logger.debug('Template not found: %s', template_path)
        return False

    for attempt in range(retries):
        try:
            loc = pyautogui.locateOnScreen(template_path, confidence=confidence)
            if loc:
                cx, cy = pyautogui.center(loc)
                pyautogui.click(cx, cy)
                return True
        except Exception as e:
            logger.debug('pyautogui locate attempt %d failed: %s', attempt + 1, e)
        time.sleep(delay)
    return False


def handle_click_search_icon(event_payload):
    try:
        w = get_intrepid_window()
        logger.debug('Intrepid window object: %s', repr(w))
        if not w:
            raise RuntimeError('Intrepid window not found')
        # find the search icon button (left sidebar magnifier)
        try:
            btn = w.child_window(title_re='Search|search|Kinh lup|Search by name', control_type='Button')
            exists = False
            try:
                exists = btn.exists()
            except Exception as ex_inner:
                logger.debug('Error calling btn.exists(): %s', ex_inner)
            logger.debug('Search button lookup exists=%s btn=%s', exists, repr(btn))
            if exists:
                try:
                    btn.click_input()
                    time.sleep(0.2)
                    return True
                except Exception as click_err:
                    logger.warning('click_input on btn failed: %s', click_err)
        except Exception as lookup_err:
            logger.debug('Error looking up search button: %s', lookup_err)
        # fallback: try image-based locate of the search icon
        try:
            asset = os.path.join(os.path.dirname(__file__), '..', '..', 'assets', 'icons', 'search-brand-icon.png')
            asset = os.path.normpath(asset)
            if not os.path.exists(asset):
                logger.debug('Search icon asset missing: %s', asset)
            else:
                if click_image(asset, confidence=0.8):
                    time.sleep(0.2)
                    return True
        except Exception as inner_e:
            logger.warning('Image fallback for search icon failed: %s', inner_e)
            logger.debug(traceback.format_exc())
    except Exception as e:
        # Log full traceback for easier debugging and re-raise with context
        logger.error('click_search_icon failed: %s', e)
        logger.debug(traceback.format_exc())
        raise RuntimeError(f'click_search_icon failed: {e}')
