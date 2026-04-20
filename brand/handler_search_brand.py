from brand.events.search_helpers import click_shopee_shop_icon, shop_not_found_present
from utils.window import get_intrepid_window
from auth.handler_2fa import handle_2fa
from brand.events.handler_click_search_icon import handle_click_search_icon
from brand.events.handler_select_result import enter_brand_in_search_box
from brand.events.handler_clean_brand_box import handle_clean_brand_box
import time
import logging
from utils.twofa_cache import is_brand_verified

# remember last processed brand to avoid duplicate work
LAST_PROCESSED_BRAND = None
# cache last brand search outcome: brand -> bool (True=found, False=not found)
LAST_BRAND_STATUS: dict = {}


def should_process_brand(brand_name: str) -> bool:
    """Return True if this brand should be processed (not duplicate of last)."""
    global LAST_PROCESSED_BRAND
    if not brand_name:
        return False
    if LAST_PROCESSED_BRAND and str(brand_name).strip().lower() == str(LAST_PROCESSED_BRAND).strip().lower():
        logging.debug('Brand "%s" same as last processed; skipping', brand_name)
        return False
    LAST_PROCESSED_BRAND = brand_name
    return True


def start_and_search_brand(brand_name: str):
    """Orchestrate the steps to search for a brand and select the result."""
    # ensure window present
    w = get_intrepid_window()
    if not w:
        raise RuntimeError('Intrepid window not found')

    # if we previously determined this brand has no results, skip searching
    prev = LAST_BRAND_STATUS.get(str(brand_name).strip().lower())
    if prev is False:
        logging.debug('Previously marked "%s" as not found; skipping search', brand_name)
        return False
    
    if not should_process_brand(brand_name):
        return True

    if not handle_click_search_icon({}):
        raise RuntimeError('Failed to click search icon')

    if not enter_brand_in_search_box({'query': brand_name}):
        raise RuntimeError('Failed to select brand result for query: "%s"' % brand_name)
    
    if shop_not_found_present():
        logging.debug('Shop not found message detected after selecting brand "%s"', brand_name)
        # cache negative result to skip future searches for this brand
        LAST_BRAND_STATUS[str(brand_name).strip().lower()] = False
        handle_clean_brand_box({})
        return False
    
    if not click_shopee_shop_icon():
        logging.debug('Failed to click shopee shop icon after selecting brand, continuing anyway')

    # clean the brand search box by clicking the saved search icon coordinates
    if not handle_clean_brand_box({}):
        logging.debug('clean brand box failed, continuing')

    # final 2FA check: if OTP prompt appears after selection, try reload/resend
    from auth.handler_2fa import handle_2fa
    # skip 2FA helper if this brand was previously verified
    if brand_name and is_brand_verified(brand_name):
        logging.debug('Brand "%s" previously verified via 2FA; skipping 2FA helper', brand_name)
    # else:
    #     if handle_2fa(timeout_seconds=3.0, post_click_delay=1.0, brand=brand_name):
    #         raise RuntimeError('2FA OTP prompt detected after selecting brand, user may need to enter OTP')

    # mark as processed and record positive result
    global LAST_PROCESSED_BRAND
    LAST_PROCESSED_BRAND = brand_name
    LAST_BRAND_STATUS[str(brand_name).strip().lower()] = True

    return True


def handle_search_brand_event(event_payload):
    brand = event_payload.get('brand')
    if not brand:
        raise RuntimeError('Missing brand in payload')
    return start_and_search_brand(brand)
