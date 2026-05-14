"""
ArtyWinControl — Windows-native app control.

Strategy:
1. win32 GetWindowRect → click content area → clipboard paste  (primary)
2. WM_CHAR to Edit ctrl                                         (classic apps)
3. pywinauto UIA                                                (fallback)
"""
import time
import os as _os

_DEBUG = _os.environ.get("ARTY_DEBUG", "0") == "1"
def _dbg(msg: str):
    if _DEBUG:
        print(f"  [WIN] {msg}", flush=True)

# ── optional imports ──────────────────────────────────────────────────────────
try:
    import win32gui, win32con
    _HAS_WIN32 = True
except ImportError:
    _HAS_WIN32 = False

try:
    from pywinauto import Application, findwindows
    from pywinauto.keyboard import send_keys
    _HAS_PYWINAUTO = True
except ImportError:
    _HAS_PYWINAUTO = False

try:
    import pyautogui
    _HAS_PYAUTOGUI = True
except ImportError:
    _HAS_PYAUTOGUI = False

try:
    import pyperclip
    _HAS_CLIP = True
except ImportError:
    _HAS_CLIP = False


# ── window finding ────────────────────────────────────────────────────────────

def _find_hwnd(title_contains: str) -> int:
    if not _HAS_WIN32:
        _dbg("win32 unavailable")
        return 0
    result = []
    all_visible = []
    def _cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            t = win32gui.GetWindowText(hwnd)
            if t:
                all_visible.append(t)
            if title_contains.lower() in t.lower():
                result.append(hwnd)
    win32gui.EnumWindows(_cb, None)
    if result:
        _dbg(f"found '{win32gui.GetWindowText(result[0])}' hwnd={result[0]}")
    else:
        _dbg(f"no match for '{title_contains}'. windows={all_visible[:8]}")
    return result[0] if result else 0


def _content_center(hwnd: int) -> tuple:
    """Return (cx, cy) in the content area of the window (below title bar)."""
    rect = win32gui.GetWindowRect(hwnd)
    left, top, right, bottom = rect
    cx = (left + right) // 2
    cy = top + 60 + (bottom - top - 60) // 2  # skip ~60px title bar
    _dbg(f"rect={rect} content_center=({cx},{cy})")
    return cx, cy


# ── Strategy 1: GetWindowRect → click → clipboard paste ──────────────────────

def click_paste_type_into(title_contains: str, text: str, new_line_first: bool = False) -> bool:
    _dbg(f"click_paste: target='{title_contains}' text='{text[:40]}'")
    if not (_HAS_WIN32 and _HAS_PYAUTOGUI and _HAS_CLIP):
        missing = [n for n,v in [("win32",_HAS_WIN32),("pyautogui",_HAS_PYAUTOGUI),("pyperclip",_HAS_CLIP)] if not v]
        _dbg(f"missing deps: {missing}")
        return False
    hwnd = _find_hwnd(title_contains)
    if not hwnd:
        return False
    cx, cy = _content_center(hwnd)
    try:
        win32gui.ShowWindow(hwnd, 9)        # SW_RESTORE
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.5)
        pyautogui.click(cx, cy)
        time.sleep(0.4)
        _dbg(f"clicked ({cx},{cy}), pasting text")
        if new_line_first:
            pyautogui.hotkey("ctrl", "end")
            pyautogui.press("enter")
            time.sleep(0.1)
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
        _dbg("click_paste done")
        return True
    except Exception as e:
        _dbg(f"click_paste error: {e}")
        return False


# ── Strategy 2: WM_CHAR (classic Win32 edit controls) ────────────────────────

def wm_char_type_into(title_contains: str, text: str, new_line_first: bool = False) -> bool:
    _dbg(f"wm_char: target='{title_contains}'")
    if not _HAS_WIN32:
        return False
    hwnd = _find_hwnd(title_contains)
    if not hwnd:
        return False
    edit = 0
    for cls in ("Edit", "RichEdit20W", "RichEditD2DPT", "RICHEDIT50W", "Scintilla"):
        edit = win32gui.FindWindowEx(hwnd, None, cls, None)
        if edit:
            break
    target = edit if edit else hwnd
    _dbg(f"wm_char target hwnd={target} (edit={edit})")
    try:
        win32gui.ShowWindow(hwnd, 9)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.4)
    except Exception as e:
        _dbg(f"wm_char foreground: {e}")
    if new_line_first:
        win32gui.SendMessage(target, win32con.WM_KEYDOWN, win32con.VK_END, 0)
        win32gui.SendMessage(target, win32con.WM_CHAR, ord('\r'), 0)
        time.sleep(0.05)
    for ch in text:
        win32gui.SendMessage(target, win32con.WM_CHAR, ord(ch), 0)
        time.sleep(0.008)
    _dbg("wm_char done")
    return True


# ── Public helpers ────────────────────────────────────────────────────────────

def win32_focus(title_contains: str) -> bool:
    hwnd = _find_hwnd(title_contains)
    if not hwnd:
        return False
    try:
        win32gui.ShowWindow(hwnd, 9)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.4)
        return True
    except Exception:
        return False


def win32_list_windows() -> list:
    if not _HAS_WIN32:
        return []
    titles = []
    def _cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
            titles.append(win32gui.GetWindowText(hwnd))
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
        return win32_focus(title_contains)

    def type_into(self, title_contains: str, text: str, new_line_first: bool = False) -> bool:
        # Strategy 1: click content area then clipboard paste
        if click_paste_type_into(title_contains, text, new_line_first):
            return True
        # Strategy 2: WM_CHAR
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
            if _HAS_CLIP:
                pyperclip.copy(text)
                send_keys("^v")
            else:
                send_keys(text, with_spaces=True)
            return True
        except Exception:
            return False

    def click_control(self, title_contains: str, control_name: str = None) -> bool:
        return win32_focus(title_contains)

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
