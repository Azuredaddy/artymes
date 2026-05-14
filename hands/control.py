import pyautogui
import subprocess
import time

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05

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
            time.sleep(1.2)
        else:
            # Fall back to Windows search
            pyautogui.hotkey("win")
            time.sleep(0.6)
            pyautogui.typewrite(app_name, interval=0.05)
            time.sleep(0.5)
            pyautogui.press("enter")
            time.sleep(1.2)

    def screen_size(self) -> tuple:
        return pyautogui.size()

    def execute_action(self, action: dict) -> str:
        """Execute a structured action dict returned by Claude. Returns narration string."""
        atype = action.get("action", "")
        params = action.get("params", {})
        narration = action.get("narration", f"Executing {atype}")

        if atype == "click":
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
