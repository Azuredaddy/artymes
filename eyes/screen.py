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
        shot = self.sct.grab(monitor)
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        # Cap at 1280px wide to keep payload reasonable for Claude vision
        if img.width > 1280:
            ratio = 1280 / img.width
            img = img.resize((1280, int(img.height * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    def get_screen_size(self, monitor: int = 1) -> tuple:
        m = self.sct.monitors[min(monitor, len(self.sct.monitors) - 1)]
        return m["width"], m["height"]
