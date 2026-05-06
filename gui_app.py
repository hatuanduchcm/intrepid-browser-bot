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
    import glob as _glob

    def _apply(cmd: str, tessdata: str = None):
        pytesseract.pytesseract.tesseract_cmd = cmd
        os.environ['TESSERACT_CMD'] = cmd
        if tessdata:
            os.environ['TESSDATA_PREFIX'] = tessdata

    # 1. Bundled inside exe (PyInstaller _MEIPASS)
    bundled = _BASE_DIR / 'Tesseract-OCR' / 'tesseract.exe'
    if bundled.exists():
        _apply(str(bundled), str(_BASE_DIR / 'Tesseract-OCR'))
        return
    # 2. Env override
    env_cmd = os.getenv('TESSERACT_CMD')
    if env_cmd and Path(env_cmd).exists():
        pytesseract.pytesseract.tesseract_cmd = env_cmd
        return
    # 3. Default system path
    default = Path(r'C:\Program Files\Tesseract-OCR\tesseract.exe')
    if default.exists():
        _apply(str(default))
        return
    # 4. Search bundled _internal directories (dev environment fallback)
    search_roots = [
        Path.home() / 'Downloads',
        Path.home() / 'Desktop',
    ]
    for root in search_roots:
        if not root.exists():
            continue
        pattern = str(root / '*' / '_internal' / 'Tesseract-OCR' / 'tesseract.exe')
        hits = sorted(_glob.glob(pattern), key=os.path.getmtime, reverse=True)
        if hits:
            found = hits[0]
            _apply(found, str(Path(found).parent))
            return

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
    _AI_FIELDS = [
        ('GOOGLE_GEMINI_API_KEY',   'settings_label_gemini_key',   True,  False, False),
        ('GOOGLE_GEMINI_MODEL',     'settings_label_gemini_model', False, False, False),
    ]
    _VENTURE_CODES = ["VN", "MY", "ID", "SG", "PH", "TH"]

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

        # ── Section: AI (Google Gemini) ───────────────────────────────────────
        ai = _section('settings_section_ai')
        for i, (ek, lk, pw, fp, jj) in enumerate(self._AI_FIELDS):
            _add_field(ai, i, ek, lk, pw, fp, jj)

        # ── Section: Intrepid Accounts per Venture ────────────────────────────
        va = _section('settings_section_intrepid_accounts')
        va.columnconfigure(1, weight=1)
        va.columnconfigure(2, weight=1)

        # Common password (fallback when per-venture pass is empty)
        tk.Label(va, text=L.get('settings_label_common_pass', 'Common Password:'),
                 bg=t['bg'], fg=t['fg'], font=('Segoe UI', 9), anchor=tk.W, width=22,
                 ).grid(row=0, column=0, sticky=tk.W, padx=(8, 4), pady=(8, 4))
        _cp_cell = tk.Frame(va, bg=t['bg'])
        _cp_cell.grid(row=0, column=1, columnspan=2, sticky=tk.EW, padx=(0, 8), pady=(8, 4))
        _cp_cell.columnconfigure(0, weight=1)
        _cp_var = tk.StringVar(value=os.getenv('INTREPID_PASS', ''))
        self._vars['INTREPID_PASS'] = _cp_var
        _cp_entry = tk.Entry(_cp_cell, textvariable=_cp_var, show='•',
                             bg=t['entry_bg'], fg=t['fg'], insertbackground=t['fg'],
                             relief=tk.FLAT, font=('Consolas', 9))
        _cp_entry.grid(row=0, column=0, sticky=tk.EW)
        self._show_pass['INTREPID_PASS'] = False
        def _toggle_cp(e=_cp_entry):
            self._show_pass['INTREPID_PASS'] = not self._show_pass['INTREPID_PASS']
            e.configure(show='' if self._show_pass['INTREPID_PASS'] else '•')
            self._eye_btns['INTREPID_PASS'].configure(
                text='🙈' if self._show_pass['INTREPID_PASS'] else '👁')
        _cp_eye = tk.Button(_cp_cell, text='👁', command=_toggle_cp,
                            bg=t['bg2'], fg=t['fg'], relief=tk.FLAT,
                            font=('Segoe UI', 10), padx=6, cursor='hand2')
        _cp_eye.grid(row=0, column=1, padx=(4, 0))
        self._eye_btns['INTREPID_PASS'] = _cp_eye

        # Column headers
        _hdr = {'bg': t['bg'], 'fg': t['fg2'], 'font': ('Segoe UI', 9, 'bold')}
        tk.Label(va, text=L.get('settings_col_venture', 'Venture'), **_hdr, width=10,
                 ).grid(row=1, column=0, sticky=tk.W, padx=(8, 4), pady=(6, 2))
        tk.Label(va, text=L.get('settings_col_user', 'Email / User'), **_hdr,
                 ).grid(row=1, column=1, sticky=tk.W, pady=(6, 2))
        tk.Label(va, text=L.get('settings_col_pass', 'Password'), **_hdr,
                 ).grid(row=1, column=2, sticky=tk.W, padx=(8, 0), pady=(6, 2))

        # Per-venture rows
        _tmpl = os.getenv('INTREPID_USER_TEMPLATE', 'ssc.{venture}@intrepid.asia')
        for vi, code in enumerate(self._VENTURE_CODES):
            row = vi + 2
            uk = f'INTREPID_USER_{code}'
            pk = f'INTREPID_PASS_{code}'
            _default_user = os.getenv(uk) or _tmpl.format(venture=code)
            _default_pass = os.getenv(pk, '')

            tk.Label(va, text=code, bg=t['bg'], fg=t['accent'],
                     font=('Segoe UI', 10, 'bold'), width=10,
                     ).grid(row=row, column=0, sticky=tk.W, padx=(8, 4), pady=3)

            u_var = tk.StringVar(value=_default_user)
            self._vars[uk] = u_var
            tk.Entry(va, textvariable=u_var,
                     bg=t['entry_bg'], fg=t['fg'], insertbackground=t['fg'],
                     relief=tk.FLAT, font=('Consolas', 9),
                     ).grid(row=row, column=1, sticky=tk.EW, padx=(0, 4), pady=3)

            p_var = tk.StringVar(value=_default_pass)
            self._vars[pk] = p_var
            _p_cell = tk.Frame(va, bg=t['bg'])
            _p_cell.grid(row=row, column=2, sticky=tk.EW, padx=(4, 8), pady=3)
            _p_cell.columnconfigure(0, weight=1)
            _p_entry = tk.Entry(_p_cell, textvariable=p_var, show='•',
                                bg=t['entry_bg'], fg=t['fg'], insertbackground=t['fg'],
                                relief=tk.FLAT, font=('Consolas', 9))
            _p_entry.grid(row=0, column=0, sticky=tk.EW)
            self._show_pass[pk] = False
            def _mk_toggle(ek=pk, e=_p_entry):
                def _toggle():
                    self._show_pass[ek] = not self._show_pass[ek]
                    e.configure(show='' if self._show_pass[ek] else '•')
                    self._eye_btns[ek].configure(text='🙈' if self._show_pass[ek] else '👁')
                return _toggle
            _p_eye = tk.Button(_p_cell, text='👁', command=_mk_toggle(),
                               bg=t['bg2'], fg=t['fg'], relief=tk.FLAT,
                               font=('Segoe UI', 10), padx=6, cursor='hand2')
            _p_eye.grid(row=0, column=1, padx=(4, 0))
            self._eye_btns[pk] = _p_eye

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
        all_fields = self._GSHEET_FIELDS + self._AI_FIELDS
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

        # Per-venture + common password
        extra_keys = ['INTREPID_PASS']
        for code in self._VENTURE_CODES:
            extra_keys += [f'INTREPID_USER_{code}', f'INTREPID_PASS_{code}']
        for ek in extra_keys:
            if ek not in self._vars:
                continue
            val = self._vars[ek].get().strip()
            os.environ[ek] = val
            try:
                if _ENV_FILE.exists():
                    set_key(str(_ENV_FILE), ek, val)
            except Exception:
                pass

        # sync sheet fields back to main window
        try:
            self._parent._sheet_id_var.set(os.getenv('GSHEET_ID', ''))
            self._parent._sheet_name_var.set(os.getenv('GSHEET_SHEET_NAME', ''))
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

        # Venture checkboxes
        self._venture_codes = ["VN", "MY", "ID", "SG", "PH", "TH"]
        _saved_ventures_str = os.getenv("SELECTED_VENTURES", ",".join(self._venture_codes))
        _saved_ventures = set(s.strip() for s in _saved_ventures_str.split(",") if s.strip()) or set(self._venture_codes)
        self._venture_vars = {code: tk.BooleanVar(value=(code in _saved_ventures)) for code in self._venture_codes}
        for _code in self._venture_codes:
            self._venture_vars[_code].trace_add("write", lambda *_: self._save_ventures())

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
        self._is_paused: bool = False
        # Update tracking
        self._update_available_tag: str = ''
        self._update_available_zip: str = ''
        self._update_available_patch: str = ''
        self._update_is_patch: bool = False
        self._bell_blink_on: bool = False
        self._build_ui()
        self._setup_logging()
        self._poll_log_queue()
        # Startup update check (after small delay so UI renders first)
        self.after(2000, lambda: threading.Thread(target=self._check_update_bg, daemon=True).start())
        # Periodic check every 3 hours
        self._schedule_periodic_check()

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
                    _running = bool(self._bot_process and self._bot_process.is_alive())
                    if _running and not self._is_paused:
                        w.configure(bg=t["log_warning"], fg="#1e1e2e")  # orange = pause
                    else:
                        w.configure(bg=t["accent"], fg=t["accent_fg"])  # green = play/resume
                elif role == "btn_stop_ctrl":
                    _active = bool(self._bot_process and self._bot_process.is_alive()) or self._is_paused
                    if _active:
                        w.configure(bg=t["danger"], fg=t["danger_fg"], state=tk.NORMAL)
                    else:
                        w.configure(bg=t["btn_neutral"], fg=t["btn_neu_fg"], state=tk.DISABLED)
                elif role == "btn_neutral":
                    w.configure(bg=t["btn_neutral"], fg=t["btn_neu_fg"])
                elif role == "venture_cb":
                    w.configure(
                        bg=t["bg"], fg=t["fg"],
                        selectcolor=t["bg2"],
                        activebackground=t["bg"],
                        activeforeground=t["accent"],
                    )
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
        "status_paused":  "#fab387",  # orange
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
            _is_running = bool(self._bot_process and self._bot_process.is_alive())
            if not _is_running and not self._is_paused:
                self._play_pause_btn.configure(text=L.get("btn_run", ""))
            elif self._is_paused:
                self._play_pause_btn.configure(text=L.get("btn_resume", ""))
            else:
                self._play_pause_btn.configure(text=L.get("btn_pause", ""))
            self._stop_btn.configure(text=L.get("btn_stop", ""))
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

    def _save_ventures(self):
        """Persist selected ventures to .env so state survives restarts."""
        selected = ",".join(v for v in self._venture_codes if self._venture_vars[v].get())
        os.environ["SELECTED_VENTURES"] = selected
        try:
            if _ENV_FILE.exists():
                set_key(str(_ENV_FILE), "SELECTED_VENTURES", selected)
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

    _PERIODIC_UPDATE_MS = 3 * 3600 * 1000  # 3 hours

    def _fetch_latest_release(self):
        """Fetch latest GitHub release. Returns (tag, full_url, patch_url) or (None, None, None)."""
        try:
            req = urllib.request.Request(
                GITHUB_API_LATEST,
                headers={"Accept": "application/vnd.github+json", "User-Agent": "InvoiceAdjBot"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            latest_tag = data.get("tag_name", "").lstrip("v")
            if not latest_tag:
                return None, None, None
            def _ver(v):
                try:
                    return tuple(int(x) for x in v.split('.') if x.isdigit())
                except Exception:
                    return (0,)
            if _ver(latest_tag) <= _ver(APP_VERSION):
                return None, None, None
            assets = data.get("assets", [])
            full_url = next(
                (a["browser_download_url"] for a in assets if a["name"] == "InvoiceAdjustmentBot.zip"),
                None,
            )
            patch_url = next(
                (a["browser_download_url"] for a in assets if a["name"] == "InvoiceAdjustmentBot-patch.zip"),
                None,
            )
            return latest_tag, full_url, patch_url
        except Exception:
            return None, None, None

    def _check_update_bg(self):
        """Startup background check: if newer version exists, show dialog."""
        tag, full_url, patch_url = self._fetch_latest_release()
        if tag:
            self.after(0, lambda: self._show_update_dialog(tag, full_url or '', patch_url))

    def _schedule_periodic_check(self):
        """Schedule the next periodic version check (3 h)."""
        self.after(self._PERIODIC_UPDATE_MS,
                   lambda: threading.Thread(target=self._periodic_check_bg, daemon=True).start())

    def _periodic_check_bg(self):
        """Periodic background check: show bell if new version found."""
        tag, full_url, patch_url = self._fetch_latest_release()
        if tag and tag != self._update_available_tag:
            self.after(0, lambda: self._notify_update_bell(tag, full_url or '', patch_url))
        self.after(0, self._schedule_periodic_check)

    # ── Update UI helpers ──────────────────────────────────────────────────────

    def _show_update_dialog(self, tag: str, zip_url: str, patch_url=None):
        """Modal dialog: new version found. Update now or later."""
        L = self._locale
        t = self._theme
        dlg = tk.Toplevel(self)
        dlg.title(L.get('update_title', 'Cap nhat'))
        dlg.configure(bg=t['bg'])
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.update_idletasks()
        px = self.winfo_x() + (self.winfo_width()  - 440) // 2
        py = self.winfo_y() + (self.winfo_height() - 190) // 2
        dlg.geometry(f'440x190+{px}+{py}')

        tk.Label(dlg,
                 text=f"v{tag}  -  {L.get('update_available', 'Co phien ban moi')}",
                 bg=t['bg'], fg=t['accent'],
                 font=('Segoe UI', 13, 'bold')).pack(pady=(22, 6))
        tk.Label(dlg,
                 text=L.get('update_body', 'Ban co muon tai va cap nhat ngay khong?'),
                 bg=t['bg'], fg=t['fg'],
                 font=('Segoe UI', 10)).pack(pady=(0, 18))

        btn_row = tk.Frame(dlg, bg=t['bg'])
        btn_row.pack()

        def _do_now():
            dlg.destroy()
            if zip_url:
                self._start_download(zip_url, tag, patch_url=patch_url)
            else:
                self._update_banner.configure(
                    text=L.get('update_no_asset', 'Khong tim thay file tai'),
                    bg=t['btn_neutral'], fg=t['log_error'])
                self._update_banner.pack(side=tk.LEFT, padx=(8, 0))

        def _do_later():
            dlg.destroy()
            self._notify_update_bell(tag, zip_url, patch_url)

        tk.Button(btn_row,
                  text=L.get('update_btn_now', 'Cap nhat ngay'),
                  command=_do_now,
                  bg=t['accent'], fg=t['accent_fg'],
                  font=('Segoe UI', 10, 'bold'),
                  relief=tk.FLAT, padx=18, pady=8, cursor='hand2',
                  ).pack(side=tk.LEFT, padx=(0, 10))
        tk.Button(btn_row,
                  text=L.get('update_btn_later', 'De sau'),
                  command=_do_later,
                  bg=t['btn_neutral'], fg=t['btn_neu_fg'],
                  font=('Segoe UI', 10),
                  relief=tk.FLAT, padx=18, pady=8, cursor='hand2',
                  ).pack(side=tk.LEFT)

    def _notify_update_bell(self, tag: str, zip_url: str, patch_url=None):
        """Store update info and show animated bell in header."""
        self._update_available_tag = tag
        self._update_available_zip = zip_url
        self._update_available_patch = patch_url or ''
        try:
            self._update_bell.pack(side=tk.RIGHT, padx=(0, 2))
            self._bell_blink_on = True
            self._blink_bell()
        except Exception:
            pass

    def _blink_bell(self):
        if not self._bell_blink_on:
            return
        try:
            cur = self._update_bell.cget('text')
            self._update_bell.configure(text='\U0001f514' if cur == '\U0001f515' else '\U0001f515')
        except Exception:
            return
        self.after(900, self._blink_bell)

    def _on_bell_click(self):
        """Bell clicked — stop blink and show update dialog."""
        self._bell_blink_on = False
        try:
            self._update_bell.configure(text='\U0001f514')
        except Exception:
            pass
        tag = self._update_available_tag
        zip_url = self._update_available_zip
        if tag:
            self._show_update_dialog(tag, zip_url, self._update_available_patch or None)

    def _start_download(self, zip_url: str, tag: str, patch_url=None):
        """Show progress banner and download in background thread.
        If running as frozen exe and patch_url is available, downloads patch only (~5 MB)."""
        self._bell_blink_on = False
        try:
            self._update_bell.pack_forget()
        except Exception:
            pass
        is_patch = bool(patch_url) and getattr(sys, 'frozen', False)
        url = patch_url if is_patch else zip_url
        lbl = self._locale.get('update_downloading', 'Dang tai')
        self._update_banner.configure(
            text=f"{lbl} v{tag}... 0%",
            bg=self._theme['btn_neutral'], fg=self._theme['fg'],
        )
        self._update_banner.pack(side=tk.LEFT, padx=(8, 0))
        threading.Thread(target=self._download_thread, args=(url, tag, is_patch), daemon=True).start()

    def _download_thread(self, zip_url: str, tag: str, is_patch: bool = False):
        try:
            tmp = tempfile.NamedTemporaryFile(suffix='.zip', delete=False)
            tmp.close()
            urllib.request.urlretrieve(zip_url, tmp.name, reporthook=self._download_progress)
            self._update_zip_path = tmp.name
            self._update_is_patch = is_patch
            self.after(0, lambda: self._show_update_ready(tag))
        except Exception as e:
            self.after(0, lambda err=e: self._update_banner.configure(
                text=f"{self._locale.get('update_failed', 'Tai that bai')}: {err}",
                bg=self._theme['btn_neutral'], fg=self._theme['log_error'],
            ))

    def _download_progress(self, block_num, block_size, total_size):
        if total_size <= 0:
            return
        pct = min(int(block_num * block_size * 100 / total_size), 99)
        lbl = self._locale.get('update_downloading', 'Dang tai')
        self.after(0, lambda p=pct: self._update_banner.configure(text=f"{lbl}... {p}%"))

    def _show_update_ready(self, tag: str):
        """Download complete — prompt user to restart."""
        lbl = self._locale.get('update_ready', 'v{tag} san sang - Nhap de khoi dong lai').format(tag=tag)
        self._update_banner.configure(text=lbl, bg='#a6e3a1', fg='#1e1e2e')
        self._update_banner.pack(side=tk.LEFT, padx=(8, 0))

    def _apply_update(self):
        if not self._update_zip_path or not Path(self._update_zip_path).exists():
            return
        zip_path = self._update_zip_path
        exe_path = str(Path(sys.executable))
        # Patch: extract vào _internal/ (runtime giữ nguyên, chỉ .pyc + assets thay)
        # Full:  extract vào app_dir (thay toàn bộ kể cả _internal/)
        if self._update_is_patch and getattr(sys, 'frozen', False):
            dest_dir = str(Path(sys.executable).parent / '_internal')
        else:
            dest_dir = str(_PROJECT_ROOT)
        bat_lines = [
            '@echo off',
            'timeout /t 2 /nobreak >nul',
            f'powershell -Command "Expand-Archive -Path \'\'{zip_path}\'\' -DestinationPath \'\'{dest_dir}\'\' -Force"',
            f'del /f /q "{zip_path}"',
            f'start "" "{exe_path}"',
            'del /f /q "%~f0"',
        ]
        bat_path = Path(tempfile.gettempdir()) / 'iab_updater.bat'
        bat_path.write_text('\n'.join(bat_lines), encoding='utf-8')
        subprocess.Popen(['cmd', '/c', str(bat_path)], creationflags=subprocess.CREATE_NO_WINDOW)
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

        # Update banner (hidden by default, shown during download / ready)
        self._update_banner = tk.Button(
            header,
            text="",
            command=self._apply_update,
            bg="#a6e3a1", fg="#1e1e2e",
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT, padx=10, pady=4, cursor="hand2", bd=0,
        )
        # Bell button (hidden by default, shown when update available & user chose 'later')
        self._update_bell = tk.Button(
            header, text="\U0001f514",
            command=self._on_bell_click,
            bg=t["bg2"], fg="#fab387",
            font=("Segoe UI", 13),
            relief=tk.FLAT, padx=4, pady=2, cursor="hand2", bd=0,
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

        self._sa_path_var = tk.StringVar(value=os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH", ""))

        settings.columnconfigure(1, weight=1)


        # ── Venture checkboxes ───────────────────────────────────────────────
        venture_frame = self._reg(tk.Frame(self, bg=t["bg"]), "bg")
        venture_frame.pack(fill=tk.X, padx=16, pady=(8, 0))
        self._reg(tk.Label(venture_frame, text="Venture:", bg=t["bg"], fg=t["fg"], font=("Segoe UI", 10, "bold")), "label").pack(side=tk.LEFT, padx=(0, 8))
        for code in self._venture_codes:
            cb = self._reg(tk.Checkbutton(
                venture_frame, text=code, variable=self._venture_vars[code],
                bg=t["bg"], fg=t["fg"],
                selectcolor=t["bg2"],
                activebackground=t["bg"], activeforeground=t["accent"],
                font=("Segoe UI", 11, "bold"), padx=6, pady=4,
                cursor="hand2",
            ), "venture_cb")
            cb.pack(side=tk.LEFT, padx=4)

        # ── Control buttons ───────────────────────────────────────────────────
        btn_frame = self._reg(tk.Frame(self, bg=t["bg"]), "bg")
        btn_frame.pack(fill=tk.X, padx=16, pady=8)

        self._play_pause_btn = self._reg(tk.Button(
            btn_frame, text=self._("btn_run"), command=self._on_play_pause,
            bg=t["accent"], fg=t["accent_fg"],
            font=("Segoe UI", 11, "bold"),
            relief=tk.FLAT, padx=16, pady=8, cursor="hand2",
            width=10,
        ), "btn_run")
        self._play_pause_btn.pack(side=tk.LEFT, padx=(0, 6))

        self._stop_btn = self._reg(tk.Button(
            btn_frame, text=self._("btn_stop"), command=self._on_stop,
            bg=t["btn_neutral"], fg=t["btn_neu_fg"],
            font=("Segoe UI", 11, "bold"),
            relief=tk.FLAT, padx=14, pady=8, cursor="hand2",
            width=7, state=tk.DISABLED,
        ), "btn_stop_ctrl")
        self._stop_btn.pack(side=tk.LEFT, padx=(0, 8))

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

        # ── Stats panel + Error list + Log output (with resizable splitter) ──
        self._stats_lf = self._reg(tk.LabelFrame(
            self, text=self._("section_stats"), font=("Segoe UI", 10),
            bg=t["bg"], fg=t["label_frame"], bd=1, relief=tk.GROOVE
        ), "lf_stats")
        self._stats_lf.pack(fill=tk.X, padx=16, pady=(0, 4))

        # Row: three count badges
        counts_row = self._reg(tk.Frame(self._stats_lf, bg=t["bg"]), "bg")
        counts_row.pack(fill=tk.X, padx=6, pady=(4, 2))

        # PanedWindow for error list and log (vertical split, user can drag)
        self._main_pane = tk.PanedWindow(self, orient=tk.VERTICAL, sashrelief=tk.RAISED, sashwidth=6, showhandle=True, bg=t["bg"])
        self._main_pane.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 8))

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
        self._error_list_frame = tk.Frame(self._main_pane, bg=t["bg"])
        # Do NOT pack yet — shown dynamically when errors arrive

        _err_lf = self._reg(tk.LabelFrame(
            self._error_list_frame,
            text=self._("stat_error_list"),
            font=("Segoe UI", 9),
            bg=t["bg"], fg=t["log_error"], bd=1, relief=tk.GROOVE,
        ), "lf_error_list")
        _err_lf.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))

        self._error_listbox = tk.Listbox(
            _err_lf, height=8, selectmode=tk.SINGLE,
            bg=t["bg3"], fg=t["fg"], font=("Consolas", 9),
            relief=tk.FLAT, bd=0, activestyle="none",
            selectbackground=t["bg2"], selectforeground=t["log_error"],
        )
        _err_scroll = ttk.Scrollbar(_err_lf, command=self._error_listbox.yview)
        self._error_listbox.configure(yscrollcommand=_err_scroll.set)
        self._error_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0), pady=4)
        _err_scroll.pack(side=tk.RIGHT, fill=tk.Y, pady=4)
        self._error_listbox.bind("<<ListboxSelect>>", self._on_error_click)

        # Log output (in a frame for paned window)
        self._log_lf = self._reg(tk.LabelFrame(
            self._main_pane, text=self._("section_log"), font=("Segoe UI", 10),
            bg=t["bg"], fg=t["label_frame"], bd=1, relief=tk.GROOVE
        ), "lf_log")
        log_frame = self._log_lf
        log_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

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

        # Add error list and log to paned window (default sizes)
        self._main_pane.add(self._error_list_frame, minsize=80, height=120)
        self._main_pane.add(self._log_lf, minsize=80, height=220)

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

        # Also remove all files inside assets/debug_matches/
        try:
            import shutil
            from pathlib import Path
            debug_dir = Path(__file__).resolve().parent / 'assets' / 'debug_matches'
            if debug_dir.is_dir():
                for f in debug_dir.iterdir():
                    try:
                        if f.is_file():
                            f.unlink()
                    except Exception:
                        pass
        except Exception:
            pass

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
        # Always keep error list frame in PanedWindow; do not hide

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
            brand    = ev.get('brand', '')
            error    = ev.get('error', '')
            # Shorten error to first 40 chars for display
            err_short = error[:40].rstrip() + ('…' if len(error) > 40 else '') if error else ''
            parts = []
            if venture:
                parts.append(venture)
            if brand:
                parts.append(brand)
            prefix = f"[{' | '.join(parts)}] " if parts else ""
            tag = f"  {prefix}{order_id}" + (f"  — {err_short}" if err_short else "")
            self._error_listbox.insert(tk.END, tag)
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
        """Open a Toplevel window showing error details, OCR text, parsed mapping, and the debug image."""
        t = self._theme
        order_id = ev.get('order_id', '?')
        venture  = ev.get('venture', '')
        error    = ev.get('error', '')
        crop_path = ev.get('crop_path')
        ocr_lines = ev.get('ocr_lines') or []
        parsed_mapping = ev.get('parsed_mapping')

        top = tk.Toplevel(self)
        top.title(f"{self._('stat_detail_title')} — {order_id}")
        top.configure(bg=t["bg"])
        top.resizable(True, True)
        top.minsize(800, 400)

        # Header info
        info_frame = tk.Frame(top, bg=t["bg2"], pady=8)
        info_frame.pack(fill=tk.X)
        def _inf_lbl(label_key, value, bold=False, copyable=False):
            row = tk.Frame(info_frame, bg=t["bg2"])
            row.pack(fill=tk.X, padx=12, pady=1)
            tk.Label(row, text=self._(label_key), bg=t["bg2"], fg=t["fg2"], font=("Segoe UI", 9)).pack(side=tk.LEFT)
            if copyable:
                _var = tk.StringVar(value=value)
                # Tăng width cho order id
                width = max(18, len(value) + 2) if label_key == "stat_label_order" else len(value) + 2
                _ent = tk.Entry(row, textvariable=_var, bg=t["bg2"], fg=t["fg"], font=("Segoe UI", 9, "bold" if bold else "normal"), relief=tk.FLAT, bd=0, state="readonly", readonlybackground=t["bg2"], width=width)
                _ent.pack(side=tk.LEFT, padx=(4, 0))
            else:
                tk.Label(row, text=value, bg=t["bg2"], fg=t["fg"], font=("Segoe UI", 9, "bold" if bold else "normal"), wraplength=480, justify=tk.LEFT).pack(side=tk.LEFT, padx=(4, 0))
        _inf_lbl("stat_label_order",   order_id,  bold=True, copyable=True)
        if venture:
            _inf_lbl("stat_label_venture", venture, copyable=True)
        if error:
            _inf_lbl("stat_label_error",   error)

        # Main 3-column layout (always grid, image centered, no vertical stacking)
        main_frame = tk.Frame(top, bg=t["bg"])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        for i in range(3):
            main_frame.columnconfigure(i, weight=1, uniform="col")
        main_frame.rowconfigure(0, weight=1)

        # (1) Parsed mapping (left, show real column name, copyable, more spacing)
        from gsheets.order_adjustment_sheet import GSHEET_COLUMN
        mapping_frame = tk.Frame(main_frame, bg=t["bg"])
        mapping_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=0)
        tk.Label(mapping_frame, text=self._("stat_label_parsed_mapping") or "Parsed Mapping", bg=t["bg"], fg=t["fg2"], font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, pady=(0, 4))
        if parsed_mapping:
            for k, v in parsed_mapping.items():
                row = tk.Frame(mapping_frame, bg=t["bg"])
                row.pack(fill=tk.X, padx=0, pady=4)  # tăng giãn dòng
                # Lấy tên thật từ GSHEET_COLUMN, fallback sang str(k)
                col_name = GSHEET_COLUMN.get(k, str(k))
                # Copyable entry cho tên cột và value
                col_var = tk.StringVar(value=col_name)
                val_var = tk.StringVar(value=str(v))
                col_ent = tk.Entry(row, textvariable=col_var, bg=t["bg"], fg=t["fg2"], font=("Segoe UI", 9, "bold"), relief=tk.FLAT, bd=0, state="readonly", readonlybackground=t["bg"], width=max(18, len(col_name)+2))
                col_ent.pack(side=tk.LEFT, padx=(0, 4))
                val_ent = tk.Entry(row, textvariable=val_var, bg=t["bg"], fg=t["fg"], font=("Consolas", 9), relief=tk.FLAT, bd=0, state="readonly", readonlybackground=t["bg"], width=max(10, len(str(v))+2))
                val_ent.pack(side=tk.LEFT, padx=(0, 0))

        # (2) Image (center, always centered, margin top)
        img_frame = tk.Frame(main_frame, bg=t["bg"])
        img_frame.grid(row=0, column=1, sticky="nsew", padx=0, pady=(24,0))
        img_frame.grid_propagate(True)
        img_frame.rowconfigure(0, weight=1)
        img_frame.columnconfigure(0, weight=1)
        _img_lbl = tk.Label(img_frame, bg=t["bg"], cursor="hand2", bd=0, highlightthickness=0, anchor="center")
        _img_lbl.grid(row=0, column=0, sticky="nsew")
        def _open_full_image():
            if not crop_path:
                return
            try:
                full_win = tk.Toplevel(top)
                full_win.title("Screenshot")
                full_win.configure(bg=t["bg3"])
                full_win.resizable(True, True)
                pil_full = Image.open(crop_path)
                sw = full_win.winfo_screenwidth()
                sh = full_win.winfo_screenheight()
                max_w = int(sw * 0.9)
                max_h = int(sh * 0.9)
                pil_full.thumbnail((max_w, max_h), Image.LANCZOS)
                full_photo = ImageTk.PhotoImage(pil_full)
                full_win.geometry(f"{pil_full.width}x{pil_full.height}")
                lbl = tk.Label(full_win, image=full_photo, bg=t["bg3"])
                lbl._photo_ref = full_photo
                lbl.pack(fill=tk.BOTH, expand=True)
                lbl.bind("<Button-1>", lambda _: full_win.destroy())
            except Exception as err:
                messagebox.showerror("Lỗi", str(err), parent=top)
        _img_lbl.bind("<Button-1>", lambda _: _open_full_image())
        def _load_image():
            if crop_path:
                try:
                    img = Image.open(crop_path)
                    img.thumbnail((340, 340), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    def _set(p=photo):
                        _img_lbl.configure(image=p, text="", bd=0, highlightthickness=0)
                        _img_lbl._photo_ref = p
                    top.after(0, _set)
                    return
                except Exception:
                    pass
            def _no_img():
                _img_lbl.configure(text=self._("stat_no_image"), fg=t["fg2"], font=("Segoe UI", 9), bd=0, highlightthickness=0)
            top.after(0, _no_img)
        threading.Thread(target=_load_image, daemon=True).start()

        # (3) OCR lines (right)
        ocr_frame = tk.Frame(main_frame, bg=t["bg"])
        ocr_frame.grid(row=0, column=2, sticky="nsew", padx=(8, 0), pady=0)
        tk.Label(ocr_frame, text=self._("stat_label_ocr"), bg=t["bg"], fg=t["fg2"], font=("Segoe UI", 9)).pack(anchor=tk.W, pady=(0, 4))
        ocr_box = scrolledtext.ScrolledText(ocr_frame, bg=t["bg3"], fg=t["fg"], font=("Consolas", 9), relief=tk.FLAT, wrap=tk.WORD)
        ocr_box.pack(fill=tk.BOTH, expand=True)
        ocr_content = "\n".join(ocr_lines) if ocr_lines else "—"
        ocr_box.insert(tk.END, ocr_content)
        ocr_box.bind("<Key>", lambda e: "break" if e.state & 0x4 == 0 else None)

    # ── Process suspend/resume (Windows) ─────────────────────────────────────

    @staticmethod
    def _suspend_process(pid: int):
        try:
            handle = ctypes.windll.kernel32.OpenProcess(0x1F0FFF, False, pid)
            ctypes.windll.ntdll.NtSuspendProcess(handle)
            ctypes.windll.kernel32.CloseHandle(handle)
        except Exception as e:
            logging.getLogger(__name__).debug('NtSuspendProcess failed: %s', e)

    @staticmethod
    def _resume_process(pid: int):
        try:
            handle = ctypes.windll.kernel32.OpenProcess(0x1F0FFF, False, pid)
            ctypes.windll.ntdll.NtResumeProcess(handle)
            ctypes.windll.kernel32.CloseHandle(handle)
        except Exception as e:
            logging.getLogger(__name__).debug('NtResumeProcess failed: %s', e)

    def _on_play_pause(self):
        running = bool(self._bot_process and self._bot_process.is_alive())
        if not running and not self._is_paused:
            self._on_run()
        elif running and not self._is_paused:
            self._on_pause()
        else:
            self._on_resume()

    def _on_pause(self):
        if not (self._bot_process and self._bot_process.is_alive()):
            return
        self._is_paused = True
        self._suspend_process(self._bot_process.pid)
        self._progress.stop()
        t = self._theme
        self._play_pause_btn.configure(text=self._("btn_resume"),
                                       bg=t["accent"], fg=t["accent_fg"])
        self._stop_btn.configure(bg=t["danger"], fg=t["danger_fg"], state=tk.NORMAL)
        self._set_status("status_paused")
        logging.getLogger(__name__).info("Bot đã tạm dừng (PID %s)", self._bot_process.pid)

    def _on_resume(self):
        if not (self._bot_process and self._bot_process.is_alive()):
            self._is_paused = False
            return
        self._is_paused = False
        self._resume_process(self._bot_process.pid)
        self._progress.start(12)
        t = self._theme
        self._play_pause_btn.configure(text=self._("btn_pause"),
                                       bg=t["log_warning"], fg="#1e1e2e")
        self._stop_btn.configure(bg=t["danger"], fg=t["danger_fg"], state=tk.NORMAL)
        self._set_status("status_running")
        logging.getLogger(__name__).info("Bot tiếp tục chạy (PID %s)", self._bot_process.pid)

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

        self._is_paused = False
        t = self._theme
        self._play_pause_btn.configure(text=self._("btn_pause"),
                                       bg=t["log_warning"], fg="#1e1e2e")
        self._stop_btn.configure(bg=t["danger"], fg=t["danger_fg"], state=tk.NORMAL)
        self._set_status("status_running")
        self._progress.start(12)
        self._reset_stats()

        # Lấy danh sách venture được chọn
        selected_ventures = [v for v, var in self._venture_vars.items() if var.get()]
        os.environ["SELECTED_VENTURES"] = ",".join(selected_ventures)

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
        # If paused, resume first so the process can be terminated cleanly
        if self._is_paused and self._bot_process and self._bot_process.is_alive():
            self._resume_process(self._bot_process.pid)
        self._is_paused = False
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
        self._play_pause_btn.configure(text=self._("btn_run"),
                                       bg=t["accent"], fg=t["accent_fg"])
        self._stop_btn.configure(bg=t["btn_neutral"], fg=t["btn_neu_fg"], state=tk.DISABLED)
        self._set_status("status_stopped")

    def _check_thread(self):
        if self._bot_process and self._bot_process.is_alive():
            self.after(300, self._check_thread)
        else:
            self._is_paused = False
            self._progress.stop()
            t = self._theme
            self._play_pause_btn.configure(text=self._("btn_run"),
                                           bg=t["accent"], fg=t["accent_fg"])
            self._stop_btn.configure(bg=t["btn_neutral"], fg=t["btn_neu_fg"], state=tk.DISABLED)
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
