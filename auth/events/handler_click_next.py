from pywinauto.keyboard import send_keys
from utils.window import get_intrepid_window
import time


def handle_click_next(event_payload):
    try:
        w = get_intrepid_window()
        if not w:
            raise RuntimeError('Intrepid window not found')
        # try find Next/Continue button
        try:
            btn = w.child_window(title_re='Next|Continue', control_type='Button')
            if btn and btn.exists():
                btn.click_input()
                return True
        except Exception:
            pass
        # fallback: press Enter
        send_keys('{ENTER}')
        time.sleep(0.2)
        return True
    except Exception as e:
        raise RuntimeError(f"click_next failed: {e}")
