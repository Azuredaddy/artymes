"""
ArtyComputerUse — Claude Computer Use API integration.
Claude controls the screen directly via trained tool calls rather than
our custom vision→JSON→execute loop. Much smarter and more reliable.
Falls back gracefully if unavailable.
"""
import time
import anthropic
from rich.console import Console

try:
    from hands.win_control import get_active_window_context
except Exception:
    def get_active_window_context() -> str:
        return ""

console = Console()

CU_BETA        = "computer-use-2025-01-24"
CU_TOOL_TYPE   = "computer_20250124"
ZOOM_REFINE    = True   # Two-pass zoom on every click for small-icon precision
ZOOM_RADIUS    = 200    # Logical pixels around click point to zoom into

SYSTEM_PROMPT = """You are ARTY, an AI employee controlling a Windows computer for your trainer.

SETUP: The user has 3 monitors running multiple apps simultaneously (Chrome, 8x8, Outlook, Teams, etc.).
Many apps have visually identical buttons in the same screen position (e.g. every app has an X close button).
ALWAYS target the correct app window — never click a button that belongs to the wrong application.

BROWSER TASKS: If the task involves a web browser (Chrome, Edge, etc.), prefer browser_* actions over
pixel clicks — they target elements by text/role so they never miss due to DPI or window position:
  browser_navigate {url}                       — go to a URL
  browser_click {text?, role?, selector?}      — click by visible text or ARIA role
  browser_type {text, placeholder?, label?}    — type into an input
  browser_fill {text, selector?}               — instantly fill an input
  browser_press {key}                          — e.g. "Enter", "Tab", "Control+a"
  browser_scroll {direction, amount}           — scroll the page
  browser_back / browser_forward               — history navigation
  browser_new_tab {url?}                       — open a new tab

HOW TO WORK:
- Complete tasks efficiently. Narrate briefly what you're doing (casual, first person).
- For browser tasks, use browser_* actions first — they are far more reliable than pixel clicks.
- Prefer keyboard shortcuts over mouse clicks for desktop apps.
- After each action, wait for the screenshot to confirm it worked before continuing.
- For small icons (plus buttons, close buttons, checkboxes) be very precise with coordinates.
  Click the exact centre of the icon — not near it.
- If a click doesn't work, try a slightly different coordinate rather than repeating the same one.
- When the task is fully complete, say so and stop using tools."""


class ArtyComputerUse:
    def __init__(self, eyes, voice):
        from config import ANTHROPIC_API_KEY, COMPUTER_USE_MODEL
        self.eyes   = eyes
        self.voice  = voice
        self.model  = COMPUTER_USE_MODEL
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.x_scale = 1.0
        self.y_scale = 1.0

    # ── helpers ───────────────────────────────────────────────────────────────

    def _screenshot_with_scale(self) -> tuple:
        """Take a screenshot and update stored DPI scale factors.
        Returns (b64, img_w, img_h) ready for the Claude tools block."""
        b64, img_w, img_h, xs, ys = self.eyes.capture_primary_native()
        self.x_scale = xs
        self.y_scale = ys
        return b64, img_w, img_h

    def _to_logical(self, x: float, y: float) -> tuple:
        """Convert image-pixel coordinates (from Claude) → pyautogui logical coords."""
        return int(x * self.x_scale), int(y * self.y_scale)

    def _zoom_and_refine(self, rough_lx: int, rough_ly: int, hint: str) -> tuple:
        """Two-pass precision: zoom into the region and ask Claude for the exact spot.
        rough_lx/ly are already in logical coords. Returns refined (logical_x, logical_y)."""
        try:
            b64, zw, zh, rl, rt, rw, rh = self.eyes.capture_region_for_zoom(
                rough_lx, rough_ly, radius=ZOOM_RADIUS
            )
            refine_messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
                        },
                        {
                            "type": "text",
                            "text": (
                                f"This is a {zw}×{zh} zoomed view of the screen. "
                                f"I need to click: {hint}. "
                                "Reply with ONLY a JSON object: {\"x\": <int>, \"y\": <int>} "
                                "giving the exact pixel in THIS zoomed image to click. "
                                "No explanation, no markdown."
                            ),
                        },
                    ],
                }
            ]
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=64,
                messages=refine_messages,
            )
            import json, re
            raw = resp.content[0].text.strip()
            m = re.search(r'\{[^}]+\}', raw)
            if m:
                coords = json.loads(m.group())
                zx, zy = int(coords["x"]), int(coords["y"])
                refined_lx = int(rl + (zx / zw) * rw)
                refined_ly = int(rt + (zy / zh) * rh)
                console.print(
                    f"  [dim cyan]  zoom-refine: rough=({rough_lx},{rough_ly}) "
                    f"→ refined=({refined_lx},{refined_ly})[/dim cyan]"
                )
                return refined_lx, refined_ly
        except Exception as e:
            console.print(f"  [dim red]  zoom-refine failed ({e}), using rough coords[/dim red]")
        return rough_lx, rough_ly

    # ── main task loop ────────────────────────────────────────────────────────

    def execute_task(self, goal: str, max_iterations: int = 30) -> bool:
        """Run a task using Claude Computer Use. Returns True if completed."""
        import pyautogui

        b64, img_w, img_h = self._screenshot_with_scale()

        tools = [{
            "type": CU_TOOL_TYPE,
            "name": "computer",
            "display_width_px":  img_w,
            "display_height_px": img_h,
        }]

        win_ctx = get_active_window_context()
        initial_text = f"{win_ctx}\n{goal}" if win_ctx else goal

        messages = [{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
                },
                {"type": "text", "text": initial_text},
            ],
        }]

        console.print(f"\n  [yellow]ARTY (Computer Use): {goal[:80]}[/yellow]")

        for iteration in range(max_iterations):
            try:
                response = self.client.beta.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    system=SYSTEM_PROMPT,
                    tools=tools,
                    messages=messages,
                    betas=[CU_BETA],
                )
            except anthropic.BadRequestError as e:
                err = str(e)
                if "does not support tool types" in err or "computer_" in err:
                    console.print(f"  [red]Model '{self.model}' does not support Computer Use.[/red]")
                    console.print(f"  [yellow]  → Update COMPUTER_USE_MODEL in config.py to a supported model.[/yellow]")
                else:
                    console.print(f"  [red]Computer Use API error: {e}[/red]")
                return False
            except Exception as e:
                console.print(f"  [red]Computer Use error: {e}[/red]")
                return False

            messages.append({"role": "assistant", "content": response.content})

            for block in response.content:
                if hasattr(block, "text") and block.text.strip():
                    narration = block.text.strip()
                    console.print(f"  [green]ARTY:[/green] {narration[:200]}")
                    self.voice.speak(narration[:200])

            if response.stop_reason == "end_turn":
                did_something = any(
                    b.type == "tool_use" for b in messages[-1]["content"]
                    if hasattr(b, "type")
                )
                return did_something

            tool_results = []
            has_tool_call = False

            for block in response.content:
                if block.type != "tool_use" or block.name != "computer":
                    continue

                has_tool_call = True
                action = block.input.get("action", "")
                console.print(f"  [dim]  → CU {action} {dict(list(block.input.items())[:3])}[/dim]")

                if action == "screenshot":
                    b64, img_w, img_h = self._screenshot_with_scale()
                    tools[0]["display_width_px"]  = img_w
                    tools[0]["display_height_px"] = img_h
                    win_ctx = get_active_window_context()
                    content = [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                        *([{"type": "text", "text": win_ctx}] if win_ctx else []),
                    ]
                else:
                    self._execute(action, block.input, hint=goal)
                    time.sleep(0.7)
                    b64, img_w, img_h = self._screenshot_with_scale()
                    tools[0]["display_width_px"]  = img_w
                    tools[0]["display_height_px"] = img_h
                    win_ctx = get_active_window_context()
                    content = [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                        *([{"type": "text", "text": win_ctx}] if win_ctx else []),
                    ]

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": content,
                })

            if not has_tool_call:
                return True

            messages.append({"role": "user", "content": tool_results})

        self.voice.speak("I've hit my iteration limit on this one.")
        return False

    # ── action executor ───────────────────────────────────────────────────────

    def _execute(self, action: str, params: dict, hint: str = ""):
        """Translate Computer Use tool call into pyautogui actions.
        Applies DPI scale so image-pixel coords → pyautogui logical coords."""
        import pyautogui
        try:
            import pyperclip
            _clipboard = True
        except ImportError:
            _clipboard = False

        coord = params.get("coordinate", [0, 0])
        # Convert from image-pixel space → pyautogui logical-pixel space
        raw_x, raw_y = coord[0], coord[1]
        lx, ly = self._to_logical(raw_x, raw_y)

        is_click = action in ("left_click", "right_click", "middle_click", "double_click")

        if is_click and ZOOM_REFINE:
            lx, ly = self._zoom_and_refine(lx, ly, hint or action)

        if action == "left_click":
            pyautogui.click(lx, ly)
        elif action == "right_click":
            pyautogui.rightClick(lx, ly)
        elif action == "middle_click":
            pyautogui.middleClick(lx, ly)
        elif action == "double_click":
            pyautogui.doubleClick(lx, ly)
        elif action == "mouse_move":
            pyautogui.moveTo(lx, ly, duration=0.3)
        elif action == "left_click_drag":
            start = params.get("startCoordinate", [0, 0])
            slx, sly = self._to_logical(start[0], start[1])
            pyautogui.drag(slx, sly, lx - slx, ly - sly, duration=0.5, button="left")
        elif action == "key":
            keys  = params.get("text", "").replace("super", "win")
            parts = [k.strip() for k in keys.split("+")]
            if len(parts) > 1:
                pyautogui.hotkey(*parts)
            else:
                pyautogui.press(keys)
        elif action == "type":
            text = params.get("text", "")
            if _clipboard:
                pyperclip.copy(text)
                pyautogui.hotkey("ctrl", "v")
            else:
                pyautogui.typewrite(text, interval=0.05)
        elif action == "scroll":
            direction = params.get("direction", "down")
            amount    = int(params.get("amount", 3))
            scroll_val = amount if direction == "up" else -amount
            pyautogui.scroll(scroll_val, x=lx, y=ly)
        elif action == "cursor_position":
            pass
