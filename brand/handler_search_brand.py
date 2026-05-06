from brand.events.search_helpers import click_shopee_shop_icon, shop_not_found_present, find_and_click_brand_tab, get_brand_search_query, _BRAND_TAB_ICON_MAP, wait_for_shop_url
from utils.window import get_intrepid_window
from auth.handler_2fa import handle_2fa
from brand.events.handler_click_search_icon import handle_click_search_icon
from brand.events.handler_select_result import enter_brand_in_search_box
from brand.events.handler_clean_brand_box import handle_clean_brand_box
import time
import logging
from utils.twofa_cache import is_brand_verified

# remember last processed (brand, venture) to avoid duplicate work
LAST_PROCESSED_STATE = (None, None)  # (brand_lower, venture_upper)
# cache last brand search outcome: brand -> bool (True=found, False=not found)
LAST_BRAND_STATUS: dict = {}


def should_process_brand(brand_name: str, venture: str = '') -> bool:
    """Return True if this (brand, venture) combo differs from the last processed one."""
    global LAST_PROCESSED_STATE
    if not brand_name:
        return False
    key = (str(brand_name).strip().lower(), str(venture).strip().upper())
    if LAST_PROCESSED_STATE == key:
        logging.debug('Brand "%s" (venture=%s) same as last processed; skipping', brand_name, venture)
        return False
    LAST_PROCESSED_STATE = key
    return True


def start_and_search_brand(brand_name: str, venture: str = ''):
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
    
    if not should_process_brand(brand_name, venture=venture):
        return True

    if not handle_click_search_icon({}):
        raise RuntimeError('Failed to click search icon')

    search_query = get_brand_search_query(brand_name)
    if not enter_brand_in_search_box({'query': search_query}):
        raise RuntimeError('Failed to select brand result for query: "%s"' % search_query)

    if shop_not_found_present():
        logging.debug('Shop not found message detected after selecting brand "%s"', brand_name)
        # cache negative result to skip future searches for this brand
        LAST_BRAND_STATUS[str(brand_name).strip().lower()] = False
        handle_clean_brand_box({})
        return False

    # brands with a dedicated tab icon use find_and_click_brand_tab instead of the generic Shopee icon
    if brand_name.strip().lower() in _BRAND_TAB_ICON_MAP:
        if not find_and_click_brand_tab(brand_name):
            logging.debug('find_and_click_brand_tab failed for "%s", continuing anyway', brand_name)
    elif not click_shopee_shop_icon():
        logging.debug('Failed to click shopee shop icon after selecting brand, continuing anyway')

    # clean the brand search box by clicking the saved search icon coordinates
    if not handle_clean_brand_box({}):
        logging.debug('clean brand box failed, continuing')

    # final 2FA / URL stability check
    # skip entirely if this brand was previously verified (known reachable)
    if brand_name and is_brand_verified(brand_name):
        logging.debug('Brand "%s" previously verified; skipping URL wait', brand_name)
    else:
        _url_ok = wait_for_shop_url(timeout=15.0, stable_for=2.0)
        if not _url_ok:
            logging.warning('Brand "%s": page did not reach a stable shop URL within timeout — skipping order', brand_name)
            return False

    return True


def handle_search_brand_event(event_payload):
    brand = event_payload.get('brand')
    if not brand:
        raise RuntimeError('Missing brand in payload')
    venture = event_payload.get('venture', '')
    return start_and_search_brand(brand, venture=venture)
