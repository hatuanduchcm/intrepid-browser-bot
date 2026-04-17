from pywinauto import Desktop
from pywinauto.keyboard import send_keys
import time
import os
from pathlib import Path
import logging

from auth.events.handler_enter_email import handle_enter_email
from auth.events.handler_click_next import handle_click_next
from auth.events.handler_enter_password import handle_enter_password
from auth.events.handler_submit import handle_submit


def _env_for_region(region: str):
    user_key = f'INTREPID_USER_{region.upper()}'
    user = os.getenv(user_key)
    pwd = os.getenv(f'INTREPID_PASS_{region.upper()}') or os.getenv('INTREPID_PASS')
    return user, pwd


def launch_via_windows_search(app_name: str = 'IntrepidBrowser'):
    try:
        send_keys('{LWIN}')
    except Exception:
        try:
            send_keys('{VK_LWIN}')
        except Exception:
            return False
    time.sleep(0.4)
    send_keys(app_name)
    time.sleep(0.3)
    send_keys('{ENTER}')
    return True


def _is_already_logged_in(timeout: float = 1.0) -> bool:
    """Best-effort check whether Intrepid is already logged in by
    looking for a logout/profile icon on screen. Returns True if found.
    """
    try:
        import pyautogui
    except Exception:
        return False
    base_icons = Path(__file__).resolve().parents[1] / 'assets' / 'icons'
    logout_icon = base_icons / 'logout-icon.png'
    if not logout_icon.exists():
        logging.debug('Logout icon not found at %s', logout_icon)
        return False
    deadline = time.time() + float(timeout)
    while time.time() < deadline:
        try:
            loc = pyautogui.locateOnScreen(str(logout_icon), confidence=0.8)
            if loc:
                return True
            else:
                logging.debug('Logout icon not found on screen')
        except Exception:
            pass
        time.sleep(0.1)
    return False


def find_intrepid_window(timeout=10):
    d = Desktop(backend='uia')
    deadline = time.time() + timeout
    while time.time() < deadline:
        wins = d.windows()
        for w in wins:
            try:
                if 'intrepid' in w.window_text().lower():
                    w.set_focus()
                    return w
            except Exception:
                continue
        time.sleep(0.5)
    return None


def start_and_login(region: str = 'MY', username_val: str = None, password_val: str = None):
    # happy-path: attempt to open app, then run per-step handlers sequentially
    launch_via_windows_search('IntrepidBrowser')

    # If app is already logged in (logout/profile icon present), skip login steps
    try:
        if _is_already_logged_in(timeout=1.0):
            return True
    except Exception:
        pass

    if not handle_enter_email({'username': username_val}):
        raise RuntimeError('Failed to enter email')

    time.sleep(0.6)

    if not handle_click_next({}):
        raise RuntimeError('Failed to click next')

    time.sleep(0.6)

    if not handle_enter_password({'password': password_val}):
        raise RuntimeError('Failed to enter password')

    if not handle_submit({}):
        raise RuntimeError('Failed to submit')

    return True


def handle_login_event(event_payload):
    region = event_payload.get('region')
    username_val, password_val = _env_for_region(region)
    if not username_val or not password_val:
        raise RuntimeError(
            f"Missing credentials for region {region}. Set INTREPID_USER_{region} and either INTREPID_PASS_{region} or INTREPID_PASS (shared) in .env"
        )
    return start_and_login(region=region, username_val=username_val, password_val=password_val)
