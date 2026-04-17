from utils.window import get_intrepid_window
import time
import pywinauto


def handle_type_search(event_payload):
    query = event_payload.get('query')
    try:
        w = get_intrepid_window()
        if not w:
            raise RuntimeError('Intrepid window not found')
        # focus the search edit (assume first Edit in popup)
        edit = w.child_window(control_type='Edit', found_index=0)
        edit.set_focus()
        # use set_text when available else type_keys
        try:
            edit.set_text(query)
        except Exception:
            from pywinauto.keyboard import send_keys
            send_keys(query)
        time.sleep(0.4)
        return True
    except Exception as e:
        raise RuntimeError(f'type_search failed: {e}')
