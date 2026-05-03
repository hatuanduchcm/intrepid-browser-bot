from pathlib import Path
import logging
import time
import re as _re
import pyautogui

logger = logging.getLogger(__name__)

# Map normalized brand name -> icon filename in assets/icons.
# Used by find_and_click_brand_tab() to switch to the correct browser tab.
# Same icon file can cover both ID and TH ventures when the brand name is identical.
_BRAND_TAB_ICON_MAP: dict = {
    'darya-varia official shop -admin': 'brand_id_darya_admin.png',
    'natur-e -admin': 'brand_id_natur_e_admin.png',
    'optimum nutrition official -admin': 'brand_id_optimum_nutrition_offical_admin.png',
}

# Prefix to type into the search box for brands that have a dedicated tab icon.
# Shorter prefix avoids matching incorrect results when full name includes " -Admin".
_BRAND_SEARCH_PREFIX_MAP: dict = {
    'darya-varia official shop -admin': 'darya-varia official shop',
    'natur-e -admin': 'natur-e',
    'optimum nutrition official -admin': 'optimum nutrition official',
}


def get_brand_search_query(brand_name: str) -> str:
    """Return the search box query to use for the given brand.

    If a shorter prefix is registered (to avoid the ' -Admin' suffix), return it.
    Otherwise return the brand name unchanged.
    """
    return _BRAND_SEARCH_PREFIX_MAP.get(brand_name.strip().lower(), brand_name)


def find_and_click_brand_tab(brand_name: str, confidences: tuple = (0.9, 0.85, 0.8), timeout: float = 5.0) -> bool:
    """Locate and click the browser tab for the given brand using its icon template.

    Returns True if the tab was found and clicked, False (or if no icon registered).
    Works for any venture that shares the same brand name and tab appearance.
    """
    normalized = brand_name.strip().lower()
    icon_file = _BRAND_TAB_ICON_MAP.get(normalized)
    if not icon_file:
        logger.debug('No tab icon template registered for brand: %s', brand_name)
        return False

    base_icons = Path(__file__).resolve().parents[2] / 'assets' / 'icons'
    icon_path = base_icons / icon_file
    if not icon_path.exists():
        logger.debug('Brand tab icon file not found: %s', icon_path)
        return False

    deadline = time.time() + timeout
    while time.time() < deadline:
        for conf in confidences:
            try:
                loc = pyautogui.locateCenterOnScreen(str(icon_path), confidence=conf)
                if loc:
                    logger.debug('Found tab icon for "%s" at %s (conf=%s), clicking', brand_name, loc, conf)
                    pyautogui.click(loc.x, loc.y, duration=0.12)
                    time.sleep(0.5)
                    return True
            except Exception as e:
                logger.debug('locateCenterOnScreen failed for "%s" conf=%s: %s', brand_name, conf, e)
        time.sleep(0.5)

    logger.debug('Brand tab icon not found for "%s" within timeout', brand_name)
    return False


def wait_for_shop_url(venture: str = '', timeout: float = 15.0, stable_for: float = 3.5) -> bool:
    """Wait until the Intrepid address bar shows a Shopee shop URL and stays stable.

    Matches patterns like:
      https://shopee.vn/<slug>/
      https://*.shopee.co.id/<slug>/
    Returns True once the URL has been stable for `stable_for` seconds.
    Returns False if `timeout` is reached without stabilising.
    """
    from utils.window import get_intrepid_window

    # Build pattern: matches shopee domain with optional path
    # e.g. https://banhang.shopee.vn/ or https://shopee.vn/brand-slug
    _BASE_PATTERNS = [
        _re.compile(r'https?://[^/]*shopee\.[^/]+', _re.IGNORECASE),
    ]

    def _get_url() -> str:
        """Try to read the address bar text via pywinauto."""
        try:
            w = get_intrepid_window()
            if not w:
                return ''
            # Chrome/Edge address bar is an Edit control inside a toolbar
            for ctrl_type in ('Edit', 'Document'):
                try:
                    bars = w.descendants(control_type=ctrl_type)
                    for bar in bars:
                        try:
                            val = bar.get_value() or bar.window_text() or ''
                            if val.startswith('http'):
                                return val.strip()
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            pass
        return ''

    deadline = time.time() + timeout
    stable_since = None
    last_url = ''

    while time.time() < deadline:
        url = _get_url()
        is_shop = any(p.search(url) for p in _BASE_PATTERNS)
        # exclude known transient/auth URLs
        is_transient = any(x in url for x in ('verify', 'login', 'auth', 'email-link'))

        if is_shop and not is_transient:
            if url == last_url:
                if stable_since is None:
                    stable_since = time.time()
                elif time.time() - stable_since >= stable_for:
                    logger.info('[wait_for_shop_url] stable at: %s', url)
                    return True
            else:
                # URL changed — reset stability timer
                stable_since = None
                last_url = url
                logger.debug('[wait_for_shop_url] navigating: %s', url)
        else:
            stable_since = None
            last_url = url
            if url:
                logger.debug('[wait_for_shop_url] waiting, current: %s', url)

        time.sleep(0.5)

    logger.warning('[wait_for_shop_url] timed out after %.0fs, last url: %s', timeout, last_url)
    return False


def shop_not_found_present(confidence: float = 0.85) -> bool:
    """Return True if the 'shop_not_found.png' image appears on screen.

    Determines the icons folder internally.
    """
    try:
        base_icons = Path(__file__).resolve().parents[2] / 'assets' / 'icons'
        shop_not_found = base_icons / 'shop_not_found.png'
        if not shop_not_found.exists():
            logger.debug('shop_not_found.png not present in icons folder')
            return False
        loc = pyautogui.locateOnScreen(str(shop_not_found), confidence=confidence)
        return bool(loc)
    except Exception as e:
        logger.debug('Shop not found not detected due to: %s', e)
        return False


def click_shopee_shop_icon(confidences=(0.95, 0.85, 0.8), timeout: float = 4.0) -> bool:
    """Locate and click the brand icon using multiple confidences and a timeout.

    Determines the icons folder internally.
    """
    try:
        base_icons = Path(__file__).resolve().parents[2] / 'assets' / 'icons'
        icon = base_icons / 'brand_shopee_icon.png'
        if not icon.exists():
            logger.debug('brand_shopee_icon.png not found at %s', icon)
            return False
        deadline = time.time() + timeout
        while time.time() < deadline:
            for conf in confidences:
                try:
                    loc = pyautogui.locateCenterOnScreen(str(icon), confidence=conf)
                    if loc:
                        logger.debug('Found brand icon at %s with confidence %s, clicking', loc, conf)
                        pyautogui.click(loc.x, loc.y, duration=0.12)
                        time.sleep(0.3)
                        return True
                except Exception as e:
                    logger.debug('Error locating brand icon at confidence %s: %s', conf, e)
            time.sleep(1)
    except Exception as e:
        logger.debug('Error in click_brand_icon: %s', e)
    return False
