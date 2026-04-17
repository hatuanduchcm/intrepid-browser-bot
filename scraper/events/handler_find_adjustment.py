from src.scraper import find_adjustment_text

def handle_find_adjustment(event_payload, win=None):
    # win can be passed (pywinauto window) or discovered inside
    d = find_adjustment_text(win) if win else find_adjustment_text(None)
    return d
