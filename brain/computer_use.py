"""
ArtyComputerUse — Claude Computer Use API.
Captures all monitors combined so Claude sees the full desktop.
Uses win32api for mouse/keyboard actions (more reliable than pyautogui on Windows).
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

CU_BETA      = "computer-use-2025-01-24"
CU_TOOL_TYPE = "computer_20250124"

SYSTEM_PROMPT = """You are ARTY, an AI employee controlling a Windows computer.

SETUP: 3 monitors. The screenshot you receive shows ALL monitors side by side.
Many apps have visually identical buttons — always target the correct app window.

HOW TO WORK:
- Take a screenshot first to see the current state.
- Narrate briefly what you are doing (casual, first person, 1 sentence max).
- Prefer keyboard shortcuts over clicks where possible.
- After each action, take another screenshot to confirm it worked.
- For small buttons (plus, close, checkbox) click the exact centre — not near it.
- If a click doesn't work, try a slightly different coordinate.
- When the task is fully complete, say so clearly and stop using tools.

OUTLOOK EMAIL — exact sequence:
1. Click the Outlook window to focus it
2. Press Ctrl+N → new message window opens
3. Type recipient name/email in To field
4. Press Tab → Subject field
5. Type subject
6. Press Tab → Body
7. Type body text
8. Leave as draft — do NOT click Send unless told to

AUTOTASK — creating a ticket:
1. Click the + (plus) button in the Autotask toolbar
2. Click "New Ticket" or "Ticket" from the dropdown
3. Fill in Title, Company, etc.
4. Save the ticket"""


def _get_dpi_scale(eyes) -> float:
    """Return physical-to-logical scale factor for the primary monitor."""
    try:
        import pyautogui
        logical_w, _ = pyautogui.size()
        primary = next(
            (m for m in eyes.sct.monitors[1:] if m["left"] == 0 and m["top"] == 0),
            None,
        )
        if primary and logical_w > 0:
            return primary["width"] / logical_w
    except Exception:
        pass
    return 1.0


class ArtyComputerUse:
    def __init__(self, eyes, voice):
        from config import ANTHROPIC_API_KEY, COMPUTER_USE_MODEL
        self.eyes   = eyes
        self.voice  = voice
        self.model  = COMPUTER_USE_MODEL
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        # Virtual screen info — updated every screenshot
        self._phys_w    = 1920
        self._phys_h    = 1080
        self._phys_left = 0
        self._phys_top  = 0
        self._img_w     = 1366
        self._img_h     = 768
        self._dpi_scale = 1.0

    # ── screenshot ────────────────────────────────────────────────────────────

    def _take_screenshot(self) -> tuple:
        """Capture all monitors. Returns (b64, img_w, img_h). Updates internal state."""
        b64, img_w, img_h, phys_w, phys_h, phys_left, phys_top = \
            self.eyes.capture_all_native()
        self._phys_w    = phys_w
        self._phys_h    = phys_h
        self._phys_left = phys_left
        self._phys_top  = phys_top
        self._img_w     = img_w
        self._img_h     = img_h
        self._dpi_scale = _get_dpi_scale(self.eyes)
        return b64, img_w, img_h

    # ── coordinate conversion ─────────────────────────────────────────────────

    def _to_logical(self, x_img: float, y_img: float) -> tuple:
        """Image-pixel coordinates → logical screen coordinates (what win32api needs)."""
        x_phys = self._phys_left + x_img * (self._phys_w / self._img_w)
        y_phys = self._phys_top  + y_img * (self._phys_h / self._img_h)
        return int(x_phys / self._dpi_scale), int(y_phys / self._dpi_scale)

    # ── action executor ───────────────────────────────────────────────────────

    def _execute(self, action: str, params: dict):
        """Execute a Computer Use tool action via win32api (falls back to pyautogui)."""
        try:
            import win32api, win32con
            _win32 = True
        except ImportError:
            _win32 = False

        coord = params.get("coordinate", [0, 0])
        lx, ly = self._to_logical(coord[0], coord[1])

        console.print(f"  [dim]  → {action} logical=({lx},{ly})[/dim]")

        def _mouse_click(x, y, button="left", double=False):
            if _win32:
                win32api.SetCursorPos((x, y))
                time.sleep(0.06)
                if button == "right":
                    dn, up = win32con.MOUSEEVENTF_RIGHTDOWN, win32con.MOUSEEVENTF_RIGHTUP
                else:
                    dn, up = win32con.MOUSEEVENTF_LEFTDOWN, win32con.MOUSEEVENTF_LEFTUP
                win32api.mouse_event(dn, 0, 0)
                time.sleep(0.06)
                win32api.mouse_event(up, 0, 0)
                if double:
                    time.sleep(0.12)
                    win32api.mouse_event(dn, 0, 0)
                    time.sleep(0.06)
                    win32api.mouse_event(up, 0, 0)
            else:
                import pyautogui
                pyautogui.FAILSAFE = False
                if double:
                    pyautogui.doubleClick(x, y)
                elif button == "right":
                    pyautogui.rightClick(x, y)
                else:
                    pyautogui.click(x, y)

        if action == "left_click":
            _mouse_click(lx, ly)

        elif action == "right_click":
            _mouse_click(lx, ly, button="right")

        elif action == "middle_click":
            if _win32:
                win32api.SetCursorPos((lx, ly))
                time.sleep(0.06)
                win32api.mouse_event(win32con.MOUSEEVENTF_MIDDLEDOWN, 0, 0)
                time.sleep(0.06)
                win32api.mouse_event(win32con.MOUSEEVENTF_MIDDLEUP, 0, 0)

        elif action == "double_click":
            _mouse_click(lx, ly, double=True)

        elif action == "mouse_move":
            if _win32:
                win32api.SetCursorPos((lx, ly))
            else:
                import pyautogui
                pyautogui.FAILSAFE = False
                pyautogui.moveTo(lx, ly, duration=0.2)

        elif action == "left_click_drag":
            start = params.get("startCoordinate", [0, 0])
            slx, sly = self._to_logical(start[0], start[1])
            if _win32:
                win32api.SetCursorPos((slx, sly))
                time.sleep(0.06)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
                time.sleep(0.1)
                win32api.SetCursorPos((lx, ly))
                time.sleep(0.1)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
            else:
                import pyautogui
                pyautogui.FAILSAFE = False
                pyautogui.drag(slx, sly, lx - slx, ly - sly, duration=0.4, button="left")

        elif action == "key":
            keys  = params.get("text", "").replace("super", "win")
            parts = [k.strip() for k in keys.split("+")]
            import pyautogui
            pyautogui.FAILSAFE = False
            if len(parts) > 1:
                pyautogui.hotkey(*parts)
            else:
                pyautogui.press(keys)

        elif action == "type":
            text = params.get("text", "")
            try:
                import pyperclip
                pyperclip.copy(text)
                import pyautogui
                pyautogui.FAILSAFE = False
                pyautogui.hotkey("ctrl", "v")
            except Exception:
                import pyautogui
                pyautogui.FAILSAFE = False
                pyautogui.typewrite(text, interval=0.04)

        elif action == "scroll":
            direction = params.get("direction", "down")
            amount    = int(params.get("amount", 3))
            if _win32:
                win32api.SetCursorPos((lx, ly))
                scroll_val = amount * 120 if direction == "up" else -(amount * 120)
                win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, 0, 0, scroll_val)
            else:
                import pyautogui
                pyautogui.FAILSAFE = False
                pyautogui.scroll(amount if direction == "up" else -amount, x=lx, y=ly)

        elif action == "cursor_position":
            pass   # Claude is just querying position — nothing to do

    # ── main loop ─────────────────────────────────────────────────────────────

    def execute_task(self, goal: str, max_iterations: int = 30) -> bool:
        """Run a task using Claude Computer Use. Returns True on success."""
        b64, img_w, img_h = self._take_screenshot()

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
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                {"type": "text",  "text": initial_text},
            ],
        }]

        console.print(f"\n  [yellow]Computer Use: {goal[:80]}[/yellow]")

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
                    console.print("  [yellow]  → Set COMPUTER_USE_MODEL=claude-3-5-sonnet-20241022 in config.py[/yellow]")
                else:
                    console.print(f"  [red]Computer Use API error: {e}[/red]")
                return False
            except Exception as e:
                console.print(f"  [red]Computer Use error: {e}[/red]")
                return False

            messages.append({"role": "assistant", "content": response.content})

            # Print any narration
            for block in response.content:
                if hasattr(block, "text") and block.text.strip():
                    narration = block.text.strip()[:200]
                    console.print(f"  [green]ARTY:[/green] {narration}")
                    self.voice.speak(narration)

            if response.stop_reason == "end_turn":
                return any(hasattr(b, "type") and b.type == "tool_use"
                           for b in response.content)

            tool_results = []
            has_tool_call = False

            for block in response.content:
                if block.type != "tool_use" or block.name != "computer":
                    continue

                has_tool_call = True
                action = block.input.get("action", "")

                if action == "screenshot":
                    b64, img_w, img_h = self._take_screenshot()
                    tools[0]["display_width_px"]  = img_w
                    tools[0]["display_height_px"] = img_h
                else:
                    self._execute(action, block.input)
                    time.sleep(0.8)
                    b64, img_w, img_h = self._take_screenshot()
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

        self.voice.speak("I hit my step limit on that one.")
        return False
