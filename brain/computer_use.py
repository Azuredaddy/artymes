"""
ArtyComputerUse — Claude Computer Use API integration.
Claude controls the screen directly via trained tool calls rather than
our custom vision→JSON→execute loop. Much smarter and more reliable.
Falls back gracefully if unavailable.
"""
import time
import anthropic
from rich.console import Console

console = Console()

CU_BETA = "computer-use-2025-01-24"
CU_TOOL_TYPE = "computer_20250124"

SYSTEM_PROMPT = """You are ARTY, an AI employee controlling a Windows computer for your trainer.
Complete tasks efficiently. Narrate briefly what you're doing as you go (casual, first person).
Prefer keyboard shortcuts over mouse clicks where possible.
After each action, check the screenshot to confirm it worked before continuing.
When the task is fully complete, say so and stop using tools."""


class ArtyComputerUse:
    def __init__(self, eyes, voice):
        from config import ANTHROPIC_API_KEY, COMPUTER_USE_MODEL
        self.eyes = eyes
        self.voice = voice
        self.model = COMPUTER_USE_MODEL
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    def execute_task(self, goal: str, max_iterations: int = 30) -> bool:
        """Run a task using Claude Computer Use. Returns True if completed."""
        import pyautogui

        screenshot_b64, disp_w, disp_h = self.eyes.capture_primary_native()

        tools = [{
            "type": CU_TOOL_TYPE,
            "name": "computer",
            "display_width_px": disp_w,
            "display_height_px": disp_h,
        }]

        messages = [{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg", "data": screenshot_b64},
                },
                {"type": "text", "text": goal},
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
                console.print(f"  [red]Computer Use API error: {e}[/red]")
                return False
            except Exception as e:
                console.print(f"  [red]Computer Use error: {e}[/red]")
                return False

            messages.append({"role": "assistant", "content": response.content})

            # Speak any text narration Claude provides
            for block in response.content:
                if hasattr(block, "text") and block.text.strip():
                    narration = block.text.strip()
                    console.print(f"  [green]ARTY:[/green] {narration[:200]}")
                    self.voice.speak(narration[:200])

            if response.stop_reason == "end_turn":
                # Only count as success if we actually called tools — text-only responses
                # mean Claude narrated but didn't do anything
                did_something = any(
                    b.type == "tool_use" for b in messages[-1]["content"]
                    if hasattr(b, "type")
                )
                return did_something

            # Execute tool calls and feed results back
            tool_results = []
            has_tool_call = False

            for block in response.content:
                if block.type != "tool_use" or block.name != "computer":
                    continue

                has_tool_call = True
                action = block.input.get("action", "")
                console.print(f"  [dim]  → CU {action} {dict(list(block.input.items())[:3])}[/dim]")

                if action == "screenshot":
                    b64, _, _ = self.eyes.capture_primary_native()
                    content = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}}]
                else:
                    self._execute(action, block.input)
                    time.sleep(0.7)
                    b64, _, _ = self.eyes.capture_primary_native()
                    content = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}}]

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

    def _execute(self, action: str, params: dict):
        """Translate Computer Use tool call into pyautogui / clipboard actions."""
        import pyautogui
        try:
            import pyperclip
            _clipboard = True
        except ImportError:
            _clipboard = False

        coord = params.get("coordinate", [0, 0])
        x, y = int(coord[0]), int(coord[1])

        if action == "left_click":
            pyautogui.click(x, y)
        elif action == "right_click":
            pyautogui.rightClick(x, y)
        elif action == "middle_click":
            pyautogui.middleClick(x, y)
        elif action == "double_click":
            pyautogui.doubleClick(x, y)
        elif action == "mouse_move":
            pyautogui.moveTo(x, y, duration=0.3)
        elif action == "left_click_drag":
            start = params.get("startCoordinate", [0, 0])
            pyautogui.drag(start[0], start[1], x - start[0], y - start[1],
                           duration=0.5, button="left")
        elif action == "key":
            keys = params.get("text", "").replace("super", "win")
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
                pyautogui.typewrite(text, interval=0.04)
        elif action == "scroll":
            direction = params.get("direction", "down")
            amount = int(params.get("amount", 3))
            scroll_val = amount if direction == "up" else -amount
            pyautogui.scroll(scroll_val, x=x, y=y)
        elif action == "cursor_position":
            pass  # read-only, no execution needed
