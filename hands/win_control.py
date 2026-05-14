"""
ArtyWinControl — Windows-native app control.

Priority stack for typing into an app:
1. win32 WM_CHAR direct messaging (most reliable — no focus/coords needed)
2. pywinauto accessibility API (good for UI elements by name)
3. pyautogui clipboard paste (fallback)
"""
import time

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


def _find_window_handle(title_contains: str) -> int:
    """Find a window HWND by partial title. Returns 0 if not found."""
    if not _HAS_WIN32:
        return 0
    result = []
    def _cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            t = win32gui.GetWindowText(hwnd)
            if title_contains.lower() in t.lower():
                result.append(hwnd)
    win32gui.EnumWindows(_cb, None)
    return result[0] if result else 0


def _find_edit_handle(parent_hwnd: int) -> int:
    """Find the main Edit control inside a window."""
    if not _HAS_WIN32 or not parent_hwnd:
        return 0
    # Try common text control class names
    for cls in ("Edit", "RichEdit20W", "RichEditD2DPT", "RICHEDIT50W", "Scintilla"):
        h = win32gui.FindWindowEx(parent_hwnd, None, cls, None)
        if h:
            return h
    return 0


def win32_type_into(title_contains: str, text: str, new_line_first: bool = False) -> bool:
    """Send text directly to a window's Edit control via WM_CHAR.
    Works without focus, without coordinates. Most reliable method."""
    if not _HAS_WIN32:
        return False

    hwnd = _find_window_handle(title_contains)
    if not hwnd:
        return False

    edit = _find_edit_handle(hwnd)
    target = edit if edit else hwnd

    # Bring window to foreground first
    try:
        win32gui.ShowWindow(hwnd, 5)   # SW_SHOW
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.3)
    except Exception:
        pass

    if new_line_first:
        # Move to end then newline
        win32gui.SendMessage(target, win32con.WM_KEYDOWN, win32con.VK_END, 0)
        win32gui.SendMessage(target, win32con.WM_CHAR, ord('\r'), 0)
        time.sleep(0.05)

    for char in text:
        win32gui.SendMessage(target, win32con.WM_CHAR, ord(char), 0)
        time.sleep(0.01)

    return True


def win32_focus(title_contains: str) -> bool:
    """Bring a window to front using win32."""
    if not _HAS_WIN32:
        return False
    hwnd = _find_window_handle(title_contains)
    if not hwnd:
        return False
    try:
        win32gui.ShowWindow(hwnd, 5)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.3)
        return True
    except Exception:
        return False


def win32_list_windows() -> list:
    """List all visible window titles via win32."""
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
        """Try win32 direct messaging first, then pywinauto, then give up."""
        # Strategy 1: win32 WM_CHAR — most reliable
        if win32_type_into(title_contains, text, new_line_first):
            return True

        # Strategy 2: pywinauto accessibility
        if not _HAS_PYWINAUTO:
            return False
        app = self.connect(title_contains)
        if not app:
            return False
        try:
            dlg = app.top_window()
            dlg.set_focus()
            time.sleep(0.3)
            try:
                edit = dlg.Edit
                edit.set_focus()
            except Exception:
                pass
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
            # Win32 focused it — good enough for most cases
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
            try:
                ctrl = dlg[control_name] if control_name else dlg.Edit
                ctrl.click_input()
            except Exception:
                dlg.click_input()
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
