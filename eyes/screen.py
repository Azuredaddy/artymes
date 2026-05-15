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
        """Capture primary monitor. Returns (b64, img_w, img_h, x_scale, y_scale).

        img_w/img_h  — exact JPEG dimensions; pass to Claude as display_width_px/display_height_px.
        x_scale/y_scale — multiply Claude's returned coordinates by these to get pyautogui
                          logical-pixel coordinates, correcting for DPI scaling and resize."""
        monitor = self.sct.monitors[1] if len(self.sct.monitors) > 1 else self.sct.monitors[0]
        shot = self.sct.grab(monitor)
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

        # pyautogui works in logical pixels; mss captures physical pixels.
        # We need the logical resolution to compute the correction factor.
        try:
            import pyautogui as _pag
            logical_w, logical_h = _pag.size()
        except Exception:
            logical_w, logical_h = img.width, img.height  # fallback: assume 1:1

        if img.width > 1366:
            ratio = 1366 / img.width
            img = img.resize((1366, int(img.height * ratio)), Image.LANCZOS)

        img_w, img_h = img.size
        # image coord × scale → pyautogui logical coord (absorbs both resize and DPI factors)
        x_scale = logical_w / img_w
        y_scale = logical_h / img_h

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        return base64.b64encode(buf.getvalue()).decode("utf-8"), img_w, img_h, x_scale, y_scale

    def capture_region_for_zoom(self, cx_logical: int, cy_logical: int,
                                radius: int = 200, monitor_idx: int = 1) -> tuple:
        """Zoom into a region around a logical-pixel coordinate for precision targeting.

        Returns (b64, zoom_w, zoom_h, region_left, region_top, region_w, region_h).
        To convert a zoomed-image coord (zx, zy) back to a logical screen coord:
            screen_x = region_left + (zx / zoom_w) * region_w
            screen_y = region_top  + (zy / zoom_h) * region_h
        """
        try:
            import pyautogui as _pag
            logical_w, logical_h = _pag.size()
        except Exception:
            logical_w, logical_h = 1920, 1080

        monitor = (self.sct.monitors[monitor_idx]
                   if monitor_idx < len(self.sct.monitors)
                   else self.sct.monitors[1])
        phys_w, phys_h = monitor["width"], monitor["height"]

        # Convert logical radius → physical pixels for mss grab
        px_scale_x = phys_w / logical_w
        px_scale_y = phys_h / logical_h
        cx_phys = int(cx_logical * px_scale_x)
        cy_phys = int(cy_logical * px_scale_y)
        rad_phys_x = int(radius * px_scale_x)
        rad_phys_y = int(radius * px_scale_y)

        left_phys  = max(0, cx_phys - rad_phys_x)
        top_phys   = max(0, cy_phys - rad_phys_y)
        right_phys = min(phys_w, cx_phys + rad_phys_x)
        bot_phys   = min(phys_h, cy_phys + rad_phys_y)

        region = {
            "left":   monitor["left"] + left_phys,
            "top":    monitor["top"]  + top_phys,
            "width":  right_phys - left_phys,
            "height": bot_phys   - top_phys,
        }
        shot = self.sct.grab(region)
        img  = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

        zoom_w, zoom_h = 512, 512
        img = img.resize((zoom_w, zoom_h), Image.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        # Region in logical coordinates (what pyautogui understands)
        region_left = left_phys  / px_scale_x
        region_top  = top_phys   / px_scale_y
        region_w    = (right_phys - left_phys) / px_scale_x
        region_h    = (bot_phys   - top_phys)  / px_scale_y

        return b64, zoom_w, zoom_h, region_left, region_top, region_w, region_h

    def get_screen_size(self, monitor: int = 1) -> tuple:
        m = self.sct.monitors[min(monitor, len(self.sct.monitors) - 1)]
        return m["width"], m["height"]
