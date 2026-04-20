import json
import time
import logging
import pyautogui
logger = logging.getLogger(__name__)


def handle_clean_brand_box(event_payload=None):
    """Read saved click coords and click to clear the brand search box."""

    try:
        from pathlib import Path
        dbg = Path(__file__).resolve().parents[2] / 'assets' / 'debug_matches'
        p = dbg / 'last_search_click.json'
        if not p.exists():
            logger.debug('No last_search_click.json found')
            return False
        data = json.loads(p.read_text())
        x = int(data.get('x'))
        y = int(data.get('y'))
        # click to focus the box, select all and delete content
        pyautogui.moveTo(x, y, duration=0.1)
        pyautogui.click(x, y)
        time.sleep(0.08)
        try:
            pyautogui.hotkey('ctrl', 'a', interval=0.05)
            time.sleep(0.04)
            pyautogui.press('backspace', presses=2, interval=0.02)
            # Move mouse out of box
            pyautogui.moveTo(10, 10)
            time.sleep(0.2)
        except Exception:
            # fallback: send several backspaces
            for _ in range(6):
                pyautogui.press('backspace', presses=2, interval=0.02)
                time.sleep(0.02)
        return True
    except Exception as e:
        logger.debug('clean_brand_box failed: %s', e)
        return False
