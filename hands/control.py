import pyautogui
import subprocess
import time
import os as _os
from rich.console import Console as _Console
_con = _Console()
_DEBUG = _os.environ.get("ARTY_DEBUG", "0") == "1"
def _dbg(msg):
    if _DEBUG: _con.print(f"  [dim cyan][HANDS] {msg}[/dim cyan]")
try:
    import pyperclip
    _HAS_CLIPBOARD = True
except ImportError:
    _HAS_CLIPBOARD = False

try:
    import pygetwindow as gw
    _HAS_GW = True
except ImportError:
    _HAS_GW = False

try:
    from hands.win_control import ArtyWinControl
    _win_ctrl = ArtyWinControl()
    _HAS_WINCTRL = True
except Exception:
    _win_ctrl = None
    _HAS_WINCTRL = False

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.15

WINDOWS_APPS = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "paint": "mspaint.exe",
    "explorer": "explorer.exe",
    "chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "edge": "msedge.exe",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
    "word": "winword.exe",
    "excel": "excel.exe",
    "outlook": "outlook.exe",
    "teams": "teams.exe",
}


class ArtyHands:
    def click(self, x: int, y: int, button: str = "left"):
        pyautogui.click(x, y, button=button)

    def double_click(self, x: int, y: int):
        pyautogui.doubleClick(x, y)

    def right_click(self, x: int, y: int):
        pyautogui.rightClick(x, y)

    def move(self, x: int, y: int, duration: float = 0.3):
        pyautogui.moveTo(x, y, duration=duration)

    def type_text(self, text: str, interval: float = 0.04):
        if _HAS_CLIPBOARD:
            # Clipboard paste is faster and handles all characters reliably
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")
        else:
            pyautogui.typewrite(text, interval=interval)

    def press(self, key: str):
        pyautogui.press(key)

    def hotkey(self, *keys, window: str = ""):
        if window and _HAS_WINCTRL:
            _win_ctrl.focus(window)
            time.sleep(0.35)
        pyautogui.hotkey(*keys)

    def scroll(self, x: int, y: int, amount: int):
        pyautogui.scroll(amount, x=x, y=y)

    def open_app(self, app_name: str):
        exe = WINDOWS_APPS.get(app_name.lower().strip())
        if exe:
            try:
                subprocess.Popen([exe])
            except FileNotFoundError:
                # Browser/Office exes aren't in PATH — use Windows shell to resolve
                subprocess.Popen(f'start "" "{exe}"', shell=True)
            time.sleep(2.0)
        else:
            # Fall back to Windows search
            pyautogui.hotkey("win")
            time.sleep(0.8)
            pyautogui.typewrite(app_name, interval=0.06)
            time.sleep(0.8)
            pyautogui.press("enter")
            time.sleep(2.0)

    def find_window(self, title_contains: str):
        """Find an open window by partial title. Returns window object or None."""
        if not _HAS_GW:
            return None
        matches = [w for w in gw.getAllWindows() if title_contains.lower() in w.title.lower() and w.visible]
        return matches[0] if matches else None

    def focus_window(self, title_contains: str) -> dict | None:
        """Bring a window to front and return its position/size, or None if not found."""
        win = self.find_window(title_contains)
        if not win:
            return None
        try:
            win.activate()
            time.sleep(0.4)
        except Exception:
            pass
        return {"left": win.left, "top": win.top, "width": win.width, "height": win.height}

    def click_into_window(self, title_contains: str) -> bool:
        """Focus a window and click its text area (below the title bar)."""
        info = self.focus_window(title_contains)
        if not info:
            return False
        # Click slightly below centre-top to land in the content area, not the title bar
        cx = info["left"] + info["width"] // 2
        cy = info["top"] + info["height"] // 2
        pyautogui.click(cx, cy)
        return True

    def type_into_window(self, title_contains: str, text: str, new_line_first: bool = False) -> bool:
        """Type into a named window using pywinauto — no coordinates needed."""
        if _HAS_WINCTRL:
            return _win_ctrl.type_into(title_contains, text, new_line_first)
        return False

    def click_window(self, title_contains: str, control: str = None) -> bool:
        """Click into a named window's text area using pywinauto."""
        if _HAS_WINCTRL:
            return _win_ctrl.click_control(title_contains, control)
        return False

    def list_windows(self) -> list[str]:
        if not _HAS_GW:
            return []
        return [w.title for w in gw.getAllWindows() if w.title and w.visible]

    def screen_size(self) -> tuple:
        return pyautogui.size()

    def execute_action(self, action: dict) -> str:
        """Execute a structured action dict returned by Claude. Returns narration string."""
        atype = action.get("action", "")
        params = action.get("params", {})
        narration = action.get("narration", f"Executing {atype}")

        if atype == "direct_type":
            app_title = params.get("app", "")
            text = params.get("text", "")
            new_line = params.get("new_line", False)
            _dbg(f"direct_type → app='{app_title}' text='{text[:40]}' new_line={new_line}")
            ok = self.type_into_window(app_title, text, new_line)
            _dbg(f"type_into_window result: {ok}")
            if not ok:
                _dbg("falling back to click_into_window + clipboard paste")
                focused = self.click_into_window(app_title)
                _dbg(f"click_into_window: {focused}")
                time.sleep(0.5)
                if new_line:
                    pyautogui.hotkey("ctrl", "end")
                    pyautogui.press("enter")
                    time.sleep(0.1)
                if _HAS_CLIPBOARD:
                    _dbg("pasting via ctrl+v")
                    pyperclip.copy(text)
                    pyautogui.hotkey("ctrl", "v")
                else:
                    _dbg("typewrite fallback")
                    pyautogui.typewrite(text, interval=0.05)
        elif atype == "focus_window":
            title = params.get("title", "")
            if _HAS_WINCTRL:
                _win_ctrl.focus(title)  # uses win32 + Alt-key trick
            else:
                self.click_into_window(title)
        elif atype == "click":
            self.click(params["x"], params["y"])
        elif atype == "double_click":
            self.double_click(params["x"], params["y"])
        elif atype == "right_click":
            self.right_click(params["x"], params["y"])
        elif atype == "move":
            self.move(params["x"], params["y"])
        elif atype == "type":
            self.type_text(params["text"])
        elif atype == "press":
            self.press(params["key"])
        elif atype == "hotkey":
            self.hotkey(*params["keys"], window=params.get("window", ""))
        elif atype == "close":
            title = params.get("title", "")
            if _HAS_WINCTRL:
                _win_ctrl.focus(title)
                time.sleep(0.3)
            pyautogui.hotkey("alt", "f4")
        elif atype == "scroll":
            self.scroll(params["x"], params["y"], params["amount"])
        elif atype == "open":
            self.open_app(params["app"])
        elif atype == "wait":
            time.sleep(params.get("seconds", 1))
        elif atype == "click_element":
            # Click a named UI element inside a specific app — no coordinates needed.
            # params: {app: "8x8", element: "Create ticket", element_type: "Button" (optional)}
            # This is the safest way to click on one app's button without hitting another app's.
            if _HAS_WINCTRL:
                ok = _win_ctrl.find_and_click_element(
                    params.get("app", ""),
                    params.get("element", ""),
                    params.get("element_type"),
                )
                if not ok:
                    narration = f"Couldn't find '{params.get('element')}' in '{params.get('app')}'"
            else:
                narration = "UI automation unavailable — pywinauto not installed"
        elif atype == "list_elements":
            # Enumerate all clickable elements in a window so ARTY knows what to target.
            # params: {app: "8x8"}
            # Returns element list as narration string for ARTY to reason about.
            if _HAS_WINCTRL:
                elements = _win_ctrl.list_interactive_elements(params.get("app", ""))
                if elements:
                    lines = [
                        f"  [{e['type']}] '{e['name']}' id='{e['auto_id']}'"
                        for e in elements[:40]  # cap at 40 to avoid wall of text
                    ]
                    narration = f"Elements in '{params.get('app')}':\n" + "\n".join(lines)
                else:
                    narration = f"No elements found in '{params.get('app')}'"
            else:
                narration = "UI automation unavailable"

        return narration
