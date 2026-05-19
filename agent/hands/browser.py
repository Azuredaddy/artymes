"""
BrowserHands — Playwright-based browser control for ARTY.

Controls Chrome/Edge at the DOM level (element clicks by text/role/selector)
rather than pixel coordinates, so DPI scaling and window position are irrelevant.

Requires: pip install playwright && playwright install chromium
"""
import time
import base64
import os as _os

_DEBUG = _os.environ.get("ARTY_DEBUG", "0") == "1"
def _dbg(msg: str):
    if _DEBUG:
        print(f"  [BROWSER] {msg}", flush=True)

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    _HAS_PLAYWRIGHT = True
except ImportError:
    _HAS_PLAYWRIGHT = False
    _dbg("playwright not installed — run: pip install playwright && playwright install chromium")


class BrowserHands:
    """Playwright-backed browser control. One persistent browser instance per session."""

    def __init__(self):
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def start(self, headless: bool = False, channel: str = "chrome") -> bool:
        """Launch the browser. Returns True on success."""
        if not _HAS_PLAYWRIGHT:
            return False
        if self._page and not self._page.is_closed():
            return True  # already running
        try:
            self._pw = sync_playwright().start()
            # Try the requested channel; fall back to bundled chromium
            try:
                self._browser = self._pw.chromium.launch(
                    headless=headless,
                    channel=channel,
                    args=["--start-maximized"],
                )
            except Exception:
                _dbg(f"channel '{channel}' not found — using bundled Chromium")
                self._browser = self._pw.chromium.launch(
                    headless=headless,
                    args=["--start-maximized"],
                )
            self._context = self._browser.new_context(no_viewport=True)
            self._page = self._context.new_page()
            _dbg("browser started")
            return True
        except Exception as e:
            _dbg(f"start failed: {e}")
            return False

    def stop(self):
        """Close the browser and release resources."""
        try:
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
        except Exception:
            pass
        self._pw = self._browser = self._context = self._page = None
        _dbg("browser stopped")

    def restart(self) -> bool:
        self.stop()
        return self.start()

    def _ensure(self) -> bool:
        """Make sure browser is running; auto-start if not."""
        if self._page and not self._page.is_closed():
            return True
        return self.start()

    def _active_page(self):
        """Return the active page, preferring any newly-opened tabs."""
        if not self._context:
            return self._page
        pages = self._context.pages
        return pages[-1] if pages else self._page

    # ── navigation ────────────────────────────────────────────────────────────

    def navigate(self, url: str, wait_until: str = "domcontentloaded") -> bool:
        if not self._ensure():
            return False
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            self._active_page().goto(url, wait_until=wait_until, timeout=30_000)
            _dbg(f"navigated to {url}")
            return True
        except Exception as e:
            _dbg(f"navigate error: {e}")
            return False

    def go_back(self) -> bool:
        if not self._ensure():
            return False
        try:
            self._active_page().go_back(timeout=10_000)
            return True
        except Exception:
            return False

    def go_forward(self) -> bool:
        if not self._ensure():
            return False
        try:
            self._active_page().go_forward(timeout=10_000)
            return True
        except Exception:
            return False

    def current_url(self) -> str:
        if not self._ensure():
            return ""
        return self._active_page().url

    def new_tab(self, url: str = "") -> bool:
        if not self._ensure():
            return False
        try:
            page = self._context.new_page()
            self._page = page
            if url:
                return self.navigate(url)
            return True
        except Exception as e:
            _dbg(f"new_tab error: {e}")
            return False

    # ── clicking ──────────────────────────────────────────────────────────────

    def click(
        self,
        text: str = "",
        selector: str = "",
        role: str = "",
        placeholder: str = "",
        label: str = "",
        timeout: int = 8_000,
    ) -> bool:
        """
        Click an element. Resolution order:
          1. role + text  (e.g. role='button', text='Submit')
          2. visible text (exact then partial)
          3. CSS/XPath selector
          4. placeholder text
          5. label text
        """
        if not self._ensure():
            return False
        page = self._active_page()

        locators = []
        if role and text:
            locators.append(page.get_by_role(role, name=text))
        if text:
            locators.append(page.get_by_text(text, exact=True))
            locators.append(page.get_by_text(text, exact=False))
        if role and not text:
            locators.append(page.get_by_role(role))
        if selector:
            locators.append(page.locator(selector))
        if placeholder:
            locators.append(page.get_by_placeholder(placeholder))
        if label:
            locators.append(page.get_by_label(label))

        for loc in locators:
            try:
                loc.first.click(timeout=timeout)
                _dbg(f"clicked: text={text!r} role={role!r} selector={selector!r}")
                return True
            except Exception:
                continue

        _dbg(f"click failed — no element matched text={text!r} role={role!r} selector={selector!r}")
        return False

    def double_click(self, text: str = "", selector: str = "", timeout: int = 8_000) -> bool:
        if not self._ensure():
            return False
        page = self._active_page()
        locators = []
        if text:
            locators.append(page.get_by_text(text, exact=True))
            locators.append(page.get_by_text(text, exact=False))
        if selector:
            locators.append(page.locator(selector))
        for loc in locators:
            try:
                loc.first.dblclick(timeout=timeout)
                return True
            except Exception:
                continue
        return False

    # ── typing ────────────────────────────────────────────────────────────────

    def type_into(
        self,
        text: str,
        selector: str = "",
        placeholder: str = "",
        label: str = "",
        clear_first: bool = True,
        timeout: int = 8_000,
    ) -> bool:
        """Type text into an input field, identified by selector, placeholder, or label."""
        if not self._ensure():
            return False
        page = self._active_page()

        locators = []
        if selector:
            locators.append(page.locator(selector))
        if placeholder:
            locators.append(page.get_by_placeholder(placeholder))
        if label:
            locators.append(page.get_by_label(label))
        # Fallback: focused element
        locators.append(page.locator(":focus"))

        for loc in locators:
            try:
                el = loc.first
                el.wait_for(state="visible", timeout=timeout)
                if clear_first:
                    el.fill("")
                el.type(text, delay=30)
                _dbg(f"typed into selector={selector!r} placeholder={placeholder!r}")
                return True
            except Exception:
                continue

        # Last resort: type at whatever is focused
        try:
            page.keyboard.type(text, delay=30)
            return True
        except Exception as e:
            _dbg(f"type_into failed: {e}")
            return False

    def fill(self, text: str, selector: str = "", placeholder: str = "", label: str = "") -> bool:
        """Instantly fill an input (no per-keystroke delay). Good for long text."""
        if not self._ensure():
            return False
        page = self._active_page()
        locators = []
        if selector:
            locators.append(page.locator(selector))
        if placeholder:
            locators.append(page.get_by_placeholder(placeholder))
        if label:
            locators.append(page.get_by_label(label))
        for loc in locators:
            try:
                loc.first.fill(text, timeout=8_000)
                return True
            except Exception:
                continue
        return False

    def press_key(self, key: str) -> bool:
        """Press a keyboard key or combo (e.g. 'Enter', 'Control+a', 'Tab')."""
        if not self._ensure():
            return False
        try:
            self._active_page().keyboard.press(key)
            return True
        except Exception as e:
            _dbg(f"press_key error: {e}")
            return False

    # ── scrolling ─────────────────────────────────────────────────────────────

    def scroll(self, direction: str = "down", amount: int = 3) -> bool:
        if not self._ensure():
            return False
        try:
            delta = -amount * 100 if direction == "up" else amount * 100
            self._active_page().mouse.wheel(0, delta)
            return True
        except Exception as e:
            _dbg(f"scroll error: {e}")
            return False

    # ── reading / inspection ──────────────────────────────────────────────────

    def get_text(self, selector: str, timeout: int = 5_000) -> str:
        """Return the inner text of an element."""
        if not self._ensure():
            return ""
        try:
            return self._active_page().locator(selector).first.inner_text(timeout=timeout)
        except Exception:
            return ""

    def get_page_title(self) -> str:
        if not self._ensure():
            return ""
        try:
            return self._active_page().title()
        except Exception:
            return ""

    def wait_for(self, selector: str, timeout: int = 10_000) -> bool:
        """Wait until a selector is visible."""
        if not self._ensure():
            return False
        try:
            self._active_page().locator(selector).first.wait_for(
                state="visible", timeout=timeout
            )
            return True
        except Exception:
            return False

    def screenshot_b64(self) -> str:
        """Return a base64 JPEG screenshot of the current page."""
        if not self._ensure():
            return ""
        try:
            png = self._active_page().screenshot(type="jpeg", quality=80)
            return base64.b64encode(png).decode()
        except Exception:
            return ""

    # ── execute_action dispatcher ─────────────────────────────────────────────

    def execute_action(self, action: dict) -> str:
        """
        Execute a structured browser action dict from Claude.
        Mirrors ArtyHands.execute_action for browser-specific action types.

        Supported action types and their params:
          browser_navigate  : {url}
          browser_click     : {text?, selector?, role?, placeholder?, label?}
          browser_type      : {text, selector?, placeholder?, label?, clear?}
          browser_fill      : {text, selector?, placeholder?, label?}
          browser_press     : {key}
          browser_scroll    : {direction?, amount?}
          browser_back      : {}
          browser_forward   : {}
          browser_new_tab   : {url?}
          browser_close     : {}
          browser_wait      : {selector?, seconds?}
        """
        atype = action.get("action", "")
        params = action.get("params", {})
        narration = action.get("narration", f"Browser: {atype}")

        if atype == "browser_navigate":
            ok = self.navigate(params.get("url", ""))
            if ok:
                narration = f"Navigated to {params.get('url')}"
            else:
                narration = f"Failed to navigate to {params.get('url')}"

        elif atype == "browser_click":
            ok = self.click(
                text=params.get("text", ""),
                selector=params.get("selector", ""),
                role=params.get("role", ""),
                placeholder=params.get("placeholder", ""),
                label=params.get("label", ""),
            )
            if not ok:
                narration = f"Couldn't find element to click: {params}"

        elif atype == "browser_type":
            ok = self.type_into(
                text=params.get("text", ""),
                selector=params.get("selector", ""),
                placeholder=params.get("placeholder", ""),
                label=params.get("label", ""),
                clear_first=params.get("clear", True),
            )
            if not ok:
                narration = "Couldn't find input field to type into"

        elif atype == "browser_fill":
            ok = self.fill(
                text=params.get("text", ""),
                selector=params.get("selector", ""),
                placeholder=params.get("placeholder", ""),
                label=params.get("label", ""),
            )
            if not ok:
                narration = "Couldn't fill input field"

        elif atype == "browser_press":
            self.press_key(params.get("key", "Enter"))

        elif atype == "browser_scroll":
            self.scroll(
                direction=params.get("direction", "down"),
                amount=int(params.get("amount", 3)),
            )

        elif atype == "browser_back":
            self.go_back()

        elif atype == "browser_forward":
            self.go_forward()

        elif atype == "browser_new_tab":
            self.new_tab(params.get("url", ""))

        elif atype == "browser_close":
            self.stop()
            narration = "Browser closed"

        elif atype == "browser_wait":
            if params.get("selector"):
                self.wait_for(params["selector"], timeout=int(params.get("timeout", 10_000)))
            else:
                time.sleep(float(params.get("seconds", 1)))

        return narration
