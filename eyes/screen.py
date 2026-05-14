import mss
from PIL import Image
import base64
import io


class ArtyEyes:
    def __init__(self):
        self.sct = mss.mss()

    def get_monitor_count(self) -> int:
        return len(self.sct.monitors) - 1  # monitors[0] is "all screens combined"

    def capture_all(self) -> str:
        """Capture all monitors combined as base64 JPEG."""
        return self._grab(self.sct.monitors[0])

    def capture_monitor(self, index: int = 1) -> str:
        """Capture a specific monitor (1-indexed)."""
        monitors = self.sct.monitors
        idx = min(index, len(monitors) - 1)
        return self._grab(monitors[idx])

    def capture_primary(self) -> str:
        return self.capture_monitor(1)

    def _grab(self, monitor) -> str:
        b64, _, _ = self._grab_with_scale(monitor)
        return b64

    def _grab_with_scale(self, monitor) -> tuple:
        """Returns (base64_jpeg, x_scale, y_scale).
        Scale factors convert Claude's image coords back to real screen coords."""
        shot = self.sct.grab(monitor)
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        orig_w, orig_h = img.width, img.height
        if orig_w > 1280:
            ratio = 1280 / orig_w
            img = img.resize((1280, int(orig_h * ratio)), Image.LANCZOS)
        scaled_w, scaled_h = img.size
        x_scale = orig_w / scaled_w
        y_scale = orig_h / scaled_h
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        return b64, x_scale, y_scale

    def capture_all_with_scale(self) -> tuple:
        """Capture all monitors and return (base64_jpeg, x_scale, y_scale)."""
        return self._grab_with_scale(self.sct.monitors[0])

    def capture_with_focus(self, title_contains: str = None) -> tuple:
        """Capture the monitor containing the named window (or primary monitor as fallback).
        Returns (b64, x_offset, y_offset, x_scale, y_scale).
        x_offset/y_offset are the monitor's top-left in global screen space."""
        if title_contains:
            try:
                import win32gui
                hwnd = 0
                def _cb(h, _):
                    nonlocal hwnd
                    if not hwnd and win32gui.IsWindowVisible(h):
                        if title_contains.lower() in win32gui.GetWindowText(h).lower():
                            hwnd = h
                win32gui.EnumWindows(_cb, None)
                if hwnd:
                    rect = win32gui.GetWindowRect(hwnd)
                    cx = (rect[0] + rect[2]) // 2
                    for m in self.sct.monitors[1:]:
                        if m['left'] <= cx < m['left'] + m['width']:
                            b64, xs, ys = self._grab_with_scale(m)
                            return b64, m['left'], m['top'], xs, ys
            except Exception:
                pass
        # Fall back to primary monitor — the combined-all-monitors image compresses
        # 3×1920px into 1280px, making Claude's coordinate estimates 4.5× less accurate.
        primary = self.sct.monitors[1] if len(self.sct.monitors) > 1 else self.sct.monitors[0]
        b64, xs, ys = self._grab_with_scale(primary)
        return b64, primary["left"], primary["top"], xs, ys

    def capture_primary_native(self) -> tuple:
        """Capture primary monitor and return (base64_jpeg, real_width, real_height).
        Used by Computer Use API — Claude needs real pixel dimensions for coordinates."""
        monitor = self.sct.monitors[1] if len(self.sct.monitors) > 1 else self.sct.monitors[0]
        shot = self.sct.grab(monitor)
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        real_w, real_h = img.width, img.height
        # Scale down for API payload size, but return REAL dimensions for Claude's coord space
        if img.width > 1366:
            ratio = 1366 / img.width
            img = img.resize((1366, int(img.height * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        return base64.b64encode(buf.getvalue()).decode("utf-8"), real_w, real_h

    def get_screen_size(self, monitor: int = 1) -> tuple:
        m = self.sct.monitors[min(monitor, len(self.sct.monitors) - 1)]
        return m["width"], m["height"]
