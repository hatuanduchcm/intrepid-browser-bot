"""Utility event to close the current browser/tab using Ctrl+W."""
import logging
import time

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

    try:
        # Press Ctrl+W
        pyautogui.keyDown('ctrl')
        time.sleep(delay)
        pyautogui.press('w')
        time.sleep(delay)
        pyautogui.keyUp('ctrl')
        return True
    except Exception as e:
        logger.debug('close_tab_event failed: %s', e, exc_info=True)
        return False
