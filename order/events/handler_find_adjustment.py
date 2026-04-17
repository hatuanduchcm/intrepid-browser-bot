from utils.window import get_intrepid_window
import logging
import time

logger = logging.getLogger(__name__)


def handle_find_adjustment_event(event_payload):
    """Locate 'Order Adjustment' section on the current order page.
    Returns True if found (and focuses it), False otherwise.
    """
    w = get_intrepid_window()
    if not w:
        raise RuntimeError('Intrepid window not found')

    try:
        # Try to find a control with text 'Order Adjustment'
        item = w.child_window(title_re='.*Order Adjustment.*', control_type='Text')
        if item and item.exists():
            try:
                item.set_focus()
            except Exception:
                pass
            logger.debug('Found Order Adjustment control: %s', item)
            return True
    except Exception as e:
        logger.debug('find_adjustment lookup failed: %s', e)

    # fallback: search all text controls
    try:
        for c in w.descendants(control_type='Text'):
            try:
                txt = c.window_text() or ''
            except Exception:
                txt = ''
            if 'order adjustment' in txt.lower():
                try:
                    c.set_focus()
                except Exception:
                    pass
                logger.debug('Found by scanning text: %s', txt)
                return True
    except Exception as e:
        logger.debug('scan for Order Adjustment failed: %s', e)

    return False
