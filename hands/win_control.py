from pywinauto import Application, findwindows
from pywinauto.keyboard import send_keys
import time


class ArtyWinControl:
    def connect(self, title_contains: str):
        """Connect to a window by partial title. Returns pywinauto app or None."""
        try:
            return Application(backend="uia").connect(title_re=f".*{title_contains}.*", timeout=3)
        except Exception:
            try:
                return Application(backend="win32").connect(title_re=f".*{title_contains}.*", timeout=3)
            except Exception:
                return None

    def focus(self, title_contains: str) -> bool:
        """Bring a window to front."""
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
        """Find a window and type directly into its text area — no coordinates needed.
        new_line_first=True moves to end of text and presses Enter before typing."""
        app = self.connect(title_contains)
        if not app:
            return False
        try:
            dlg = app.top_window()
            dlg.set_focus()
            time.sleep(0.3)
            # Try to find an Edit control first
            try:
                edit = dlg.Edit
                edit.set_focus()
                if new_line_first:
                    send_keys("{END}{ENTER}")
                    time.sleep(0.1)
                # Use clipboard to paste — handles all characters
                import pyperclip
                pyperclip.copy(text)
                send_keys("^v")
            except Exception:
                # Fallback: send to window directly
                if new_line_first:
                    send_keys("{END}{ENTER}")
                import pyperclip
                pyperclip.copy(text)
                send_keys("^v")
            return True
        except Exception as e:
            return False

    def click_control(self, title_contains: str, control_name: str = None) -> bool:
        """Click a named control in a window, or click into the window's main area."""
        app = self.connect(title_contains)
        if not app:
            return False
        try:
            dlg = app.top_window()
            dlg.set_focus()
            time.sleep(0.3)
            if control_name:
                dlg[control_name].click_input()
            else:
                dlg.Edit.click_input()
            return True
        except Exception:
            try:
                dlg.click_input()
                return True
            except Exception:
                return False

    def list_windows(self) -> list:
        """List all visible window titles."""
        try:
            return [w.window_text() for w in findwindows.find_elements(visible_only=True) if w.window_text()]
        except Exception:
            return []
