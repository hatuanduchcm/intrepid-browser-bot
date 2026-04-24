from pathlib import Path
import logging
import time
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
        logger.debug('Error checking for shop_not_found image: %s', e)
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
