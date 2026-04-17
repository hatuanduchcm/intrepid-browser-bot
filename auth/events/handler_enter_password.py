from utils.window import get_intrepid_window


def handle_enter_password(event_payload):
    password = event_payload.get('password')
    try:
        w = get_intrepid_window()
        if not w:
            raise RuntimeError('Intrepid window not found')
        pwd_edit = w.child_window(control_type='Edit', found_index=0)
        pwd_edit.set_text(password)
        return True
    except Exception as e:
        raise RuntimeError(f"enter_password failed: {e}")
