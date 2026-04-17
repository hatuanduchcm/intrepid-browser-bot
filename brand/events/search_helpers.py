from pathlib import Path
import logging
import time
import pyautogui

logger = logging.getLogger(__name__)


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
                        pyautogui.click(loc.x, loc.y)
                        time.sleep(0.3)
                        return True
                except Exception as e:
                    logger.debug('Error locating brand icon at confidence %s: %s', conf, e)
            time.sleep(0.25)
    except Exception as e:
        logger.debug('Error in click_brand_icon: %s', e)
    return False
