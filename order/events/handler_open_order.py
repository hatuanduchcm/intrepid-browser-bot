from pywinauto.keyboard import send_keys

from brand.handler_search_brand import should_process_brand
from utils.window import get_intrepid_window
import time
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


# Shopee seller portal TLD per venture
_VENTURE_TLD = {
    'VN': 'vn',
    'PH': 'ph',
    'SG': 'sg',
    'MY': 'com.my',
    'TH': 'co.th',
    'ID': 'co.id',
}


def _order_portal_url(venture: str) -> str:
    tld = _VENTURE_TLD.get(venture.upper(), venture.lower())
    return f'https://seller.shopee.{tld}/portal/sale/order'


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
                venture_ev = event_payload.get('venture', '')
                if brand is not None and not _should_process_brand(brand, venture=venture_ev):
                    logging.debug('Skipping open_order because brand "%s" (venture=%s) same as last processed', brand, venture_ev)
                else:
                    navigated = _navigate_to_order_portal(edits, venture=event_payload.get('venture', 'VN'))
                    if not navigated:
                        logger.debug('navigate_to_order_portal failed')
                        # dismiss any obstructing popup ads that may appear after navigation
                        try:
                            _dismiss_popups()
                        except Exception as e:
                            logger.debug('dismiss_popups failed: %s', e)

                # find and fill the order ID input (uses control descendants or image fallback)
                try:
                    if not _find_and_fill_order_input(edits, order_id):
                        logger.debug('find_and_fill_order_input failed')
                except Exception as e:
                    logger.debug('find_and_fill_order_input exception: %s', e)

                # after search results appear, click the 'Order ID' label/box to open details
                try:
                    import pyautogui
                    _icons_dir = Path(__file__).resolve().parents[2] / 'assets' / 'icons'
                    _box_candidates = ['order_id_box.png', 'order_id_box_label.png', 'order_id_box_2.png']
                    m = None
                    for scroll_attempt in range(4):
                        for _candidate in _box_candidates:
                            _img = _icons_dir / _candidate
                            if not _img.exists():
                                logger.debug('%s not found, skipping', _candidate)
                                continue
                            try:
                                m = pyautogui.locateCenterOnScreen(str(_img), confidence=0.7)
                                if m:
                                    logger.debug('Found order ID box via %s', _candidate)
                                    break
                                else:
                                    logger.debug('%s not found on screen', _candidate)
                            except Exception as e:
                                logger.debug('Error locating order ID box %s on screen: %s', _candidate, e)
                        if m:
                            break
                        # If not found, scroll down and try again
                        try:
                            pyautogui.scroll(-300)
                            time.sleep(0.3)
                            logger.debug('Scrolled down to search for order ID box (attempt %d)', scroll_attempt+1)
                            # Always scroll up after scrolling down
                            pyautogui.scroll(300)
                            time.sleep(0.2)
                            logger.debug('Scrolled up after scrolling down (reset view)')
                        except Exception as e:
                            logger.debug('scroll down/up while searching order ID box failed: %s', e)
                    if m:
                        pyautogui.moveTo(m.x, m.y, duration=0.5)
                        time.sleep(0.3)
                        pyautogui.click()
                        time.sleep(6)
                        # Scroll up to ensure adjustment table is visible (for TH)
                        try:
                            pyautogui.scroll(500)
                            time.sleep(0.3)
                        except Exception as e:
                            logger.debug('scroll up after opening order detail failed: %s', e)
                        return True
                    else:
                        logger.debug('No order ID box image found on screen after trying all candidates')
                        # Stop processing further orders if not found
                        raise RuntimeError('Order ID box not found, stopping further order processing.')
                except Exception as e:
                    logger.debug('pyautogui fallback for clicking order ID box failed: %s', e)
                    raise
            except Exception as e:
                logger.debug('open_order navigation failed: %s', e)
        return False
    except Exception as e:
        logger.debug('open_order failed: %s', e)
    return False

LAST_PROCESSED_STATE = (None, None)  # (brand_lower, venture_upper)


def _should_process_brand(brand_name: str, venture: str = '') -> bool:
    """Return True if navigation is needed (brand+venture combo differs from last)."""
    global LAST_PROCESSED_STATE
    if not brand_name:
        return False
    key = (str(brand_name).strip().lower(), str(venture).strip().upper())
    if LAST_PROCESSED_STATE == key:
        logging.debug('Brand "%s" (venture=%s) same as last; skipping navigation', brand_name, venture)
        return False
    LAST_PROCESSED_STATE = key
    return True

def _navigate_to_order_portal(edits, venture: str = 'VN') -> bool:
    """Navigate the browser address bar to the order portal URL. Returns True on success."""
    try:
        import pyautogui

        url = _order_portal_url(venture)
        logger.debug('Navigating to order portal: %s', url)

        edits_sorted = sorted(edits, key=lambda e: e.rectangle().width, reverse=True)
        addr = edits_sorted[0]
        addr.set_focus()
        time.sleep(0.3)
        addr.set_text(url)
        time.sleep(0.2)
        send_keys('{ENTER}')

        # Wait for order input box (image) to appear, up to 15s
        input_img = Path(__file__).resolve().parents[2] / 'assets' / 'icons' / 'order_input.png'
        found_input = False
        for _ in range(25):  # 25 x 0.5s = 12.5s max
            if input_img.exists():
                try:
                    m = pyautogui.locateCenterOnScreen(str(input_img), confidence=0.8)
                except Exception as e:
                    logger.debug('Error locating order input image on screen: %s', e)
                    m = None
                if m:
                    found_input = True
                    break
            else:
                logger.debug('Order input image not found in assets/icons/')
            time.sleep(0.5)

        if not found_input:
            logger.debug('Order input box not found after navigation')
            return False

        # Check for order-shipping.png and order-warning.png icons only
        icons_dir = Path(__file__).resolve().parents[2] / 'assets' / 'icons'
        shipping_icon = icons_dir / 'order-shipping.png'
        warning_icon = icons_dir / 'order-warning.png'
        found_shipping = False
        found_warning = False
        for _ in range(10):  # check for up to 5s
            try:
                if shipping_icon.exists():
                    try:
                        if pyautogui.locateOnScreen(str(shipping_icon), confidence=0.7):
                            found_shipping = True
                    except Exception as e:
                        logger.debug('Error locating shipping_icon on screen: %s', e)
                if warning_icon.exists():
                    try:
                        if pyautogui.locateOnScreen(str(warning_icon), confidence=0.7):
                            found_warning = True
                    except Exception as e:
                        logger.debug('Error locating warning_icon on screen: %s', e)
            except Exception as e:
                logger.debug('Error in shipping/warning icon check loop: %s', e)
            time.sleep(0.5)

        if found_shipping or found_warning:
            time.sleep(2.0)
        else:
            time.sleep(3.5)

        return True
    except Exception as e:
        logger.debug('navigate_to_order_portal error: %s', e)
        return False


def _dismiss_popups(max_attempts: int = 2, confidence: float = 0.85, click_delay: float = 0.25, pause_between: float = 1):
    """Try to find and click popup close buttons repeatedly until none remain or max attempts reached.

    Looks for both close-popup.png and close-popup-2.png in assets/icons/ and clicks center when found.
    Waits `pause_between` seconds between attempts to let UI stabilize. Best-effort; does not raise on failures.
    """
    try:
        import pyautogui
    except Exception:
        logger.debug('pyautogui not available for dismissing popups')
        return

    icons_dir = Path(__file__).resolve().parents[2] / 'assets' / 'icons'
    icon_paths = [
        icons_dir / 'close-popup.png',
        icons_dir / 'close-popup-2.png',
    ]
    icon_paths = [p for p in icon_paths if p.exists()]
    if not icon_paths:
        logger.debug('No popup close icons found in assets/icons/')
        return

    attempts = 0
    while attempts < max_attempts:
        attempts += 1
        matches = []
        for icon_path in icon_paths:
            try:
                found = list(pyautogui.locateAllOnScreen(str(icon_path), confidence=confidence))
                matches.extend(found)
            except Exception as e:
                logger.debug('locateAllOnScreen error while dismissing popups: %s', e)
        if not matches:
            # nothing found, stop early
            return

        # click each found close button, from topmost-first
        matches_sorted = sorted(matches, key=lambda m: m.top)
        for m in matches_sorted:
            try:
                cx = m.left + m.width // 2
                cy = m.top + m.height // 2
                pyautogui.moveTo(cx, cy, duration=0.15)
                time.sleep(0.05)
                pyautogui.click()
                time.sleep(click_delay)
            except Exception as e:
                logger.debug('clicking popup close failed: %s', e)
                continue

        time.sleep(pause_between)

    logger.debug('dismiss_popups reached max attempts (%d) and stopped', max_attempts)

def _select_fulfillment_all() -> bool:
    """Find the Fulfillment Type selector and click the 'All' option if present.

    Looks for assets/icons/fulfillment_type_select.png (the dropdown trigger),
    clicks it to open, then clicks assets/icons/fulfillment_all_option.png.
    Falls back to clicking fulfillment_all_option.png directly if dropdown trigger
    is not needed or already open.
    Returns True if 'All' was successfully clicked.
    """
    try:
        import pyautogui
        _icons_dir = Path(__file__).resolve().parents[2] / 'assets' / 'icons'

        # Step 1: optionally click the dropdown trigger to open it
        trigger_img = _icons_dir / 'fulfillment_type_select_box.png'
        if trigger_img.exists():
            try:
                t = pyautogui.locateCenterOnScreen(str(trigger_img), confidence=0.75)
                if t:
                    pyautogui.click(t.x, t.y)
                    time.sleep(0.4)
                    logger.info('Clicked fulfillment type dropdown trigger')
                else:
                    logger.info('fulfillment_type_select_box.png not found on screen, skipping trigger click')
            except Exception as e:
                logger.debug('Could not click fulfillment type trigger: %s', e)
        else:
            logger.warning('fulfillment_type_select_box.png not in assets/icons/')

        # Step 2: click the 'All' option
        all_img = _icons_dir / 'fulfillment_type_option_all.png'
        if all_img.exists():
            try:
                a = pyautogui.locateCenterOnScreen(str(all_img), confidence=0.75)
                if a:
                    pyautogui.click(a.x, a.y)
                    time.sleep(0.4)
                    logger.info('Selected fulfillment type = All')
                    return True
                else:
                    logger.info('fulfillment_type_option_all.png not found on screen')
            except Exception as e:
                logger.debug('Could not click fulfillment All option: %s', e)
        else:
            logger.warning('fulfillment_type_option_all.png not in assets/icons/, skipping fulfillment filter')
    except Exception as e:
        logger.debug('_select_fulfillment_all failed: %s', e)
    return False


def _find_and_fill_order_input(edits, order_id: str) -> bool:
    """Locate an order-id input either via Edit controls or image fallback and fill it.

    Before typing the order ID, attempts to set the Fulfillment Type filter to 'All'
    if the corresponding icon assets are present.
    Returns True if input was filled and Enter was sent.
    """

    # fallback: use pyautogui image locate if available
    try:
        import pyautogui
        input_img = Path(__file__).resolve().parents[2] / 'assets' / 'icons' / 'order_input.png'
        if input_img.exists():
            m = pyautogui.locateCenterOnScreen(str(input_img), confidence=0.8)
            if m:
                # Try to set Fulfillment Type to 'All' before entering the order ID
                try:
                    _select_fulfillment_all()
                except Exception as e:
                    logger.debug('_select_fulfillment_all raised: %s', e)

                pyautogui.click(m.x, m.y)
                time.sleep(0.2)
                pyautogui.typewrite(str(order_id), interval=0.05)
                pyautogui.press('enter')
                time.sleep(2)
                # best-effort: clear the input after submitting
                try:
                    pyautogui.click(m.x, m.y)
                    pyautogui.hotkey('ctrl', 'a')
                    pyautogui.press('backspace')
                    time.sleep(0.5)
                except Exception:
                    logging.debug('Failed to clear order ID input after submission, continuing anyway')
                return False
            else:
                logger.debug('Order ID input image not found on screen')
    except Exception as e:
        logger.debug('pyautogui fallback for order ID input failed: %s', e)

    return False
