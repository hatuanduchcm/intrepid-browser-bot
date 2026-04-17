from pywinauto.keyboard import send_keys
from utils.window import get_intrepid_window
import time


def handle_submit(event_payload):
    try:
        w = get_intrepid_window()
        if not w:
            raise RuntimeError('Intrepid window not found')
        # try find Continue/Sign in button
        try:
            btn = w.child_window(title_re='Continue|Sign in|Login', control_type='Button')
            if btn and btn.exists():
                btn.click_input()
                time.sleep(3)
                return True
        except Exception:
            pass
        send_keys('{ENTER}')
        time.sleep(0.2)
        return True
    except Exception as e:
        raise RuntimeError(f"submit failed: {e}")
