"""
ArtyWinControl — Windows-native app control.

Input strategy (in order):
1. SetForegroundWindow + SendInput  (universal — works on modern WinUI/UWP/Electron)
2. WM_CHAR to Edit handle           (classic Win32 apps, no focus needed)
3. pywinauto accessibility API      (last resort)
"""
import ctypes
import ctypes.wintypes as wintypes
import time

# ── SendInput structs (no extra dependencies — pure ctypes) ───────────────────
INPUT_KEYBOARD   = 1
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_KEYUP  = 0x0002
VK_RETURN = 0x0D
VK_END    = 0x23

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk",         wintypes.WORD),
        ("wScan",       wintypes.WORD),
        ("dwFlags",     wintypes.DWORD),
        ("time",        wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("_input", _INPUT_UNION)]

_send = ctypes.windll.user32.SendInput

# Debug helper — set ARTY_DEBUG=1 env var to enable
import os as _os
_DEBUG = _os.environ.get("ARTY_DEBUG", "0") == "1"
def _dbg(msg: str):
    if _DEBUG:
        print(f"  [WIN] {msg}", flush=True)


def _ki(vk=0, scan=0, flags=0):
    return KEYBDINPUT(vk, scan, flags, 0, None)


def _sendinput_text(text: str):
    """Inject text into the focused window via SendInput Unicode events."""
    inputs = []
    for ch in text:
        code = ord(ch)
        if ch in ('\r', '\n'):
            inputs += [
                INPUT(INPUT_KEYBOARD, _INPUT_UNION(ki=_ki(VK_RETURN, 0, 0))),
                INPUT(INPUT_KEYBOARD, _INPUT_UNION(ki=_ki(VK_RETURN, 0, KEYEVENTF_KEYUP))),
            ]
        else:
            inputs += [
                INPUT(INPUT_KEYBOARD, _INPUT_UNION(ki=_ki(0, code, KEYEVENTF_UNICODE))),
                INPUT(INPUT_KEYBOARD, _INPUT_UNION(ki=_ki(0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP))),
            ]
    if not inputs:
        return
    arr = (INPUT * len(inputs))(*inputs)
    _send(len(inputs), arr, ctypes.sizeof(INPUT))


def _press_key(vk: int):
    arr = (INPUT * 2)(
        INPUT(INPUT_KEYBOARD, _INPUT_UNION(ki=_ki(vk, 0, 0))),
        INPUT(INPUT_KEYBOARD, _INPUT_UNION(ki=_ki(vk, 0, KEYEVENTF_KEYUP))),
    )
    _send(2, arr, ctypes.sizeof(INPUT))


# ── win32 imports (optional) ──────────────────────────────────────────────────
try:
    import win32gui
    import win32con
    import win32com.client
    _HAS_WIN32 = True
except ImportError:
    _HAS_WIN32 = False

try:
    from pywinauto import Application, findwindows
    from pywinauto.keyboard import send_keys
    _HAS_PYWINAUTO = True
except ImportError:
    _HAS_PYWINAUTO = False


# ── window finding ────────────────────────────────────────────────────────────

def _find_window_handle(title_contains: str) -> int:
    if not _HAS_WIN32:
        _dbg("win32 not available — pywin32 not installed")
        return 0
    result = []
    all_titles = []
    def _cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            t = win32gui.GetWindowText(hwnd)
            if t:
                all_titles.append(t)
            if title_contains.lower() in t.lower():
                result.append(hwnd)
    win32gui.EnumWindows(_cb, None)
    if result:
        _dbg(f"found window '{win32gui.GetWindowText(result[0])}' (hwnd={result[0]})")
    else:
        _dbg(f"no window matching '{title_contains}'. visible: {all_titles[:8]}")
    return result[0] if result else 0


def _find_edit_handle(parent_hwnd: int) -> int:
    if not _HAS_WIN32 or not parent_hwnd:
        return 0
    for cls in ("Edit", "RichEdit20W", "RichEditD2DPT", "RICHEDIT50W", "Scintilla"):
        h = win32gui.FindWindowEx(parent_hwnd, None, cls, None)
        if h:
            return h
    return 0


def _foreground(hwnd: int) -> bool:
    """Bring hwnd to the foreground. Returns True on success."""
    try:
        win32gui.ShowWindow(hwnd, 9)   # SW_RESTORE
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.4)
        _dbg(f"SetForegroundWindow({hwnd}) OK")
        return True
    except Exception as e:
        _dbg(f"SetForegroundWindow({hwnd}) FAILED: {e}")
        return False


# ── primary input: SendInput (works on modern WinUI/UWP/Electron apps) ────────

def sendinput_type_into(title_contains: str, text: str, new_line_first: bool = False) -> bool:
    """Focus window then inject text via SendInput. Works on any modern app."""
    _dbg(f"sendinput_type_into('{title_contains}', '{text[:30]}', new_line={new_line_first})")
    hwnd = _find_window_handle(title_contains)
    if not hwnd:
        _dbg("sendinput: window not found — aborting")
        return False
    if not _foreground(hwnd):
        _dbg("sendinput: could not foreground window — aborting")
        return False
    _dbg(f"sendinput: sending {len(text)} chars via SendInput")
    if new_line_first:
        _press_key(VK_END)
        _press_key(VK_RETURN)
        time.sleep(0.05)
    _sendinput_text(text)
    _dbg("sendinput: done")
    return True


# ── secondary input: WM_CHAR (classic Win32 edit controls, no focus needed) ───

def wm_char_type_into(title_contains: str, text: str, new_line_first: bool = False) -> bool:
    """Send WM_CHAR directly to an Edit control. No focus needed."""
    _dbg(f"wm_char_type_into('{title_contains}', '{text[:30]}')")
    if not _HAS_WIN32:
        _dbg("wm_char: win32 not available")
        return False
    hwnd = _find_window_handle(title_contains)
    if not hwnd:
        _dbg("wm_char: window not found")
        return False
    edit = _find_edit_handle(hwnd)
    target = edit if edit else hwnd
    _foreground(hwnd)
    if new_line_first:
        win32gui.SendMessage(target, win32con.WM_KEYDOWN, win32con.VK_END, 0)
        win32gui.SendMessage(target, win32con.WM_CHAR, ord('\r'), 0)
        time.sleep(0.05)
    for ch in text:
        win32gui.SendMessage(target, win32con.WM_CHAR, ord(ch), 0)
        time.sleep(0.008)
    return True


# ── public helpers ─────────────────────────────────────────────────────────────

def win32_focus(title_contains: str) -> bool:
    if not _HAS_WIN32:
        return False
    hwnd = _find_window_handle(title_contains)
    if not hwnd:
        return False
    return _foreground(hwnd)


def win32_list_windows() -> list:
    if not _HAS_WIN32:
        return []
    titles = []
    def _cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            t = win32gui.GetWindowText(hwnd)
            if t:
                titles.append(t)
    win32gui.EnumWindows(_cb, None)
    return titles


# ── ArtyWinControl class ───────────────────────────────────────────────────────

class ArtyWinControl:

    def connect(self, title_contains: str):
        if not _HAS_PYWINAUTO:
            return None
        try:
            return Application(backend="uia").connect(title_re=f".*{title_contains}.*", timeout=3)
        except Exception:
            try:
                return Application(backend="win32").connect(title_re=f".*{title_contains}.*", timeout=3)
            except Exception:
                return None

    def focus(self, title_contains: str) -> bool:
        if win32_focus(title_contains):
            return True
        app = self.connect(title_contains)
        if not app:
            return False
        try:
            app.top_window().set_focus()
            time.sleep(0.3)
            return True
        except Exception:
            return False

    def type_into(self, title_contains: str, text: str, new_line_first: bool = False) -> bool:
        """Try all input strategies in order. Returns True if any succeeded."""
        # Strategy 1: SendInput (universal — works on modern apps)
        if sendinput_type_into(title_contains, text, new_line_first):
            return True
        # Strategy 2: WM_CHAR (classic Win32 edit controls)
        if wm_char_type_into(title_contains, text, new_line_first):
            return True
        # Strategy 3: pywinauto
        if not _HAS_PYWINAUTO:
            return False
        app = self.connect(title_contains)
        if not app:
            return False
        try:
            dlg = app.top_window()
            dlg.set_focus()
            time.sleep(0.3)
            if new_line_first:
                send_keys("{END}{ENTER}")
                time.sleep(0.1)
            try:
                import pyperclip
                pyperclip.copy(text)
                send_keys("^v")
            except Exception:
                send_keys(text, with_spaces=True)
            return True
        except Exception:
            return False

    def click_control(self, title_contains: str, control_name: str = None) -> bool:
        if win32_focus(title_contains):
            return True
        if not _HAS_PYWINAUTO:
            return False
        app = self.connect(title_contains)
        if not app:
            return False
        try:
            dlg = app.top_window()
            dlg.set_focus()
            time.sleep(0.3)
            ctrl = dlg[control_name] if control_name else dlg.Edit
            ctrl.click_input()
            return True
        except Exception:
            return False

    def list_windows(self) -> list:
        titles = win32_list_windows()
        if titles:
            return titles
        if not _HAS_PYWINAUTO:
            return []
        try:
            return [w.window_text() for w in findwindows.find_elements(visible_only=True) if w.window_text()]
        except Exception:
            return []
