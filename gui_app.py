"""
GUI entry point for Invoice Adjustment Bot.
Run: python gui_app.py
Build exe: build_exe.bat
"""
# ── DPI awareness (must be BEFORE tkinter is imported) ───────────────────────
import ctypes, sys as _sys
try:
    if _sys.platform == "win32":
        # Per-monitor v2: sharpest on multi-monitor / laptop+external setups
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import multiprocessing as mp
import logging
import queue
import os
import sys
import json
import threading
import zipfile
import tempfile
import subprocess
import urllib.request
from pathlib import Path
from dotenv import load_dotenv, set_key
from PIL import Image, ImageTk

# Load .env from project root (works both in dev and after PyInstaller bundle)
_BASE_DIR = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
# --onedir: exe nằm trong dist/AppName/, .env để cùng thư mục đó
_PROJECT_ROOT = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
_ENV_FILE = _PROJECT_ROOT / '.env'
load_dotenv(_ENV_FILE)

# ── Version & Update ───────────────────────────────────────────────────
_VERSION_FILE = _BASE_DIR / 'version.txt'
if not _VERSION_FILE.exists():
    _VERSION_FILE = _PROJECT_ROOT / 'version.txt'
APP_VERSION = _VERSION_FILE.read_text(encoding='utf-8').strip() if _VERSION_FILE.exists() else '0.0.0'

GITHUB_REPO = 'hatuanduc/intrepid-browser-bot-dist'
GITHUB_API_LATEST = f'https://api.github.com/repos/{GITHUB_REPO}/releases/latest'

# ── Locale loader ─────────────────────────────────────────────────────────────
_LOCALES_DIR = Path(__file__).parent / 'locales'   # dev path
if not _LOCALES_DIR.exists():
    _LOCALES_DIR = _BASE_DIR / 'locales'            # bundled path

def _load_locale(lang: str) -> dict:
    path = _LOCALES_DIR / f"{lang}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

LOCALES = {
    "vi": _load_locale("vi"),
    "en": _load_locale("en"),
}

# ── Auto-configure Tesseract: bundled copy takes priority over system install ──
def _setup_tesseract():
    import pytesseract
    # 1. Bundled inside exe (PyInstaller _MEIPASS)
    bundled = _BASE_DIR / 'Tesseract-OCR' / 'tesseract.exe'
    if bundled.exists():
        pytesseract.pytesseract.tesseract_cmd = str(bundled)
        os.environ['TESSDATA_PREFIX'] = str(_BASE_DIR / 'Tesseract-OCR')
        return
    # 2. Env override
    env_cmd = os.getenv('TESSERACT_CMD')
    if env_cmd and Path(env_cmd).exists():
        pytesseract.pytesseract.tesseract_cmd = env_cmd
        return
    # 3. Default system path
    default = Path(r'C:\Program Files\Tesseract-OCR\tesseract.exe')
    if default.exists():
        pytesseract.pytesseract.tesseract_cmd = str(default)

try:
    _setup_tesseract()
except Exception:
    pass

# --- Logging bridge: redirect Python logging → tkinter Text widget via Queue ---
class _QueueHandler(logging.Handler):
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        try:
            self.log_queue.put_nowait(self.format(record))
        except Exception:
            pass


# ── Bot subprocess entry point (must be at module level for pickling) ─────────
def _bot_process_target(sheet_id: str, sheet_name: str, log_queue, project_root: str, stats_queue=None):
    """Runs the bot in a separate process so it can be terminated instantly."""
    import logging as _log
    from pathlib import Path as _Path
    from dotenv import load_dotenv as _load_dotenv
    import os as _os
    import sys as _sys

    # Add project root to path so imports work from subprocess
    if project_root not in _sys.path:
        _sys.path.insert(0, project_root)
    _os.chdir(project_root)

    # Wire logging → shared mp.Queue
    _handler = _QueueHandler(log_queue)
    _handler.setFormatter(_log.Formatter("%(levelname)s | %(name)s | %(message)s"))
    _root = _log.getLogger()
    _root.setLevel(_log.DEBUG)
    _root.handlers.clear()
    _root.addHandler(_handler)

    # Re-load .env inside subprocess
    _load_dotenv(_Path(project_root) / '.env')
    _os.environ["GSHEET_ID"] = sheet_id
    _os.environ["GSHEET_SHEET_NAME"] = sheet_name

    from main import run_batch_process
    run_batch_process(sheet_id, sheet_name, stats_queue=stats_queue)


# ── Theme definitions ─────────────────────────────────────────────────────────
THEMES = {
    "dark": {
        "bg":           "#1e1e2e",
        "bg2":          "#313244",
        "bg3":          "#11111b",
        "fg":           "#cdd6f4",
        "fg2":          "#a6adc8",
        "accent":       "#a6e3a1",
        "accent_fg":    "#1e1e2e",
        "danger":       "#e5194a",
        "danger_fg":    "#ffffff",
        "btn_neutral":  "#45475a",
        "btn_neu_fg":   "#cdd6f4",
        "entry_bg":     "#313244",
        "label_frame":  "#89b4fa",
        "settings_fg":  "#a6e3a1",
        "log_error":    "#f38ba8",
        "log_warning":  "#fab387",
        "log_info":     "#a6e3a1",
        "log_debug":    "#6c7086",
        "progress_bg":  "#313244",
        "toggle_text":  "☀ Light",
    },
    "light": {
        "bg":           "#eff1f5",
        "bg2":          "#dce0e8",
        "bg3":          "#ffffff",
        "fg":           "#4c4f69",
        "fg2":          "#6c6f85",
        "accent":       "#40a02b",
        "accent_fg":    "#ffffff",
        "danger":       "#d20f39",
        "danger_fg":    "#ffffff",
        "btn_neutral":  "#bcc0cc",
        "btn_neu_fg":   "#4c4f69",
        "entry_bg":     "#dce0e8",
        "label_frame":  "#1e66f5",
        "settings_fg":  "#40a02b",
        "log_error":    "#d20f39",
        "log_warning":  "#df8e1d",
        "log_info":     "#40a02b",
        "log_debug":    "#9ca0b0",
        "progress_bg":  "#dce0e8",
        "toggle_text":  "🌙 Dark",
    },
}

# ── Settings Dialog ───────────────────────────────────────────────────────────

class _SettingsDialog(tk.Toplevel):
    """Modal dialog to view/edit important .env variables."""

    # (env_key, locale_label_key, is_password, is_path, is_json)
    _GSHEET_FIELDS = [
        ('GSHEET_ID',                    'settings_label_sheet_id',   False, False, False),
        ('GSHEET_SHEET_NAME',            'settings_label_sheet_name', False, False, False),
        ('GOOGLE_SERVICE_ACCOUNT_PATH',  'settings_label_sa_json',    False, True,  False),
    ]
    _INTREPID_FIELDS = [
        ('INTREPID_USER_TEMPLATE', 'settings_label_user_tpl', False, False, False),
        ('INTREPID_PASS',          'settings_label_pass',     True,  False, False),
    ]
    _INTREPID_ID_FIELDS = [
        ('INTREPID_USER_ID',  'settings_label_user_id',  False, False, False),
        ('INTREPID_PASS_ID',  'settings_label_pass_id',  True,  False, False),
    ]

    def __init__(self, parent: 'BotApp'):
        super().__init__(parent)
        self._parent = parent
        L = parent._locale
        t = parent._theme

        self.title(L.get('settings_dialog_title', 'Settings'))
        self.configure(bg=t['bg'])
        self.resizable(True, True)
        self.minsize(720, 600)
        self.grab_set()   # modal

        self._vars:      dict[str, tk.StringVar] = {}
        self._textareas: dict[str, tk.Text]      = {}  # for multiline JSON path
        self._eye_btns:  dict[str, tk.Button]    = {}
        self._show_pass: dict[str, bool]         = {}

        # scrollable body
        outer = tk.Frame(self, bg=t['bg'])
        outer.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(outer, bg=t['bg'], highlightthickness=0)
        vsb = ttk.Scrollbar(outer, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        body = tk.Frame(canvas, bg=t['bg'])
        _body_id = canvas.create_window((0, 0), window=body, anchor='nw')
        def _on_resize(e):
            canvas.itemconfigure(_body_id, width=e.width)
        canvas.bind('<Configure>', _on_resize)
        body.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        # mouse-wheel scroll
        def _on_mousewheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), 'units')
        canvas.bind_all('<MouseWheel>', _on_mousewheel)
        self.bind('<Destroy>', lambda e: canvas.unbind_all('<MouseWheel>'))

        body.columnconfigure(0, weight=1)

        def _section(label_key):
            lf = tk.LabelFrame(body, text=L.get(label_key, label_key),
                               font=('Segoe UI', 10), bg=t['bg'],
                               fg=t['settings_fg'], bd=1, relief=tk.GROOVE)
            lf.pack(fill=tk.X, padx=12, pady=(0, 10))
            lf.columnconfigure(1, weight=1)
            return lf

        def _add_field(frame, row, env_key, label_key, is_password, is_path, is_json=False):
            tk.Label(frame, text=L.get(label_key, label_key),
                     bg=t['bg'], fg=t['fg'],
                     font=('Segoe UI', 9), anchor=tk.W,
                     width=22).grid(row=row, column=0, sticky=tk.NW, padx=(8, 4), pady=6)

            cell = tk.Frame(frame, bg=t['bg'])
            cell.grid(row=row, column=1, sticky=tk.EW, padx=(0, 8), pady=6)
            cell.columnconfigure(0, weight=1)

            if is_path:
                # multiline Text widget — accepts file path OR raw JSON content
                txt = tk.Text(cell, height=6, wrap=tk.WORD,
                              bg=t['entry_bg'], fg=t['fg'], insertbackground=t['fg'],
                              relief=tk.FLAT, font=('Consolas', 9))
                txt.insert('1.0', os.getenv(env_key, ''))
                txt.grid(row=0, column=0, sticky=tk.EW)
                self._textareas[env_key] = txt

                def _browse(w=txt):
                    from tkinter import filedialog
                    path = filedialog.askopenfilename(
                        title=L.get('browse_dialog_title', 'Select file'),
                        filetypes=[('JSON files', '*.json'), ('All files', '*.*')]
                    )
                    if path:
                        w.delete('1.0', tk.END)
                        w.insert('1.0', path)
                tk.Button(cell, text='…', command=_browse,
                          bg=t['btn_neutral'], fg=t['btn_neu_fg'],
                          relief=tk.FLAT, font=('Segoe UI', 9),
                          padx=8, cursor='hand2').grid(row=0, column=1, sticky=tk.N, padx=(4, 0))
            else:
                var = tk.StringVar(value=os.getenv(env_key, ''))
                self._vars[env_key] = var
                entry = tk.Entry(
                    cell, textvariable=var,
                    show='•' if is_password else '',
                    bg=t['entry_bg'], fg=t['fg'], insertbackground=t['fg'],
                    relief=tk.FLAT, font=('Consolas', 9),
                )
                entry.grid(row=0, column=0, sticky=tk.EW)

                if is_password:
                    self._show_pass[env_key] = False
                    def _toggle(ek=env_key, e=entry):
                        self._show_pass[ek] = not self._show_pass[ek]
                        e.configure(show='' if self._show_pass[ek] else '•')
                        self._eye_btns[ek].configure(
                            text='🙈' if self._show_pass[ek] else '👁')
                    eye = tk.Button(cell, text='👁', command=_toggle,
                                    bg=t['bg2'], fg=t['fg'], relief=tk.FLAT,
                                    font=('Segoe UI', 10), padx=6, cursor='hand2')
                    eye.grid(row=0, column=1, padx=(4, 0))
                    self._eye_btns[env_key] = eye

        # ── Section: Google Sheet ─────────────────────────────────────────────
        gs = _section('settings_section_gsheet')
        for i, (ek, lk, pw, fp, jj) in enumerate(self._GSHEET_FIELDS):
            _add_field(gs, i, ek, lk, pw, fp, jj)

        # ── Section: Intrepid Browser ─────────────────────────────────────────
        ib = _section('settings_section_intrepid')
        for i, (ek, lk, pw, fp, jj) in enumerate(self._INTREPID_FIELDS):
            _add_field(ib, i, ek, lk, pw, fp, jj)

        # ── Section: Intrepid ID (special) ────────────────────────────────────
        ii = _section('settings_section_intrepid_id')
        for i, (ek, lk, pw, fp, jj) in enumerate(self._INTREPID_ID_FIELDS):
            _add_field(ii, i, ek, lk, pw, fp, jj)

        # bottom padding inside scroll area
        tk.Frame(body, bg=t['bg'], height=8).pack()

        # ── Buttons (outside scroll) ──────────────────────────────────────────
        btn_row = tk.Frame(self, bg=t['bg2'])
        btn_row.pack(fill=tk.X, padx=0, pady=0)
        tk.Button(btn_row, text=L.get('settings_btn_save', 'Save'),
                  command=self._save,
                  bg=t['accent'], fg=t['accent_fg'],
                  font=('Segoe UI', 10, 'bold'),
                  relief=tk.FLAT, padx=20, pady=8, cursor='hand2',
                  ).pack(side=tk.LEFT, padx=16, pady=10)
        tk.Button(btn_row, text=L.get('settings_btn_cancel', 'Cancel'),
                  command=self.destroy,
                  bg=t['btn_neutral'], fg=t['btn_neu_fg'],
                  font=('Segoe UI', 10),
                  relief=tk.FLAT, padx=20, pady=8, cursor='hand2',
                  ).pack(side=tk.LEFT)

        # center on parent
        self.update_idletasks()
        pw_x = parent.winfo_x() + (parent.winfo_width()  - self.winfo_width())  // 2
        pw_y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f'800x640+{pw_x}+{pw_y}')

    def _save(self):
        all_fields = self._GSHEET_FIELDS + self._INTREPID_FIELDS + self._INTREPID_ID_FIELDS
        for env_key, _, _, is_path, _ in all_fields:
            if is_path and env_key in self._textareas:
                val = self._textareas[env_key].get('1.0', tk.END).strip()
            else:
                val = self._vars.get(env_key, tk.StringVar()).get().strip()
            os.environ[env_key] = val
            try:
                if _ENV_FILE.exists():
                    set_key(str(_ENV_FILE), env_key, val)
            except Exception:
                pass
        # sync sheet fields back to main window
        try:
            self._parent._sheet_id_var.set(os.getenv('GSHEET_ID', ''))
            self._parent._sheet_name_var.set(os.getenv('GSHEET_SHEET_NAME', ''))
            self._parent._sa_path_var.set(os.getenv('GOOGLE_SERVICE_ACCOUNT_PATH', ''))
        except Exception:
            pass
        msg = self._parent._locale.get('settings_saved', 'Settings saved.')
        messagebox.showinfo(
            self._parent._locale.get('settings_dialog_title', 'Settings'), msg, parent=self)
        self.destroy()


# ── Main App ──────────────────────────────────────────────────────────────────

class BotApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Invoice Adjustment Bot")
        self.resizable(True, True)
        self.minsize(640, 520)

        # Set icon — iconbitmap only (wm_iconphoto causes blurry rendering)
        _ico = _PROJECT_ROOT / 'assets' / 'app_icon.ico'
        _ico_meipass = _BASE_DIR / 'assets' / 'app_icon.ico'
        _icon_path = _ico if _ico.exists() else (_ico_meipass if _ico_meipass.exists() else None)
        if _icon_path:
            try:
                self.iconbitmap(default=str(_icon_path))
            except Exception:
                pass

        self._bot_process: mp.Process | None = None
        self._log_queue: queue.Queue = queue.Queue()
        self._proc_log_queue: mp.Queue = mp.Queue()
        self._stats_queue: mp.Queue = mp.Queue()
        # Order statistics (reset each run)
        self._stat_skip: int = 0
        self._stat_success: int = 0
        self._stat_errors: list = []

        # Load saved theme preference (default: dark)
        saved_theme = os.getenv("GUI_THEME", "dark")
        self._theme_name = saved_theme if saved_theme in THEMES else "dark"
        self._theme = THEMES[self._theme_name]

        # Load saved language preference (default: vi)
        saved_lang = os.getenv("GUI_LANG", "vi")
        self._lang = saved_lang if saved_lang in LOCALES else "vi"
        self._locale = LOCALES[self._lang]

        self._all_widgets: list = []  # track for theme/lang updates
        self._flag_imgs: dict = self._load_flag_images()
        self._current_status_key: str = "status_ready"
        self._blink_on: bool = False
        self._update_zip_path: str | None = None   # path to downloaded update ZIP
        self._build_ui()
        self._setup_logging()
        self._poll_log_queue()
        # Start background update check after UI is ready
        threading.Thread(target=self._check_update_bg, daemon=True).start()

    # ── Flag images ──────────────────────────────────────────────────────────

    @staticmethod
    def _load_flag_images(w: int = 48, h: int = 30) -> dict:
        """Load vi.png / en.png from assets/flags/ and return {lang: PhotoImage}."""
        flags = {}
        for lang in ("vi", "en"):
            for base in (_BASE_DIR, _PROJECT_ROOT):
                path = base / "assets" / "flags" / f"{lang}.png"
                if path.exists():
                    try:
                        img = Image.open(str(path)).convert("RGBA").resize((w, h), Image.LANCZOS)
                        flags[lang] = ImageTk.PhotoImage(img)
                    except Exception:
                        pass
                    break
        return flags

    def _target_lang(self) -> str:
        """Language that the toggle button will switch TO."""
        return "en" if self._lang == "vi" else "vi"

    # ── Theme ─────────────────────────────────────────────────────────────────

    def _apply_theme(self):
        t = self._theme
        self.configure(bg=t["bg"])

        # Keep indicator dot background in sync
        try:
            self._indicator.configure(bg=t["bg"])
        except Exception:
            pass

        for w, role in self._all_widgets:
            try:
                if role == "bg":        w.configure(bg=t["bg"])
                elif role == "bg2":     w.configure(bg=t["bg2"])
                elif role == "bg3":     w.configure(bg=t["bg3"])
                elif role == "header":  w.configure(bg=t["bg2"])
                elif role == "header_label": w.configure(bg=t["bg2"], fg=t["fg"])
                elif role == "label":   w.configure(bg=t["bg"], fg=t["fg"])
                elif role == "lf_settings":
                    w.configure(bg=t["bg"], fg=t["settings_fg"])
                elif role == "lf_log":
                    w.configure(bg=t["bg"], fg=t["label_frame"])
                elif role == "lf_stats":
                    w.configure(bg=t["bg"], fg=t["label_frame"])
                elif role == "lf_error_list":
                    w.configure(bg=t["bg"], fg=t["log_error"])
                elif role == "entry":
                    w.configure(bg=t["entry_bg"], fg=t["fg"], insertbackground=t["fg"])
                elif role == "entry_frame":
                    w.configure(bg=t["bg"])
                elif role == "btn_run":
                    if self._bot_process and self._bot_process.is_alive():
                        w.configure(bg=t["danger"], fg=t["danger_fg"])
                    else:
                        w.configure(bg=t["accent"], fg=t["accent_fg"])
                elif role == "btn_neutral":
                    w.configure(bg=t["btn_neutral"], fg=t["btn_neu_fg"])
                elif role == "btn_toggle":
                    w.configure(bg=t["bg2"], fg=t["fg"])
                elif role == "btn_lang":
                    w.configure(bg=t["bg2"], activebackground=t["bg2"])
                elif role == "status":
                    w.configure(bg=t["bg"], fg=t["fg2"])
                elif role == "stat_skip":
                    w.configure(bg=t["bg"], fg=t["fg2"])
                elif role == "stat_success":
                    w.configure(bg=t["bg"], fg=t["log_info"])
                elif role == "stat_error":
                    err_count = len(self._stat_errors)
                    w.configure(bg=t["bg"], fg=t["log_error"] if err_count > 0 else t["fg2"])
                    w.tag_config("ERROR",   foreground=t["log_error"])
                    w.tag_config("WARNING", foreground=t["log_warning"])
                    w.tag_config("INFO",    foreground=t["log_info"])
                    w.tag_config("DEBUG",   foreground=t["log_debug"])
            except Exception:
                pass

        # ttk progressbar
        style = ttk.Style(self)
        style.configure("bot.Horizontal.TProgressbar",
                        troughcolor=t["progress_bg"],
                        background=t["accent"], thickness=4)
        # Error listbox colors
        try:
            self._error_listbox.configure(bg=t["bg3"], fg=t["fg"],
                                          selectbackground=t["bg2"],
                                          selectforeground=t["log_error"])
            self._error_list_frame.configure(bg=t["bg"])
        except Exception:
            pass

    def _toggle_theme(self):
        self._theme_name = "light" if self._theme_name == "dark" else "dark"
        self._theme = THEMES[self._theme_name]
        self._apply_theme()
        self._apply_locale()  # re-apply so toggle_text on theme btn stays correct
        try:
            if _ENV_FILE.exists():
                set_key(str(_ENV_FILE), "GUI_THEME", self._theme_name)
            os.environ["GUI_THEME"] = self._theme_name
        except Exception:
            pass

    # ── Status helper ──────────────────────────────────────────────────────
    _STATUS_COLORS = {
        "status_ready":   "#a6e3a1",  # green
        "status_running": "#89dceb",  # cyan (blinks)
        "status_done":    "#a6e3a1",  # green
        "status_stopped": "#f38ba8",  # red
        "status_stopping":"#fab387",  # orange
    }

    def _set_status(self, key: str):
        self._current_status_key = key
        self._status_var.set(self._(key))
        color = self._STATUS_COLORS.get(key, "#a6adc8")
        self._indicator.configure(fg=color)
        # start/stop blink
        if key == "status_running":
            self._blink_on = True
            self._blink()
        else:
            self._blink_on = False

    def _blink(self):
        if not self._blink_on:
            # restore solid color when stopped
            color = self._STATUS_COLORS.get(self._current_status_key, "#a6adc8")
            self._indicator.configure(fg=color)
            return
        current = self._indicator.cget("fg")
        next_color = "#89dceb" if current == "#1e1e2e" or current == self._theme.get("bg", "#1e1e2e") else "#1e1e2e"
        self._indicator.configure(fg=next_color)
        self.after(500, self._blink)

    # ── Locale ────────────────────────────────────────────────────────────────

    def _(self, key: str) -> str:
        """Translate key using current locale, fallback to key itself."""
        return self._locale.get(key, key)

    def _apply_locale(self):
        """Update all labelled widgets with current locale strings."""
        L = self._locale
        t = self._theme
        try:
            self.title(L.get("app_title", "Invoice Adjustment Bot"))
            self._header_lbl.configure(text=L.get("header_title", ""))
            self._settings_lf.configure(text=L.get("section_settings", ""))
            self._lbl_sheet_id.configure(text=L.get("label_sheet_id", ""))
            self._lbl_sheet_name.configure(text=L.get("label_sheet_name", ""))
            self._lbl_sa_json.configure(text=L.get("label_sa_json", ""))
            self._btn_browse.configure(text=L.get("btn_browse", ""))
            _is_running = bool(self._bot_process and self._bot_process.is_alive())
            self._run_btn.configure(text=L.get("btn_stop" if _is_running else "btn_run", ""))
            self._btn_clear.configure(text=L.get("btn_clear_log", ""))
            self._settings_btn.configure(text="⚙  " + L.get("settings_dialog_title", "Settings"))
            self._log_lf.configure(text=L.get("section_log", ""))
            self._log_lf.configure(fg=t["label_frame"])
            # Theme toggle text depends on current theme
            theme_key = "toggle_theme_to_light" if self._theme_name == "dark" else "toggle_theme_to_dark"
            self._toggle_btn.configure(text=L.get(theme_key, ""))
            # Lang toggle shows the flag of the CURRENT language
            _flag_img = self._flag_imgs.get(self._lang)
            if _flag_img:
                self._lang_btn.configure(image=_flag_img, text="")
                self._lang_btn._flag_ref = _flag_img
            else:
                self._lang_btn.configure(image="", text=L.get("toggle_lang", ""))
            # Sync status text to current language
            self._set_status(self._current_status_key)
            # Update stats section
            self._stats_lf.configure(text=L.get("section_stats", ""))
            self._update_stat_labels()
        except Exception:
            pass

    def _toggle_lang(self):
        self._lang = "en" if self._lang == "vi" else "vi"
        self._locale = LOCALES[self._lang]
        self._apply_locale()
        try:
            if _ENV_FILE.exists():
                set_key(str(_ENV_FILE), "GUI_LANG", self._lang)
            os.environ["GUI_LANG"] = self._lang
        except Exception:
            pass

    def _open_settings(self):
        _SettingsDialog(self)

    def _reg(self, widget, role: str):
        """Register widget for theme tracking."""
        self._all_widgets.append((widget, role))
        return widget

    # ── Auto-update ───────────────────────────────────────────────────────────────

    def _check_update_bg(self):
        """Background thread: check GitHub latest release, download ZIP if newer."""
        try:
            req = urllib.request.Request(
                GITHUB_API_LATEST,
                headers={"Accept": "application/vnd.github+json", "User-Agent": "InvoiceAdjBot"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            latest_tag = data.get("tag_name", "").lstrip("v")
            if not latest_tag or latest_tag == APP_VERSION:
                return
            # Find ZIP asset
            zip_url = None
            for asset in data.get("assets", []):
                if asset["name"].endswith(".zip"):
                    zip_url = asset["browser_download_url"]
                    break
            if not zip_url:
                return
            # Download to temp file (background, shows progress via after())
            tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
            tmp.close()
            self.after(0, lambda: self._show_update_downloading(latest_tag))
            urllib.request.urlretrieve(zip_url, tmp.name, reporthook=self._download_progress)
            self._update_zip_path = tmp.name
            self.after(0, lambda: self._show_update_ready(latest_tag))
        except Exception:
            pass  # silently ignore: offline / API rate limit etc.

    def _download_progress(self, block_num, block_size, total_size):
        if total_size <= 0:
            return
        downloaded = block_num * block_size
        pct = min(int(downloaded * 100 / total_size), 99)
        self.after(0, lambda p=pct: self._update_banner.configure(
            text=f"📥 Đang tải bản mới... {p}%"
        ))

    def _show_update_downloading(self, tag: str):
        self._update_banner.configure(text=f"📥 Đang tải bản mới {tag}...")
        self._update_banner.pack(side=tk.LEFT, padx=(8, 0))

    def _show_update_ready(self, tag: str):
        self._update_banner.configure(
            text=f"🔄 Cập nhật v{tag} sẵn sàng — Nhấp để khởi động lại",
            bg="#a6e3a1", fg="#1e1e2e",
        )
        self._update_banner.pack(side=tk.LEFT, padx=(8, 0))

    def _apply_update(self):
        if not self._update_zip_path or not Path(self._update_zip_path).exists():
            return
        app_dir = str(_PROJECT_ROOT)
        zip_path = self._update_zip_path
        exe_path = str(Path(sys.executable))

        # Write updater.bat into temp dir — runs after this process exits
        bat_lines = [
            "@echo off",
            "timeout /t 2 /nobreak >nul",
            f'powershell -Command "Expand-Archive -Path \'\'{zip_path}\'\' -DestinationPath \'\'{app_dir}\'\'  -Force"',
            f'del /f /q "{zip_path}"',
            f'start "" "{exe_path}"',
            f'del /f /q "%~f0"',   # self-delete
        ]
        bat_path = Path(tempfile.gettempdir()) / "iab_updater.bat"
        bat_path.write_text("\n".join(bat_lines), encoding="utf-8")
        subprocess.Popen(["cmd", "/c", str(bat_path)], creationflags=subprocess.CREATE_NO_WINDOW)
        self.destroy()
        sys.exit(0)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        t = self._theme
        self.configure(bg=t["bg"])

        # ── Header ──────────────────────────────────────────────────────────
        header = self._reg(tk.Frame(self, bg=t["bg2"], pady=10), "header")
        header.pack(fill=tk.X)

        self._header_lbl = self._reg(tk.Label(
            header,
            text=self._("header_title"),
            font=("Segoe UI", 16, "bold"),
            bg=t["bg2"], fg=t["fg"],
        ), "header_label")
        self._header_lbl.pack(side=tk.LEFT, expand=True)

        # Update banner (hidden by default, shown when update ready)
        self._update_banner = tk.Button(
            header,
            text="",
            command=self._apply_update,
            bg="#a6e3a1", fg="#1e1e2e",
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT, padx=10, pady=4, cursor="hand2", bd=0,
        )
        # Don't pack yet — shown only when update available
        _flag_img = self._flag_imgs.get(self._lang)
        self._lang_btn = self._reg(tk.Button(
            header,
            image=_flag_img if _flag_img else None,
            text="" if _flag_img else self._("toggle_lang"),
            command=self._toggle_lang,
            bg=t["bg2"], activebackground=t["bg2"],
            relief=tk.FLAT, padx=6, pady=4, cursor="hand2", bd=0,
        ), "btn_lang")
        if _flag_img:
            self._lang_btn._flag_ref = _flag_img  # keep GC reference
        self._lang_btn.pack(side=tk.RIGHT, padx=(0, 4))

        # Theme toggle button
        theme_key = "toggle_theme_to_light" if self._theme_name == "dark" else "toggle_theme_to_dark"
        self._toggle_btn = self._reg(tk.Button(
            header,
            text=self._(theme_key),
            command=self._toggle_theme,
            bg=t["bg2"], fg=t["fg"],
            font=("Segoe UI", 9),
            relief=tk.FLAT, padx=10, pady=4, cursor="hand2", bd=0,
        ), "btn_toggle")
        self._toggle_btn.pack(side=tk.RIGHT, padx=12)

        # ── Settings frame ─────────────────────────────────────────────────────────
        self._settings_lf = self._reg(tk.LabelFrame(
            self, text=self._("section_settings"), font=("Segoe UI", 10),
            bg=t["bg"], fg=t["settings_fg"], bd=1, relief=tk.GROOVE
        ), "lf_settings")
        settings = self._settings_lf
        settings.pack(fill=tk.X, padx=16, pady=(12, 4))

        # Row 0 — Sheet ID
        self._lbl_sheet_id = self._reg(tk.Label(settings, text=self._("label_sheet_id"), bg=t["bg"], fg=t["fg"],
                 font=("Segoe UI", 10)), "label")
        self._lbl_sheet_id.grid(row=0, column=0, sticky=tk.W, padx=8, pady=6)
        self._sheet_id_var = tk.StringVar(value=os.getenv("GSHEET_ID", ""))
        self._reg(tk.Entry(settings, textvariable=self._sheet_id_var, width=58,
                 bg=t["entry_bg"], fg=t["fg"], insertbackground=t["fg"],
                 relief=tk.FLAT, font=("Consolas", 9)), "entry").grid(row=0, column=1, sticky=tk.EW, padx=8, pady=6)

        # Row 1 — Sheet Name
        self._lbl_sheet_name = self._reg(tk.Label(settings, text=self._("label_sheet_name"), bg=t["bg"], fg=t["fg"],
                 font=("Segoe UI", 10)), "label")
        self._lbl_sheet_name.grid(row=1, column=0, sticky=tk.W, padx=8, pady=6)
        self._sheet_name_var = tk.StringVar(value=os.getenv("GSHEET_SHEET_NAME", ""))
        self._reg(tk.Entry(settings, textvariable=self._sheet_name_var, width=58,
                 bg=t["entry_bg"], fg=t["fg"], insertbackground=t["fg"],
                 relief=tk.FLAT, font=("Consolas", 9)), "entry").grid(row=1, column=1, sticky=tk.EW, padx=8, pady=6)

        # Row 2 — Service Account JSON path
        self._lbl_sa_json = self._reg(tk.Label(settings, text=self._("label_sa_json"), bg=t["bg"], fg=t["fg"],
                 font=("Segoe UI", 10)), "label")
        self._lbl_sa_json.grid(row=2, column=0, sticky=tk.W, padx=8, pady=6)
        json_frame = self._reg(tk.Frame(settings, bg=t["bg"]), "entry_frame")
        json_frame.grid(row=2, column=1, sticky=tk.EW, padx=8, pady=6)
        self._sa_path_var = tk.StringVar(value=os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH", ""))
        self._reg(tk.Entry(json_frame, textvariable=self._sa_path_var, width=46,
                 bg=t["entry_bg"], fg=t["fg"], insertbackground=t["fg"],
                 relief=tk.FLAT, font=("Consolas", 9)), "entry").pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._btn_browse = self._reg(tk.Button(json_frame, text=self._("btn_browse"), command=self._browse_sa_json,
                  bg=t["btn_neutral"], fg=t["btn_neu_fg"], relief=tk.FLAT,
                  font=("Segoe UI", 9), padx=6), "btn_neutral")
        self._btn_browse.pack(side=tk.LEFT, padx=(4, 0))

        settings.columnconfigure(1, weight=1)

        # ── Control buttons ───────────────────────────────────────────────────
        btn_frame = self._reg(tk.Frame(self, bg=t["bg"]), "bg")
        btn_frame.pack(fill=tk.X, padx=16, pady=8)

        self._run_btn = self._reg(tk.Button(
            btn_frame, text=self._("btn_run"), command=self._on_toggle,
            bg=t["accent"], fg=t["accent_fg"],
            font=("Segoe UI", 11, "bold"),
            relief=tk.FLAT, padx=16, pady=8, cursor="hand2",
            width=8,
        ), "btn_run")
        self._run_btn.pack(side=tk.LEFT, padx=(0, 8))

        self._btn_clear = self._reg(tk.Button(
            btn_frame, text=self._("btn_clear_log"), command=self._clear_log,
            bg=t["btn_neutral"], fg=t["btn_neu_fg"],
            font=("Segoe UI", 10),
            relief=tk.FLAT, padx=12, pady=8, cursor="hand2",
        ), "btn_neutral")
        self._btn_clear.pack(side=tk.LEFT)

        self._settings_btn = self._reg(tk.Button(
            btn_frame, text="⚙  "+self._("settings_dialog_title"), command=self._open_settings,
            bg=t["btn_neutral"], fg=t["btn_neu_fg"],
            font=("Segoe UI", 10),
            relief=tk.FLAT, padx=12, pady=8, cursor="hand2",
        ), "btn_neutral")
        self._settings_btn.pack(side=tk.LEFT, padx=(8, 0))

        # Status indicator (colored dot) + text
        self._status_var = tk.StringVar(value=self._("status_ready"))
        self._reg(tk.Label(btn_frame, textvariable=self._status_var,
                 bg=t["bg"], fg=t["fg2"],
                 font=("Segoe UI", 10)), "status").pack(side=tk.RIGHT, padx=(0, 4))
        self._indicator = tk.Label(
            btn_frame, text="●", font=("Segoe UI", 13),
            bg=t["bg"], fg="#a6e3a1",  # green = ready
        )
        self._indicator.pack(side=tk.RIGHT)

        # ── Progress bar ──────────────────────────────────────────────────────
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("bot.Horizontal.TProgressbar",
                        troughcolor=t["progress_bg"], background=t["accent"], thickness=4)
        self._progress = ttk.Progressbar(
            self, mode="indeterminate", length=200,
            style="bot.Horizontal.TProgressbar"
        )
        self._progress.pack(fill=tk.X, padx=16, pady=(0, 4))

        # ── Stats panel ───────────────────────────────────────────────────────
        self._stats_lf = self._reg(tk.LabelFrame(
            self, text=self._("section_stats"), font=("Segoe UI", 10),
            bg=t["bg"], fg=t["label_frame"], bd=1, relief=tk.GROOVE
        ), "lf_stats")
        self._stats_lf.pack(fill=tk.X, padx=16, pady=(0, 4))

        # Row: three count badges
        counts_row = self._reg(tk.Frame(self._stats_lf, bg=t["bg"]), "bg")
        counts_row.pack(fill=tk.X, padx=6, pady=(4, 2))

        self._stat_skip_var    = tk.StringVar(value=f"{self._('stat_skip')}: 0")
        self._stat_success_var = tk.StringVar(value=f"{self._('stat_success')}: 0")
        self._stat_error_var   = tk.StringVar(value=f"{self._('stat_error')}: 0")

        self._reg(tk.Label(
            counts_row, textvariable=self._stat_skip_var,
            bg=t["bg"], fg=t["fg2"], font=("Segoe UI", 10),
        ), "stat_skip").pack(side=tk.LEFT, padx=(0, 16))

        self._reg(tk.Label(
            counts_row, textvariable=self._stat_success_var,
            bg=t["bg"], fg=t["log_info"], font=("Segoe UI", 10, "bold"),
        ), "stat_success").pack(side=tk.LEFT, padx=(0, 16))

        self._stat_error_lbl = self._reg(tk.Label(
            counts_row, textvariable=self._stat_error_var,
            bg=t["bg"], fg=t["fg2"], font=("Segoe UI", 10),
            cursor="hand2",
        ), "stat_error")
        self._stat_error_lbl.pack(side=tk.LEFT)
        self._stat_error_lbl.bind("<Button-1>", self._on_error_label_click)

        # Error list (hidden until first error appears)
        self._error_list_frame = tk.Frame(self._stats_lf, bg=t["bg"])
        # Do NOT pack yet — shown dynamically when errors arrive

        _err_lf = self._reg(tk.LabelFrame(
            self._error_list_frame,
            text=self._("stat_error_list"),
            font=("Segoe UI", 9),
            bg=t["bg"], fg=t["log_error"], bd=1, relief=tk.GROOVE,
        ), "lf_error_list")
        _err_lf.pack(fill=tk.X, padx=4, pady=(0, 4))

        self._error_listbox = tk.Listbox(
            _err_lf, height=4, selectmode=tk.SINGLE,
            bg=t["bg3"], fg=t["fg"], font=("Consolas", 9),
            relief=tk.FLAT, bd=0, activestyle="none",
            selectbackground=t["bg2"], selectforeground=t["log_error"],
        )
        _err_scroll = ttk.Scrollbar(_err_lf, command=self._error_listbox.yview)
        self._error_listbox.configure(yscrollcommand=_err_scroll.set)
        self._error_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0), pady=4)
        _err_scroll.pack(side=tk.RIGHT, fill=tk.Y, pady=4)
        self._error_listbox.bind("<<ListboxSelect>>", self._on_error_click)

        # ── Log output ────────────────────────────────────────────────────────
        self._log_lf = self._reg(tk.LabelFrame(
            self, text=self._("section_log"), font=("Segoe UI", 10),
            bg=t["bg"], fg=t["label_frame"], bd=1, relief=tk.GROOVE
        ), "lf_log")
        log_frame = self._log_lf
        log_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 16))

        self._log_text = self._reg(scrolledtext.ScrolledText(
            log_frame, bg=t["bg3"], fg=t["fg"],
            font=("Consolas", 9),
            state=tk.DISABLED, wrap=tk.WORD, relief=tk.FLAT,
        ), "log_text")
        self._log_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._log_text.tag_config("ERROR",   foreground=t["log_error"])
        self._log_text.tag_config("WARNING", foreground=t["log_warning"])
        self._log_text.tag_config("INFO",    foreground=t["log_info"])
        self._log_text.tag_config("DEBUG",   foreground=t["log_debug"])

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _browse_sa_json(self):
        path = filedialog.askopenfilename(
            title=self._("browse_dialog_title"),
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if path:
            self._sa_path_var.set(path)

    def _clear_log(self):
        self._log_text.configure(state=tk.NORMAL)
        self._log_text.delete("1.0", tk.END)
        self._log_text.configure(state=tk.DISABLED)

    def _append_log(self, message: str):
        self._log_text.configure(state=tk.NORMAL)
        # Derive tag from the level prefix produced by the log formatter
        # Format: "LEVELNAME | logger.name | message text"
        _first = message.split('|', 1)[0].strip().upper() if '|' in message else ''
        if _first in ('ERROR', 'CRITICAL', 'EXCEPTION'):
            tag = 'ERROR'
        elif _first == 'WARNING':
            tag = 'WARNING'
        elif _first == 'DEBUG':
            tag = 'DEBUG'
        else:
            tag = 'INFO'
        self._log_text.insert(tk.END, message + "\n", tag)
        self._log_text.see(tk.END)
        self._log_text.configure(state=tk.DISABLED)

    # ── Logging setup ─────────────────────────────────────────────────────────

    def _setup_logging(self):
        handler = _QueueHandler(self._log_queue)
        handler.setFormatter(logging.Formatter("%(levelname)s | %(name)s | %(message)s"))
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        # Remove default handlers so we don't double-print
        root_logger.handlers.clear()
        root_logger.addHandler(handler)

    def _poll_log_queue(self):
        """Periodically drain both log queues (GUI + subprocess) and write to text widget."""
        for q in (self._log_queue, self._proc_log_queue):
            try:
                while True:
                    msg = q.get_nowait()
                    self._append_log(msg)
            except Exception:
                pass
        # Drain stats queue separately
        try:
            while True:
                ev = self._stats_queue.get_nowait()
                if isinstance(ev, dict) and ev.get('type') == 'stat':
                    self._handle_stat_event(ev)
        except Exception:
            pass
        self.after(100, self._poll_log_queue)

    # ── Bot thread ────────────────────────────────────────────────────────────

    def _reset_stats(self):
        """Reset all order stats counters and clear the error list."""
        self._stat_skip = 0
        self._stat_success = 0
        self._stat_errors = []
        self._stat_skip_var.set(f"{self._('stat_skip')}: 0")
        self._stat_success_var.set(f"{self._('stat_success')}: 0")
        self._stat_error_var.set(f"{self._('stat_error')}: 0")
        self._error_listbox.delete(0, tk.END)
        self._error_list_frame.pack_forget()

    def _update_stat_labels(self):
        self._stat_skip_var.set(f"{self._('stat_skip')}: {self._stat_skip}")
        self._stat_success_var.set(f"{self._('stat_success')}: {self._stat_success}")
        err_count = len(self._stat_errors)
        self._stat_error_var.set(f"{self._('stat_error')}: {err_count}")
        t = self._theme
        if err_count > 0:
            self._stat_error_lbl.configure(fg=t["log_error"])
        else:
            self._stat_error_lbl.configure(fg=t["fg2"])

    def _handle_stat_event(self, ev: dict):
        etype = ev.get('event')
        if etype == 'skip':
            self._stat_skip += 1
        elif etype == 'success':
            self._stat_success += 1
        elif etype == 'error':
            self._stat_errors.append(ev)
            order_id = ev.get('order_id', '?')
            venture  = ev.get('venture', '')
            tag = f"  {order_id}" + (f"  ({venture})" if venture else "")
            self._error_listbox.insert(tk.END, tag)
            if len(self._stat_errors) == 1:
                # show the error list frame for the first time
                self._error_list_frame.pack(fill=tk.X, padx=4, pady=(0, 2))
        self._update_stat_labels()

    def _on_error_label_click(self, _event=None):
        """Clicking the error count label opens the last error detail (or selects first)."""
        if self._stat_errors:
            self._show_error_detail(self._stat_errors[-1])

    def _on_error_click(self, _event=None):
        """Double/single click on an error list item opens its detail popup."""
        sel = self._error_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < len(self._stat_errors):
            self._show_error_detail(self._stat_errors[idx])

    def _show_error_detail(self, ev: dict):
        """Open a Toplevel window showing error details, OCR text, and the debug image."""
        t = self._theme
        order_id = ev.get('order_id', '?')
        venture  = ev.get('venture', '')
        error    = ev.get('error', '')
        crop_path = ev.get('crop_path')
        ocr_lines = ev.get('ocr_lines') or []

        top = tk.Toplevel(self)
        top.title(f"{self._('stat_detail_title')} — {order_id}")
        top.configure(bg=t["bg"])
        top.resizable(True, True)
        top.minsize(520, 360)

        # ── Header info ──────────────────────────────────────────────────────
        info_frame = tk.Frame(top, bg=t["bg2"], pady=8)
        info_frame.pack(fill=tk.X)

        def _inf_lbl(label_key, value, bold=False):
            row = tk.Frame(info_frame, bg=t["bg2"])
            row.pack(fill=tk.X, padx=12, pady=1)
            tk.Label(row, text=self._(label_key), bg=t["bg2"], fg=t["fg2"],
                      font=("Segoe UI", 9)).pack(side=tk.LEFT)
            tk.Label(row, text=value, bg=t["bg2"], fg=t["fg"],
                      font=("Segoe UI", 9, "bold" if bold else "normal"),
                      wraplength=480, justify=tk.LEFT).pack(side=tk.LEFT, padx=(4, 0))

        _inf_lbl("stat_label_order",   order_id,  bold=True)
        if venture:
            _inf_lbl("stat_label_venture", venture)
        if error:
            _inf_lbl("stat_label_error",   error)

        # ── Body: image (left) + OCR text (right) ────────────────────────────
        body = tk.Frame(top, bg=t["bg"])
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        # Left: debug image
        img_frame = tk.Frame(body, bg=t["bg2"], width=320)
        img_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=(0, 6))
        img_frame.pack_propagate(False)

        _img_lbl = tk.Label(img_frame, bg=t["bg2"])
        _img_lbl.pack(expand=True)

        # Load image in background so dialog opens instantly
        def _load_image():
            if crop_path:
                try:
                    img = Image.open(crop_path)
                    # Fit inside 310×200 keeping aspect ratio
                    img.thumbnail((310, 200), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    def _set(p=photo):
                        _img_lbl.configure(image=p, text="")
                        _img_lbl._photo_ref = p
                    top.after(0, _set)
                    return
                except Exception:
                    pass
            def _no_img():
                _img_lbl.configure(text=self._("stat_no_image"),
                                   fg=t["fg2"], font=("Segoe UI", 9))
            top.after(0, _no_img)

        threading.Thread(target=_load_image, daemon=True).start()

        # Right: OCR lines
        ocr_frame = tk.Frame(body, bg=t["bg"])
        ocr_frame.grid(row=0, column=1, sticky=tk.NSEW)

        tk.Label(ocr_frame, text=self._("stat_label_ocr"),
                 bg=t["bg"], fg=t["fg2"], font=("Segoe UI", 9)).pack(anchor=tk.W)

        ocr_box = scrolledtext.ScrolledText(
            ocr_frame, bg=t["bg3"], fg=t["fg"],
            font=("Consolas", 9), relief=tk.FLAT, wrap=tk.WORD,
        )
        ocr_box.pack(fill=tk.BOTH, expand=True)
        ocr_content = "\n".join(ocr_lines) if ocr_lines else "—"
        ocr_box.insert(tk.END, ocr_content)
        ocr_box.configure(state=tk.DISABLED)

    def _on_toggle(self):
        if self._bot_process and self._bot_process.is_alive():
            self._on_stop()
        else:
            self._on_run()

    def _on_run(self):
        sheet_id = self._sheet_id_var.get().strip()
        sheet_name = self._sheet_name_var.get().strip()
        sa_path = self._sa_path_var.get().strip()

        if not sheet_id or not sheet_name:
            messagebox.showwarning(self._("warn_missing_title"), self._("warn_missing_body"))
            return

        # Persist settings to .env so submodules can read via os.getenv
        os.environ["GSHEET_ID"] = sheet_id
        os.environ["GSHEET_SHEET_NAME"] = sheet_name
        if sa_path:
            os.environ["GOOGLE_SERVICE_ACCOUNT_PATH"] = sa_path
        # Save to .env file for next run
        try:
            if _ENV_FILE.exists():
                set_key(str(_ENV_FILE), "GSHEET_ID", sheet_id)
                set_key(str(_ENV_FILE), "GSHEET_SHEET_NAME", sheet_name)
                if sa_path:
                    set_key(str(_ENV_FILE), "GOOGLE_SERVICE_ACCOUNT_PATH", sa_path)
        except Exception:
            pass

        t = self._theme
        self._run_btn.configure(text=self._("btn_stop"), bg=t["danger"], fg=t["danger_fg"])
        self._set_status("status_running")
        self._progress.start(12)
        self._reset_stats()

        # Drain stale messages from previous run
        try:
            while True:
                self._proc_log_queue.get_nowait()
        except Exception:
            pass
        try:
            while True:
                self._stats_queue.get_nowait()
        except Exception:
            pass

        self._bot_process = mp.Process(
            target=_bot_process_target,
            args=(sheet_id, sheet_name, self._proc_log_queue, str(_PROJECT_ROOT), self._stats_queue),
            daemon=True,
        )
        self._bot_process.start()
        logging.getLogger(__name__).info(self._("log_pid"), self._bot_process.pid)
        self.after(300, self._check_thread)

    def _on_stop(self):
        logger = logging.getLogger(__name__)
        if self._bot_process and self._bot_process.is_alive():
            logger.warning(self._("log_killing"), self._bot_process.pid)
            self._bot_process.terminate()
            self._bot_process.join(timeout=3)
            if self._bot_process.is_alive():
                self._bot_process.kill()
                self._bot_process.join(timeout=2)
            logger.warning(self._("log_killed"))
        self._progress.stop()
        t = self._theme
        self._run_btn.configure(text=self._("btn_run"), bg=t["accent"], fg=t["accent_fg"])
        self._set_status("status_stopped")

    def _check_thread(self):
        if self._bot_process and self._bot_process.is_alive():
            self.after(300, self._check_thread)
        else:
            self._progress.stop()
            t = self._theme
            self._run_btn.configure(text=self._("btn_run"), bg=t["accent"], fg=t["accent_fg"])
            exitcode = self._bot_process.exitcode if self._bot_process else None
            # exitcode < 0 means terminated by signal (user stopped it)
            if exitcode is not None and exitcode < 0:
                self._set_status("status_stopped")
            else:
                self._set_status("status_done")


if __name__ == "__main__":
    mp.freeze_support()  # Required for PyInstaller + multiprocessing on Windows
    app = BotApp()
    app.mainloop()
