import pyautogui
import subprocess
import time
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

    def hotkey(self, *keys):
        pyautogui.hotkey(*keys)

    def scroll(self, x: int, y: int, amount: int):
        pyautogui.scroll(amount, x=x, y=y)

    def open_app(self, app_name: str):
        exe = WINDOWS_APPS.get(app_name.lower().strip())
        if exe:
            subprocess.Popen([exe])
            time.sleep(2.0)  # wait for window to fully appear and focus
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
            if not self.type_into_window(app_title, text, new_line):
                # Fallback to clipboard paste at current focus
                if _HAS_CLIPBOARD:
                    pyperclip.copy(text)
                    pyautogui.hotkey("ctrl", "v")
                else:
                    pyautogui.typewrite(text, interval=0.04)
        elif atype == "focus_window":
            self.click_into_window(params.get("title", ""))
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
            self.hotkey(*params["keys"])
        elif atype == "scroll":
            self.scroll(params["x"], params["y"], params["amount"])
        elif atype == "open":
            self.open_app(params["app"])
        elif atype == "wait":
            time.sleep(params.get("seconds", 1))

        return narration
