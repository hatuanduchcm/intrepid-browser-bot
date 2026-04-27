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


def handle_click_search_icon(event_payload, max_attempts: int = 5, retry_delay: float = 1.0):
    """Try to click the brand search icon.

    Retries up to `max_attempts` times with `retry_delay` seconds between each attempt,
    alternating between pywinauto button lookup and image-based locate.
    """
    asset = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', 'assets', 'icons', 'search-brand-icon.png'))

    for attempt in range(1, max_attempts + 1):
        try:
            w = get_intrepid_window()
            if not w:
                logger.warning('[search_icon] attempt %d/%d — Intrepid window not found', attempt, max_attempts)
                time.sleep(retry_delay)
                continue

            # ── Method 1: pywinauto button lookup ────────────────────────
            try:
                btn = w.child_window(title_re='Search|search|Kinh lup|Search by name', control_type='Button')
                if btn.exists():
                    btn.click_input()
                    time.sleep(0.2)
                    logger.debug('[search_icon] found via pywinauto on attempt %d', attempt)
                    return True
            except Exception as e:
                logger.debug('[search_icon] pywinauto lookup failed (attempt %d): %s', attempt, e)

            # ── Method 2: image-based locate with decreasing confidence ───
            if os.path.exists(asset):
                for conf in (0.8, 0.75):
                    if click_image(asset, confidence=conf):
                        time.sleep(0.4)
                        logger.debug('[search_icon] found via image at confidence=%.1f on attempt %d', conf, attempt)
                        return True
            else:
                logger.debug('[search_icon] asset missing: %s', asset)

            logger.warning('[search_icon] attempt %d/%d failed, retrying in %.1fs…', attempt, max_attempts, retry_delay)
            time.sleep(retry_delay)

        except Exception as e:
            logger.error('[search_icon] attempt %d/%d exception: %s', attempt, max_attempts, e)
            logger.debug(traceback.format_exc())
            time.sleep(retry_delay)

    logger.error('[search_icon] all %d attempts failed', max_attempts)
    return False
