"""Utility event to close the current browser/tab using Ctrl+W."""
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def close_tab_event(delay=0.08):
    """Send Ctrl+W to close the active tab/window.

    delay: optional small delay between key down and up to improve reliability.
    Returns True on success, False on failure.
    """
    try:
        import pyautogui
    except Exception:
        logger.debug('pyautogui not available; cannot close tab')
        return False

    # Prefer image-based close (click the rightmost/last close-tab icon) and
    # fall back to Ctrl+W if the icon is missing or the click fails.
    try:
        icon_path = Path(__file__).resolve().parents[1] / 'assets' / 'icons' / 'close-tab-icon.png'
        if icon_path.exists():
            try:
                matches = list(pyautogui.locateAllOnScreen(str(icon_path), confidence=0.8))
            except Exception as e:
                logger.debug('locateAllOnScreen failed for close-tab-icon: %s', e)
                matches = []

            if matches:
                # choose the rightmost match (largest center x) to target the last tab
                def center_x(m):
                    return m.left + (m.width // 2)

                best = max(matches, key=center_x)
                try:
                    cx = best.left + best.width // 2
                    cy = best.top + best.height // 2
                    pyautogui.moveTo(cx, cy, duration=0.12)
                    time.sleep(0.05)
                    pyautogui.click()
                    time.sleep(0.5)
                    return True
                except Exception as e:
                    logger.debug('clicking close-tab icon failed: %s', e)

        # fallback to keyboard shortcut
        pyautogui.keyDown('ctrl')
        time.sleep(delay)
        pyautogui.press('w')
        time.sleep(delay)
        pyautogui.keyUp('ctrl')
        return True
    except Exception as e:
        logger.debug('close_tab_event failed: %s', e, exc_info=True)
        return False
