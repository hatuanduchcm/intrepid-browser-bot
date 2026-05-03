from utils.window import get_intrepid_window
from pathlib import Path
import pyautogui
import time
import logging

logger = logging.getLogger(__name__)

_ICONS = Path(__file__).resolve().parents[2] / 'assets' / 'icons'
_EMAIL_BOX_IMG = _ICONS / 'sign-in-email-box.png'
_RELOAD_IMG = _ICONS / 'reload-app-icon.png'
_RELOAD_IMG2 = _ICONS / 'reload-app-icon2.png'

_MAX_FIND_ATTEMPTS = 5
_FIND_DELAY = 1.0


def _locate_email_box():
    """Try to locate the sign-in email box on screen. Returns location or None."""
    if not _EMAIL_BOX_IMG.exists():
        logger.debug('sign-in-email-box.png not found at %s', _EMAIL_BOX_IMG)
        return None
    for attempt in range(1, _MAX_FIND_ATTEMPTS + 1):
        try:
            loc = pyautogui.locateCenterOnScreen(str(_EMAIL_BOX_IMG), confidence=0.8)
            if loc:
                logger.debug('Found email box on attempt %d', attempt)
                return loc
        except Exception as e:
            logger.debug('locateCenterOnScreen error (attempt %d): %s', attempt, e)
        time.sleep(_FIND_DELAY)
    return None


def _try_reload_app():
    """Click reload-app-icon or reload-app-icon2 if found. Returns True if clicked."""
    img_paths = []
    if _RELOAD_IMG.exists():
        img_paths.append(_RELOAD_IMG)
    if _RELOAD_IMG2.exists():
        img_paths.append(_RELOAD_IMG2)
    if not img_paths:
        logger.debug('No reload-app-icon found at %s or %s', _RELOAD_IMG, _RELOAD_IMG2)
        return False
    for img_path in img_paths:
        try:
            loc = pyautogui.locateCenterOnScreen(str(img_path), confidence=0.8)
            if loc:
                pyautogui.click(loc.x, loc.y)
                logger.info('Clicked %s, waiting for app to reload', img_path.name)
                time.sleep(3.0)
                return True
        except Exception as e:
            logger.debug('reload icon locate/click failed for %s: %s', img_path, e)
    return False


def handle_enter_email(event_payload):
    username = event_payload.get('username')

    # --- image-based approach ---
    loc = _locate_email_box()
    if not loc:
        logger.info('Email box not found; attempting reload and retry')
        _try_reload_app()
        loc = _locate_email_box()

    if loc:
        try:
            pyautogui.click(loc.x, loc.y)
            time.sleep(0.3)
            pyautogui.hotkey('ctrl', 'a')
            pyautogui.typewrite(username, interval=0.05)
            time.sleep(0.5)
            return True
        except Exception as e:
            logger.debug('image-based email entry failed: %s', e)

    # --- fallback: control-based approach ---
    try:
        w = get_intrepid_window()
        if not w:
            raise RuntimeError('Intrepid window not found')
        time.sleep(0.5)
        email_edit = w.child_window(control_type='Edit', found_index=0)
        email_edit.set_text(username)
        time.sleep(0.5)
        return True
    except Exception as e:
        raise RuntimeError(f"enter_email failed: {e}")

