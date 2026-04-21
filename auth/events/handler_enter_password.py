from utils.window import get_intrepid_window
from pathlib import Path
import pyautogui
import time
import logging

logger = logging.getLogger(__name__)

_ICONS = Path(__file__).resolve().parents[2] / 'assets' / 'icons'
_PASSWORD_BOX_IMG = _ICONS / 'sign-in-password.png'

_MAX_FIND_ATTEMPTS = 5
_FIND_DELAY = 1.0


def _locate_password_box():
    """Try to locate the sign-in password box on screen. Returns location or None."""
    if not _PASSWORD_BOX_IMG.exists():
        logger.debug('sign-in-password.png not found at %s', _PASSWORD_BOX_IMG)
        return None
    for attempt in range(1, _MAX_FIND_ATTEMPTS + 1):
        try:
            loc = pyautogui.locateCenterOnScreen(str(_PASSWORD_BOX_IMG), confidence=0.8)
            if loc:
                logger.debug('Found password box on attempt %d', attempt)
                return loc
        except Exception as e:
            logger.debug('locateCenterOnScreen error (attempt %d): %s', attempt, e)
        time.sleep(_FIND_DELAY)
    return None


def handle_enter_password(event_payload):
    password = event_payload.get('password')

    # --- image-based approach ---
    loc = _locate_password_box()
    if loc:
        try:
            pyautogui.click(loc.x, loc.y)
            time.sleep(0.3)
            pyautogui.hotkey('ctrl', 'a')
            pyautogui.typewrite(password, interval=0.05)
            time.sleep(0.5)
            return True
        except Exception as e:
            logger.debug('image-based password entry failed: %s', e)

    # --- fallback: control-based approach ---
    try:
        w = get_intrepid_window()
        if not w:
            raise RuntimeError('Intrepid window not found')
        time.sleep(0.5)
        pwd_edit = w.child_window(control_type='Edit', found_index=0)
        pwd_edit.set_text(password)
        time.sleep(0.5)
        return True
    except Exception as e:
        raise RuntimeError(f"enter_password failed: {e}")

