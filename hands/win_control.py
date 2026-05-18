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


# ── foreground focus helper ───────────────────────────────────────────────────

def _force_foreground(hwnd: int):
    """SetForegroundWindow with Alt-key trick to bypass Windows foreground lock."""
    try:
        import win32api
        win32gui.ShowWindow(hwnd, 9)  # SW_RESTORE
        win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
        win32gui.SetForegroundWindow(hwnd)
        win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
    except Exception as e:
        _dbg(f"_force_foreground error: {e}")


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
        _force_foreground(hwnd)
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
    _force_foreground(hwnd)
    time.sleep(0.4)
    if new_line_first:
        win32gui.SendMessage(target, win32con.WM_KEYDOWN, win32con.VK_END, 0)
        win32gui.SendMessage(target, win32con.WM_CHAR, ord('\r'), 0)
        time.sleep(0.05)
    for ch in text:
        win32gui.SendMessage(target, win32con.WM_CHAR, ord(ch), 0)
        time.sleep(0.008)
    _dbg("wm_char done")
    return True


# ── Active window detection ───────────────────────────────────────────────────

def get_active_window_title() -> str:
    """Return the title of the currently focused window, or '' if unavailable."""
    if _HAS_WIN32:
        try:
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)
            if title:
                return title
        except Exception:
            pass
    # pygetwindow fallback
    try:
        import pygetwindow as gw
        w = gw.getActiveWindow()
        if w and w.title:
            return w.title
    except Exception:
        pass
    return ""


def get_active_window_context() -> str:
    """Return a one-line context string ready to inject into Claude prompts.
    e.g. 'ACTIVE WINDOW: "Inbox - william@... - Outlook" (Microsoft Outlook)'"""
    title = get_active_window_title()
    if not title:
        return ""

    # Map common title fragments to friendly app names
    _APP_HINTS = [
        ("outlook", "Microsoft Outlook"),
        ("edge", "Microsoft Edge"),
        ("chrome", "Google Chrome"),
        ("firefox", "Firefox"),
        ("teams", "Microsoft Teams"),
        ("8x8", "8x8 Work"),
        ("notepad", "Notepad"),
        ("excel", "Microsoft Excel"),
        ("word", "Microsoft Word"),
        ("autotask", "Autotask"),
        ("powershell", "PowerShell"),
        ("cmd.exe", "Command Prompt"),
        ("explorer", "File Explorer"),
    ]
    app_hint = next(
        (hint for frag, hint in _APP_HINTS if frag in title.lower()),
        ""
    )
    if app_hint:
        return f'ACTIVE WINDOW: "{title}" ({app_hint})'
    return f'ACTIVE WINDOW: "{title}"'


# ── Public helpers ────────────────────────────────────────────────────────────

def win32_focus(title_contains: str) -> bool:
    hwnd = _find_hwnd(title_contains)
    if not hwnd:
        return False
    try:
        _force_foreground(hwnd)
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

    def find_and_click_element(self, app_title: str, element_name: str,
                               element_type: str = None) -> bool:
        """Click a named UI element inside a specific app window using Windows Accessibility.

        Searches by element name (partial, case-insensitive) and optional control type.
        This lets ARTY click the 'X' in 8x8 without hitting Chrome's 'X', for example.
        Tries UIA backend first (modern apps / Electron), then Win32 backend.
        """
        if not _HAS_PYWINAUTO:
            _dbg("pywinauto unavailable — cannot click by element name")
            return False

        for backend in ("uia", "win32"):
            try:
                app = Application(backend=backend).connect(
                    title_re=f".*{app_title}.*", timeout=3
                )
                dlg = app.top_window()
                criteria: dict = {}
                if element_type:
                    criteria["control_type"] = element_type
                for name_arg in (
                    {"title": element_name},
                    {"title_re": f".*{element_name}.*"},
                    {"auto_id": element_name},
                ):
                    try:
                        ctrl = dlg.child_window(**{**criteria, **name_arg})
                        ctrl.wait("visible enabled", timeout=2)
                        ctrl.click_input()
                        _dbg(f"clicked '{element_name}' in '{app_title}' via {backend}")
                        return True
                    except Exception:
                        continue
            except Exception as e:
                _dbg(f"backend={backend} connect failed: {e}")
                continue
        _dbg(f"find_and_click_element: '{element_name}' not found in '{app_title}'")
        return False

    def list_interactive_elements(self, app_title: str) -> list:
        """Return all visible, enabled interactive elements in a window.

        Each entry: {name, type, auto_id, rect, backend}.
        Useful for ARTY to discover what it can click in an app without guessing coordinates.
        Tries UIA first (richer data), falls back to Win32.
        """
        if not _HAS_PYWINAUTO:
            return []

        for backend in ("uia", "win32"):
            try:
                app = Application(backend=backend).connect(
                    title_re=f".*{app_title}.*", timeout=3
                )
                dlg  = app.top_window()
                results = []
                for ctrl in dlg.descendants():
                    try:
                        if not ctrl.is_visible() or not ctrl.is_enabled():
                            continue
                        rect = ctrl.rectangle()
                        if rect.width() == 0 or rect.height() == 0:
                            continue
                        results.append({
                            "name":     ctrl.window_text().strip(),
                            "type":     ctrl.friendly_class_name(),
                            "auto_id":  getattr(ctrl, "automation_id", lambda: "")(),
                            "rect": {
                                "left":   rect.left,
                                "top":    rect.top,
                                "right":  rect.right,
                                "bottom": rect.bottom,
                            },
                            "backend": backend,
                        })
                    except Exception:
                        continue
                _dbg(f"list_interactive_elements: {len(results)} elements in '{app_title}' ({backend})")
                return results
            except Exception as e:
                _dbg(f"list_interactive_elements backend={backend} failed: {e}")
                continue
        return []

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
