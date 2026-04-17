import time
import logging
from pathlib import Path
from utils.twofa_cache import mark_brand_verified

logger = logging.getLogger(__name__)


def handle_2fa(timeout_seconds: float = 5.0, post_click_delay: float = 4.0, brand: str | None = None) -> bool:
    """Safe wrapper that attempts to reload/resend OTP and never raises.

    Returns True if reload/resend was clicked, False otherwise.
    """
    try:
        otp_visible, reload_clicked = check_and_reload_2fa(timeout_seconds=timeout_seconds, post_click_delay=post_click_delay)
        if reload_clicked and brand:
            try:
                mark_brand_verified(brand)
            except Exception:
                pass
        return bool(reload_clicked)
    except Exception as e:
        logger.debug('handle_2fa encountered error: %s', e)
        return False


def check_and_reload_2fa(timeout_seconds: float = 5.0, post_click_delay: float = 2.0) -> tuple[bool, bool]:
    """Check for OTP prompt (`2fa-otp.png`) and click reload (`reload-opt.png`).

    Returns a tuple: (otp_prompt_visible, reload_clicked).
    """
    try:
        import pyautogui
    except Exception as e:
        logger.debug('pyautogui not available for 2FA handling: %s', e)
        return False, False

    base_icons = Path(__file__).resolve().parents[1] / 'assets' / 'icons' / '2fa'
    otp_img = base_icons / '2fa-email.png'
    lang_btn = base_icons / 'button_language_en.png'
    # Previously we tried clicking a reload icon; replace with helper flow:
    # click `otp-helper.png` to reveal the OTP confirmation popup, then
    # click the first `2fa-email-confirm-link.png` if present.
    otp_helper_img = base_icons / 'otp-helper.png'
    email_confirm_img = base_icons / '2fa-email-confirm-link.png'
    verification_failed_img = base_icons / '2fa-verification-failed.png'

    # If a language-selection popup may appear before OTP, try clicking it first
    try:
        if lang_btn.exists():
            logger.debug('Looking for language button at %s', lang_btn)
            deadline_lang = time.time() + 5.0
            while time.time() < deadline_lang:
                try:
                    time.sleep(1.5)
                    loc_lang = pyautogui.locateCenterOnScreen(str(lang_btn), confidence=0.8)
                    if loc_lang:
                        logger.debug('Found language button at %s, clicking', loc_lang)
                        pyautogui.click(loc_lang.x, loc_lang.y)
                        time.sleep(1.5)
                        break
                except Exception as e:
                    logger.debug('Error locating/clicking language button: %s', e)
                time.sleep(0.2)
    except Exception as e:
        logger.debug('Error in language button handling, proceeding to OTP check: %s', e)
        # non-fatal, continue to OTP check

    if not otp_img.exists() and not verification_failed_img.exists():
        logger.debug('Neither OTP prompt nor verification-failed icon found (%s / %s)', otp_img, verification_failed_img)
        otp_visible = False
    else:
        otp_visible = False
        deadline = time.time() + float(timeout_seconds)
        while time.time() < deadline:
            try:
                loc = pyautogui.locateCenterOnScreen(str(otp_img), confidence=0.8)
                if loc:
                    otp_visible = True
                    logger.debug('Detected 2FA OTP prompt at %s', loc)
                    break
                # also consider a verification-failed dialog as a signal to attempt helper flow
                loc_fail = pyautogui.locateCenterOnScreen(str(verification_failed_img), confidence=0.8)
                if loc_fail:
                    otp_visible = True
                    logger.debug('Detected verification-failed dialog at %s', loc_fail)
                    break
            except Exception as e:
                logger.debug('Error locating OTP prompt image: %s', e)
            time.sleep(0.2)
    # If OTP prompt image was not detected on screen, skip helper/link steps
    if not otp_visible:
        logger.debug('OTP prompt not visible on screen; skipping helper/link actions')
        return False, False

    link_clicked = False
    # If an otp helper exists, click it to surface the confirmation links
    try:
        if otp_helper_img.exists():
            logger.debug('Looking for otp helper at %s', otp_helper_img)
            deadline_helper = time.time() + 3.0
            while time.time() < deadline_helper:
                try:
                    loc_h = pyautogui.locateCenterOnScreen(str(otp_helper_img), confidence=0.8)
                    if loc_h:
                        logger.debug('Found otp helper at %s, clicking', loc_h)
                        pyautogui.click(loc_h.x, loc_h.y)
                        time.sleep(1.0)
                        break
                except Exception as e:
                    logger.debug('Error locating/clicking otp helper: %s', e)
                time.sleep(0.2)
    except Exception:
        logging.debug('OTP helper image not found or error during helper click, proceeding to look for email confirm links if OTP prompt is visible')
        raise Exception('OTP helper handling failed, cannot proceed to click email confirm links')

    # After helper click, look for one or more email-confirm links and click the first
    try:
        if email_confirm_img.exists():
            logger.debug('Searching for email confirm links at %s', email_confirm_img)
            deadline_links = time.time() + 60
            retries_after_fail = 3
            while time.time() < deadline_links:
                try:
                    # locateAllOnScreen returns generators; pick first
                    locs = list(pyautogui.locateAllOnScreen(str(email_confirm_img), confidence=0.8))
                    if locs:
                        loc0 = locs[0]
                        logger.debug('Found email confirm link at %s, clicking', loc0)
                        pyautogui.click(loc0.left + loc0.width/2, loc0.top + loc0.height/2)
                        time.sleep(float(post_click_delay))
                        time.sleep(2.0)
                        # if verification-failed appears after clicking, retry helper+confirm a few times
                        loc_fail_post = None
                        try:
                            loc_fail_post = pyautogui.locateCenterOnScreen(str(verification_failed_img), confidence=0.8)
                        except Exception:
                            loc_fail_post = None
                        if loc_fail_post and retries_after_fail > 0:
                            logger.debug('Verification failed detected after click at %s, retrying helper+confirm (%s retries left)', loc_fail_post, retries_after_fail)
                            retries_after_fail -= 1
                            # attempt helper click again
                            try:
                                if otp_helper_img.exists():
                                    hloc = pyautogui.locateCenterOnScreen(str(otp_helper_img), confidence=0.8)
                                    if hloc:
                                        pyautogui.click(hloc.x, hloc.y)
                                        time.sleep(2.0)
                            except Exception as e:
                                logger.debug('Error retrying otp helper click: %s', e)
                            # continue loop to locate and click confirm again
                            continue
                        link_clicked = True
                        break
                except Exception as e:
                    logger.debug('Error locating/clicking email confirm links: %s', e)
                time.sleep(0.2)
        else:
            logger.debug('Email confirm link image not found at %s', email_confirm_img)
    except Exception:
        pass

    logger.debug('check_and_reload_2fa result: otp_visible=%s link_clicked=%s', otp_visible, link_clicked)
    return otp_visible, link_clicked
