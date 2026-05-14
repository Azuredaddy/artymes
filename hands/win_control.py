"""
ArtyWinControl — Windows-native app control.

Input strategy (in order):
1. PowerShell SendKeys   — built into Windows, runs in own process, most reliable
2. WM_CHAR to Edit ctrl  — classic Win32 apps (Notepad old, etc.)
3. pywinauto UIA         — accessibility fallback
"""
import subprocess
import time
import os as _os
from rich.console import Console as _con

_DEBUG = _os.environ.get("ARTY_DEBUG", "0") == "1"
def _dbg(msg: str):
    if _DEBUG:
        _con().print(f"  [dim cyan][WIN] {msg}[/dim cyan]")

# ── win32 imports (optional) ──────────────────────────────────────────────────
try:
    import win32gui
    import win32con
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
        _dbg("win32 not available")
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
        _dbg(f"found hwnd={result[0]} title='{win32gui.GetWindowText(result[0])}'")
    else:
        _dbg(f"no match for '{title_contains}'. visible: {all_titles[:6]}")
    return result[0] if result else 0


def _find_edit_handle(parent_hwnd: int) -> int:
    if not _HAS_WIN32 or not parent_hwnd:
        return 0
    for cls in ("Edit", "RichEdit20W", "RichEditD2DPT", "RICHEDIT50W", "Scintilla"):
        h = win32gui.FindWindowEx(parent_hwnd, None, cls, None)
        if h:
            return h
    return 0


# ── Strategy 1: PowerShell SendKeys ──────────────────────────────────────────

def _escape_sendkeys(text: str) -> str:
    """Escape special SendKeys characters."""
    special = {'+': '{+}', '^': '{^}', '%': '{%}', '~': '{~}',
               '(': '{(}', ')': '{)}', '[': '{[}', ']': '{]}',
               '{': '{{', '}': '}}'}
    return ''.join(special.get(c, c) for c in text)


def ps_type_into(title_contains: str, text: str, new_line_first: bool = False) -> bool:
    """Use PowerShell SendKeys to type into a named window. No focus/coord issues."""
    _dbg(f"ps_type_into('{title_contains}', '{text[:30]}', new_line={new_line_first})")
    escaped = _escape_sendkeys(text)
    nl = "~" if new_line_first else ""   # ~ is Enter in SendKeys
    ps = f"""
Add-Type -AssemblyName Microsoft.VisualBasic
Add-Type -AssemblyName System.Windows.Forms
$w = Get-Process | Where-Object {{ $_.MainWindowTitle -like '*{title_contains}*' }} | Select-Object -First 1
if (-not $w) {{ exit 1 }}
[Microsoft.VisualBasic.Interaction]::AppActivate($w.Id)
Start-Sleep -Milliseconds 600
[System.Windows.Forms.SendKeys]::SendWait('{nl}{escaped}')
exit 0
"""
    try:
        r = subprocess.run(
            ["powershell", "-WindowStyle", "Hidden", "-NonInteractive", "-Command", ps],
            capture_output=True, timeout=10
        )
        _dbg(f"ps_type_into returncode={r.returncode} stderr={r.stderr.decode(errors='ignore')[:100]}")
        return r.returncode == 0
    except Exception as e:
        _dbg(f"ps_type_into exception: {e}")
        return False


# ── Strategy 2: WM_CHAR (classic Win32 edit controls) ────────────────────────

def wm_char_type_into(title_contains: str, text: str, new_line_first: bool = False) -> bool:
    """Send WM_CHAR to an Edit control — no focus needed, classic apps only."""
    _dbg(f"wm_char_type_into('{title_contains}', '{text[:30]}')")
    if not _HAS_WIN32:
        _dbg("wm_char: win32 unavailable")
        return False
    hwnd = _find_window_handle(title_contains)
    if not hwnd:
        return False
    edit = _find_edit_handle(hwnd)
    target = edit if edit else hwnd
    try:
        win32gui.ShowWindow(hwnd, 9)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.4)
    except Exception as e:
        _dbg(f"wm_char foreground failed: {e}")
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
    # Try PowerShell AppActivate first (more reliable than SetForegroundWindow)
    ps = f"""
Add-Type -AssemblyName Microsoft.VisualBasic
$w = Get-Process | Where-Object {{ $_.MainWindowTitle -like '*{title_contains}*' }} | Select-Object -First 1
if ($w) {{ [Microsoft.VisualBasic.Interaction]::AppActivate($w.Id); exit 0 }} else {{ exit 1 }}
"""
    try:
        r = subprocess.run(["powershell", "-WindowStyle", "Hidden", "-NonInteractive", "-Command", ps],
                           capture_output=True, timeout=5)
        if r.returncode == 0:
            time.sleep(0.4)
            return True
    except Exception:
        pass
    if not _HAS_WIN32:
        return False
    hwnd = _find_window_handle(title_contains)
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
        return win32_focus(title_contains)

    def type_into(self, title_contains: str, text: str, new_line_first: bool = False) -> bool:
        # Strategy 1: PowerShell SendKeys (most reliable)
        if ps_type_into(title_contains, text, new_line_first):
            return True
        # Strategy 2: WM_CHAR (classic Win32)
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
