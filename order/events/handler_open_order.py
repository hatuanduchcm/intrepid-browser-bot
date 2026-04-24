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
                if brand is not None and not _should_process_brand(brand):
                    logging.debug('Skipping open_order because brand "%s" same as last processed', brand)
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
                        pyautogui.moveTo(m.x, m.y, duration=0.5)
                        time.sleep(0.3)
                        pyautogui.click()
                        time.sleep(6)
                        return True
                    else:
                        logger.debug('No order ID box image found on screen after trying all candidates')
                except Exception as e:
                    logger.debug('pyautogui fallback for clicking order ID box failed: %s', e)
                    pass
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

def _navigate_to_order_portal(edits, venture: str = 'VN') -> bool:
    """Focus an Edit control and navigate to the order portal URL. Returns True on success."""
    try:
        from pywinauto.keyboard import send_keys
        edits_sorted = sorted(edits, key=lambda e: e.rectangle().top)
        addr = edits_sorted[0]
        # focus address/control and try to set URL directly (preferred for non-standard browsers)
        addr.set_focus()
        time.sleep(3)
        url = _order_portal_url(venture)
        try:
            addr.set_text(url)
            time.sleep(0.5)
        except Exception:
            # fallback: type into the focused control (previous approach that worked)
            send_keys('^a{BACKSPACE}')
            time.sleep(0.5)
            send_keys(url)
        send_keys('{ENTER}')
        time.sleep(16.0)
        return True
    except Exception as e:
        logger.debug('navigate_to_order_portal error: %s', e)
        return False


def _dismiss_popups(max_attempts: int = 2, icon_name: str = 'close-popup.png', confidence: float = 0.85, click_delay: float = 0.25, pause_between: float = 1):
    """Try to find and click popup close buttons repeatedly until none remain or max attempts reached.

    Looks for `assets/icons/<icon_name>` on screen and clicks center when found. Waits `pause_between`
    seconds between attempts to let UI stabilize. Best-effort; does not raise on failures.
    """
    try:
        import pyautogui
    except Exception:
        logger.debug('pyautogui not available for dismissing popups')
        return

    icon_path = Path(__file__).resolve().parents[2] / 'assets' / 'icons' / icon_name
    if not icon_path.exists():
        logger.debug('Popup close icon not found: %s', icon_path)
        return

    attempts = 0
    while attempts < max_attempts:
        attempts += 1
        try:
            matches = list(pyautogui.locateAllOnScreen(str(icon_path), confidence=confidence))
        except Exception as e:
            logger.debug('locateAllOnScreen error while dismissing popups: %s', e)
            matches = []

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

def _find_and_fill_order_input(edits, order_id: str) -> bool:
    """Locate an order-id input either via Edit controls or image fallback and fill it.

    Returns True if input was filled and Enter was sent.
    """

    # fallback: use pyautogui image locate if available
    try:
        import pyautogui
        input_img = Path(__file__).resolve().parents[2] / 'assets' / 'icons' / 'order_input.png'
        if input_img.exists():
            m = pyautogui.locateCenterOnScreen(str(input_img), confidence=0.8)
            if m:
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
