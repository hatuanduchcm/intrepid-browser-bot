from utils.window import get_intrepid_window


def handle_enter_email(event_payload):
    username = event_payload.get('username')
    try:
        w = get_intrepid_window()
        if not w:
            raise RuntimeError('Intrepid window not found')
        email_edit = w.child_window(control_type='Edit', found_index=0)
        email_edit.set_text(username)
        return True
    except Exception as e:
        raise RuntimeError(f"enter_email failed: {e}")
