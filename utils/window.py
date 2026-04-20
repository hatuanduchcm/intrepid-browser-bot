import logging
from pywinauto import Desktop
import time

_DESKTOP = None
_INTREPID_WINDOW = None


def get_desktop():
    global _DESKTOP
    if _DESKTOP is None:
        _DESKTOP = Desktop(backend='uia')
        logging.info("Desktop initialized")
    return _DESKTOP


def get_intrepid_window_bk(timeout=5):
    global _INTREPID_WINDOW
    if _INTREPID_WINDOW is not None:
        try:
            _INTREPID_WINDOW.set_focus()
            return _INTREPID_WINDOW
        except Exception:
            _INTREPID_WINDOW = None

    d = get_desktop()
    deadline = time.time() + timeout
    while time.time() < deadline:
        def _find_by_substrings(subs):
            try:
                for w in d.windows():
                    try:
                        title = (w.window_text() or '').lower()
                    except Exception:
                        continue
                    for s in subs:
                        if s in title:
                            try:
                                spec = d.window(handle=w.handle)
                                try:
                                    spec.wrapper_object().set_focus()
                                except Exception:
                                    try:
                                        w.set_focus()
                                    except Exception:
                                        pass
                                return spec
                            except Exception:
                                continue
            except Exception:
                return None
            return None

        try:
            active = d.get_active()
            try:
                atitle = active.window_text() or ''
            except Exception:
                atitle = ''
            if atitle and ('shopee' in atitle.lower() or 'intrepid' in atitle.lower() or 'lazada' in atitle.lower()):
                try:
                    spec = d.window(handle=active.handle)
                    try:
                        spec.wrapper_object().set_focus()
                    except Exception:
                        try:
                            active.set_focus()
                        except Exception:
                            pass
                    _INTREPID_WINDOW = spec
                    return spec
                except Exception:
                    pass
        except Exception:
            pass
        try:
            ws = d.window(title_re='.*(Shopee|Intrepid).*', control_type='Window')
            wr = ws.wrapper_object()
            wr.set_focus()
            _INTREPID_WINDOW = ws
            return ws
        except Exception:
            targets = ['shopee', 'intrepid', 'lazada', 'seller', 'seller center', 'sellercenter']
            spec = _find_by_substrings(targets)
            if spec:
                _INTREPID_WINDOW = spec
                return spec
            try:
                for w in d.windows():
                    try:
                        title = w.window_text() or ''
                    except Exception:
                        continue
                    if 'shopee' in title.lower() or 'intrepid' in title.lower():
                        try:
                            spec = d.window(handle=w.handle)
                            try:
                                spec.wrapper_object().set_focus()
                            except Exception:
                                try:
                                    w.set_focus()
                                except Exception:
                                    pass
                            _INTREPID_WINDOW = spec
                            return spec
                        except Exception:
                            continue
            except Exception:
                pass
            time.sleep(0.25)
    return None


def get_intrepid_window(timeout=5):
    global _INTREPID_WINDOW
    if _INTREPID_WINDOW is not None:
        try:
            # _INTREPID_WINDOW.set_focus()
            return _INTREPID_WINDOW
        except Exception:
            _INTREPID_WINDOW = None
    _INTREPID_WINDOW = select_target_window()
    return _INTREPID_WINDOW


def select_target_window(targets=None):
    if targets is None:
        targets = ['shopee', 'intrepid', 'lazada', 'seller', 'seller center', 'sellercenter']
    d = get_desktop()
    try:
        for w in d.windows():
            try:
                title = (w.window_text() or '').lower()
                logging.debug('Checking window: %s', title)
            except Exception as e:
                logging.debug('Error getting window text for %s: %s', w, e)
                continue
            for s in targets:
                if s in title:
                    try:
                        spec = d.window(handle=w.handle)
                        try:
                            spec.wrapper_object().set_focus()
                        except Exception:
                            try:
                                w.set_focus()
                            except Exception:
                                pass
                        logging.info('Focused target window: %s', title)
                        return spec
                    except Exception:
                        logging.debug('Error accessing window %s', title)
                        continue
    except Exception as e:
        logging.debug('Error enumerating windows: %s', e)
        return None
    return None
