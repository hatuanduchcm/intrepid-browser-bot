from pywinauto.keyboard import send_keys

from brand.handler_search_brand import should_process_brand
from utils.window import get_intrepid_window
import time
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def handle_open_order_event(event_payload):
    order_id = event_payload.get('order_id')
    if not order_id:
        raise RuntimeError('Missing order_id')
    w = get_intrepid_window()
    if not w:
        raise RuntimeError('Intrepid window not found')

    try:
        wr = w.wrapper_object()
        # some descendants may raise when querying friendly_class_name(); guard those
        edits = []
        for c in wr.descendants():
            try:
                name = c.friendly_class_name()
            except Exception:
                continue
            try:
                if name and name.lower().startswith('edit'):
                    edits.append(c)
            except Exception as e:
                logger.debug('Error checking control: %s', e)
                continue
        if edits:
            # Navigate to the order page via address bar using keyboard (more reliable)
            try:
                brand = event_payload.get('brand')
                if brand is not None and not _should_process_brand(brand):
                    logging.debug('Skipping open_order because brand "%s" same as last processed', brand)
                else:
                    if not _navigate_to_order_portal(edits):
                        logger.debug('navigate_to_order_portal failed')

                # find and fill the order ID input (uses control descendants or image fallback)
                try:
                    if not _find_and_fill_order_input(edits, order_id):
                        logger.debug('find_and_fill_order_input failed')
                except Exception as e:
                    logger.debug('find_and_fill_order_input exception: %s', e)

                # after search results appear, click the 'Order ID' label/box to open details
                try:
                #     # look for a control with text containing 'Order ID' and click its parent center
                #     for c in wr.descendants():
                #         try:
                #             if 'order id' in (c.window_text() or '').lower():
                #                 try:
                #                     rc = c.rectangle()
                #                     cx = (rc.left + rc.right) // 2
                #                     cy = (rc.top + rc.bottom) // 2
                #                     c.click_input(coords=(cx - rc.left, cy - rc.top))
                #                     return True
                #                 except Exception:
                #                     try:
                #                         c.click_input()
                #                         return True
                #                     except Exception:
                #                         continue
                #         except Exception:
                #             continue
                    # fallback: image click
                    try:
                        import pyautogui
                        box_img = Path(__file__).resolve().parents[2] / 'assets' / 'icons' / 'order_id_box.png'
                        if box_img.exists():
                            m = pyautogui.locateCenterOnScreen(str(box_img), confidence=0.5)
                            if m:
                                pyautogui.click(m.x, m.y)
                                time.sleep(4)
                                return True
                            else:                               
                                logger.debug('Order ID box image not found on screen')
                    except Exception as e:
                        logger.debug('pyautogui fallback for clicking order ID box failed: %s', e)
                        pass
                except Exception as e:
                    logger.debug('click order id box failed: %s', e)
            except Exception as e:
                logger.debug('open_order navigation failed: %s', e)
        return False
    except Exception as e:
        logger.debug('open_order failed: %s', e)
    return False

LAST_PROCESSED_BRAND = None


def _should_process_brand(brand_name: str) -> bool:
    """Return True if this brand should be processed (not duplicate of last)."""
    global LAST_PROCESSED_BRAND
    if not brand_name:
        return False
    if LAST_PROCESSED_BRAND and str(brand_name).strip().lower() == str(LAST_PROCESSED_BRAND).strip().lower():
        logging.debug('Brand "%s" same as last processed; skipping', brand_name)
        return False
    LAST_PROCESSED_BRAND = brand_name
    return True

def _navigate_to_order_portal(edits) -> bool:
    """Focus an Edit control and navigate to the order portal URL. Returns True on success."""
    try:
        from pywinauto.keyboard import send_keys
        edits_sorted = sorted(edits, key=lambda e: e.rectangle().top)
        addr = edits_sorted[0]
        # focus address/control and try to set URL directly (preferred for non-standard browsers)
        addr.set_focus()
        time.sleep(0.2)
        url = f'https://banhang.shopee.vn/portal/sale/order'
        try:
            addr.set_text(url)
        except Exception:
            # fallback: type into the focused control (previous approach that worked)
            send_keys('^a{BACKSPACE}')
            time.sleep(0.5)
            send_keys(url)
        send_keys('{ENTER}')
        time.sleep(7.0)
        return True
    except Exception as e:
        logger.debug('navigate_to_order_portal error: %s', e)
        return False


def _type_order_id_into_control(input_control, order_id: str) -> bool:
    """Type the order_id into a pywinauto control, returning True on success."""
    try:
        input_control.set_focus()
        time.sleep(0.1)
        # clear any existing text first
        try:
            input_control.set_text('')
        except Exception:
            send_keys('^a{BACKSPACE}')
        time.sleep(0.05)
        try:
            input_control.set_text(str(order_id))
        except Exception:
            send_keys(str(order_id))
        send_keys('{ENTER}')
        time.sleep(3.0)
        # clear the input after submitting to leave a clean state
        try:
            input_control.set_focus()
            time.sleep(0.05)
            try:
                input_control.set_text('')
            except Exception:
                send_keys('^a{BACKSPACE}')
        except Exception:
            # best-effort; ignore failures
            pass
        return True
    except Exception as e:
        logger.debug('failed to type into input_control: %s', e)
        return False


def _find_and_fill_order_input(edits, order_id: str) -> bool:
    """Locate an order-id input either via Edit controls or image fallback and fill it.

    Returns True if input was filled and Enter was sent.
    """
    # # try to find an Edit control and use it
    # try:
    #     for c in edits:
    #         try:
    #             name = c.friendly_class_name()
    #         except Exception:
    #             continue
    #         try:
    #             if name and name.lower().startswith('edit'):
    #                 if _type_order_id_into_control(c, order_id):
    #                     return True
    #         except Exception:
    #             continue
    # except Exception as e:
    #     logger.debug('error scanning edits for input control: %s', e)

    # fallback: use pyautogui image locate if available
    try:
        import pyautogui
        input_img = Path(__file__).resolve().parents[2] / 'assets' / 'icons' / 'order_input.png'
        if input_img.exists():
            m = pyautogui.locateCenterOnScreen(str(input_img), confidence=0.8)
            if m:
                pyautogui.click(m.x, m.y)
                time.sleep(0.2)
                pyautogui.typewrite(str(order_id))
                pyautogui.press('enter')
                # best-effort: clear the input after submitting
                try:
                    pyautogui.click(m.x, m.y)
                    pyautogui.hotkey('ctrl', 'a')
                    pyautogui.press('backspace')
                except Exception:
                    pass
                return True
            else:
                logger.debug('Order ID input image not found on screen')
    except Exception as e:
        logger.debug('pyautogui fallback for order ID input failed: %s', e)

    return False
