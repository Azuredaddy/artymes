import json
import time
import random
import threading
from datetime import datetime
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from rich.console import Console

try:
    from hands.win_control import get_active_window_context
    _HAS_WIN_CTX = True
except Exception:
    _HAS_WIN_CTX = False
    def get_active_window_context() -> str:
        return ""

console = Console()

ACTION_SYSTEM_PROMPT = """You are ARTY, an AI assistant controlling a Windows computer. You are given a screenshot and a task to complete.

Respond ONLY with a JSON object — no markdown, no explanation, just raw JSON:
{
  "thought": "brief note on what you see and why",
  "action": "direct_type|focus_window|click|double_click|right_click|move|type|press|hotkey|scroll|open|wait|click_element|list_elements|browser_navigate|browser_click|browser_type|browser_fill|browser_press|browser_scroll|browser_back|browser_new_tab|done",
  "params": {},
  "narration": "what you say out loud (casual, first person)"
}

ENVIRONMENT: The user has 3 monitors with many apps open simultaneously (Chrome, Edge, 8x8, Outlook, Teams, etc.).
Many apps share visually identical buttons (e.g. every app has an X close button, a + button, etc.).
ALWAYS target the correct app by name — never guess coordinates when an element-based action exists.

━━━ WEB PAGE TASKS (anything inside a browser tab) ━━━
Use browser_* actions — they click by text/role, not coordinates, so they NEVER miss:

  browser_navigate: {"url": "https://example.com"}
  browser_click:    {"text": "New Ticket"}            ← click visible text on the page
  browser_click:    {"role": "button", "text": "Submit"}
  browser_click:    {"selector": "#create-btn"}       ← CSS selector fallback
  browser_type:     {"text": "hello", "placeholder": "Search..."}
  browser_fill:     {"text": "hello", "label": "Subject"}
  browser_press:    {"key": "Enter"}
  browser_scroll:   {"direction": "down", "amount": 3}
  browser_back:     {}
  browser_new_tab:  {"url": "https://example.com"}

CRITICAL: NEVER use list_elements or click_element on Edge/Chrome for web page content.
list_elements only sees the browser's own window controls (Back, Forward, address bar) —
it CANNOT see anything inside a web page. Use browser_click with the visible text instead.

━━━ DESKTOP APP TASKS (native Windows apps) ━━━
Use in this priority order:

1. click_element: {"app": "8x8", "element": "Create ticket", "element_type": "Button"}
   Clicks a named element via Windows Accessibility. No coordinates needed.
   USE THIS for desktop apps (8x8, Notepad, Teams, etc.) — NOT for web browser content.

2. list_elements: {"app": "8x8"}
   Lists desktop app UI elements. USE THIS only for native Windows apps, not browsers.

3. direct_type: {"app": "Notepad", "text": "hello", "new_line": true}
   Types into a named desktop app window. new_line: true = press Enter first.

4. focus_window: {"title": "Notepad"}
   Brings a window to front.

Coordinate-based (LAST RESORT — only if all above fail):
- click / double_click / right_click / move: {"x": int, "y": int}
- scroll: {"x": int, "y": int, "amount": int}

━━━ OTHER ACTIONS ━━━
- type: {"text": "string"}  — types at current cursor (window must already be focused)
- press: {"key": "enter|tab|escape|backspace|..."}
- hotkey: {"keys": ["ctrl", "s"], "window": "Outlook"}
  ALWAYS use window param for app-targeted hotkeys — never do focus_window + hotkey as two steps.
  Browser hotkeys: new tab=["ctrl","t"], close tab=["ctrl","w"], address bar=["ctrl","l"]
- close: {"title": "Edge"}
- open: {"app": "notepad|chrome|edge|outlook|..."}
- wait: {"seconds": float}
- done: {}  — ONLY after ALL required actions are complete

━━━ OUTLOOK SHORTCUTS ━━━
- New email:  hotkey {"keys": ["ctrl","n"], "window": "Outlook"}
- Reply:      hotkey {"keys": ["ctrl","r"], "window": "Outlook"}
- Send:       hotkey {"keys": ["ctrl","enter"], "window": "Message"}
- To field:   direct_type {"app": "Message", "text": "email@address"}
- Subject:    press tab, then direct_type {"app": "Message", "text": "subject"}
- Body:       press tab, then direct_type {"app": "Message", "text": "body"}

━━━ RULES ━━━
- Web content in browser → browser_* actions always
- Desktop apps → click_element / direct_type always
- Coordinate clicks → last resort only
- Never repeat focus_window for the same window
- Never click the top 40px of windows (title bar)
- Never repeat an action already in history
- Never return done on step 1 unless zero actions are genuinely needed
- Only return done after every requested step is complete"""

WATCH_PROMPTS = [
    "Got it.",
    "Noted.",
    "OK, I see that.",
    "Right, I'm watching.",
    "Yep, I've got that.",
    "Noted — keeping an eye on it.",
]


class TrainingSession:
    def __init__(self, topic: str, eyes, hands, voice):
        self.topic = topic
        self.eyes = eyes
        self.hands = hands
        self.voice = voice
        self.steps = []

    def record_step(self, description: str):
        """User narrated a step — capture current screen state."""
        screenshot = self.eyes.capture_all()
        self.steps.append({"description": description, "screenshot_b64": screenshot})
        console.print(f"  [dim]  ↳ Captured: {description}[/dim]")

    def try_task(self, max_steps: int = 15) -> bool:
        """ARTY attempts the task autonomously using vision + action loop."""
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        # Build task description from watched steps
        task_desc = self.topic
        if self.steps:
            step_lines = "\n".join(
                f"  Step {i+1}: {s['description']}"
                for i, s in enumerate(self.steps)
                if s['description']
            )
            task_desc = f"{self.topic}\n\nSteps I watched you do:\n{step_lines}"

        console.print(f"\n  [yellow]ARTY attempting: {self.topic}[/yellow]")

        action_history = []
        focus_target = None  # tracks last focused/typed-into app for per-monitor capture

        for step_num in range(max_steps):
            screenshot_b64, x_off, y_off, x_scale, y_scale = self.eyes.capture_with_focus(focus_target)

            # Build history text so Claude knows what's already been done
            history_text = ""
            if action_history:
                history_text = "\n\nActions already taken (do NOT repeat these):\n" + "\n".join(
                    f"  {i+1}. {a.get('narration', a.get('action', '?'))}"
                    for i, a in enumerate(action_history)
                )

            win_ctx = get_active_window_context()
            win_line = f"\n{win_ctx}" if win_ctx else ""
            if win_ctx:
                console.print(f"  [dim magenta]  {win_ctx}[/dim magenta]")

            try:
                response = client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=300,
                    system=ACTION_SYSTEM_PROMPT,
                    messages=[{
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": screenshot_b64,
                                },
                            },
                            {
                                "type": "text",
                                "text": f"{win_line}\nTask: {task_desc}{history_text}\n\nStep {step_num + 1} — what is the NEXT action?",
                            },
                        ],
                    }],
                )

                raw = response.content[0].text.strip()
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

                action = json.loads(raw)

            except Exception as e:
                console.print(f"  [red]Planning error (step {step_num + 1}): {e}[/red]")
                self.voice.speak("I hit a snag planning my next move.")
                return False

            narration = action.get("narration", "")
            atype = action.get("action", "")

            if narration:
                console.print(f"  [green]ARTY:[/green] {narration}")
                self.voice.speak(narration)

            if atype == "done":
                return True

            # Loop detection — if the same action type repeats 2 times in a row, bail
            if len(action_history) >= 2:
                last3 = [a.get("action") for a in action_history[-2:]]
                if len(set(last3)) == 1 and last3[0] == atype:
                    console.print("  [yellow]ARTY: Looks like I'm going in circles.[/yellow]")
                    self.voice.speak("I seem to be going in circles on this one.")
                    return False

            # Track focus target for per-monitor screenshot on next step
            params = action.get("params", {})
            if atype in ("focus_window", "close") and params.get("title"):
                focus_target = params["title"]
            elif atype == "direct_type" and params.get("app"):
                focus_target = params["app"]
            elif atype == "hotkey" and params.get("window"):
                focus_target = params["window"]

            # Scale coordinates: Claude's image coords → real screen pixels (+ monitor offset)
            if atype in ("click", "double_click", "right_click", "move") and "x" in params:
                params["x"] = int(params["x"] * x_scale) + x_off
                params["y"] = int(params["y"] * y_scale) + y_off
                action["params"] = params
            elif atype == "scroll" and "x" in params:
                params["x"] = int(params["x"] * x_scale) + x_off
                params["y"] = int(params["y"] * y_scale) + y_off
                action["params"] = params

            console.print(f"  [dim]  → {atype} {params}[/dim]")
            action_history.append(action)

            try:
                self.hands.execute_action(action)
                time.sleep(0.9)
            except Exception as e:
                console.print(f"  [red]Action failed: {e}[/red]")
                self.voice.speak(f"Ran into a problem — {str(e)[:60]}")
                return False

        self.voice.speak("I've used up my steps and I'm not done. I'll need some guidance.")
        return False

    def to_record(self) -> dict:
        return {
            "topic": self.topic,
            "steps": [{"description": s["description"]} for s in self.steps],
            "recorded_at": datetime.now().isoformat(),
        }


OBSERVE_SYSTEM_PROMPT = """You are ARTY, an AI learning a user's computer workflow by watching their screen.

Respond ONLY with valid JSON — no markdown, no extra text:
{"observation": "brief description of what you see", "question": "one useful question to learn the workflow, or null"}

Rules:
- observation: max 15 words, present tense
- question: max 20 words, only if genuinely useful; otherwise null
- If nothing has meaningfully changed, return {"observation": "screen unchanged", "question": null}"""


class ObserveSession:
    def __init__(self, duration_minutes: int, eyes, hands, voice, memory):
        self.duration_min = duration_minutes
        self.eyes = eyes
        self.hands = hands
        self.voice = voice
        self.memory = memory
        self._stop = threading.Event()
        self.observations = []
        self.interval_sec = 15
        self._client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        # Log file — silent, no windows opened
        import os
        log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        os.makedirs(log_dir, exist_ok=True)
        self.log_path = os.path.join(log_dir, f"observe_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")

    def stop(self):
        self._stop.set()

    def open_notepad(self):
        """Write the log file header — no windows opened, completely silent."""
        with open(self.log_path, "w", encoding="utf-8") as f:
            f.write(
                f"=== ARTY OBSERVATION LOG ===\n"
                f"Started: {datetime.now().strftime('%d %b %Y %H:%M')}\n"
                f"Duration: up to {self.duration_min} min\n"
                f"{'─' * 36}\n\n"
            )
        console.print(f"  [dim]  Logging to: {self.log_path}[/dim]")

    def _analyze(self, screenshot_b64: str) -> dict | None:
        try:
            resp = self._client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=150,
                system=OBSERVE_SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": screenshot_b64}},
                        {"type": "text", "text": "What is the user doing?"},
                    ],
                }],
            )
            raw = resp.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            return json.loads(raw)
        except Exception as e:
            console.print(f"  [dim red][Observe] analysis error: {e}[/dim red]")
            return None

    def _write_note(self, text: str):
        """Append a line to the log file silently — no window focus stolen."""
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(text + "\n")
        except Exception:
            pass

    @staticmethod
    def _screen_changed(prev_b64: str, curr_b64: str, threshold: float = 0.02) -> bool:
        """Quick pixel diff — returns True if screens differ by more than threshold fraction."""
        try:
            import base64, io
            from PIL import Image, ImageChops
            import numpy as np
            prev_img = Image.open(io.BytesIO(base64.b64decode(prev_b64))).convert("L").resize((160, 90))
            curr_img = Image.open(io.BytesIO(base64.b64decode(curr_b64))).convert("L").resize((160, 90))
            diff = np.array(ImageChops.difference(prev_img, curr_img), dtype=float)
            return (diff.mean() / 255) > threshold
        except Exception:
            return True  # assume changed if comparison fails

    def run(self):
        """Observation loop — checks for screen changes every 2s, only calls Claude when something changed."""
        start_time = time.time()
        prev_b64 = None
        cooldown = 0  # seconds remaining before next Claude call allowed

        while not self._stop.is_set():
            elapsed_sec = time.time() - start_time
            if elapsed_sec >= self.duration_min * 60:
                self._stop.set()
                break

            curr_b64 = self.eyes.capture_all()
            changed = prev_b64 is None or self._screen_changed(prev_b64, curr_b64)

            if changed and cooldown <= 0:
                result = self._analyze(curr_b64)
                if result:
                    obs = result.get("observation", "screen unchanged")
                    if obs != "screen unchanged":
                        ts = datetime.now().strftime("%H:%M:%S")
                        q = result.get("question")
                        line = f"[{ts}] {obs}"
                        if q:
                            line += f"\n  Q: {q}"
                        self._write_note(line)
                        self.observations.append(result)
                        console.print(f"  [dim cyan][Observe] {obs}[/dim cyan]")
                prev_b64 = curr_b64
                cooldown = 8  # wait at least 8s before next Claude call to avoid spamming

            # Poll every 2 seconds so fast actions (5s ticket close) get caught
            for _ in range(4):
                if self._stop.is_set():
                    break
                time.sleep(0.5)
            cooldown = max(0, cooldown - 2)

        elapsed_min = (time.time() - start_time) / 60
        self._write_note(
            f"\n{'─' * 36}\n"
            f"Session ended — {elapsed_min:.0f} min | {len(self.observations)} observations"
        )


class ArtyTrainer:
    def __init__(self, eyes, hands, voice, memory):
        self.eyes = eyes
        self.hands = hands
        self.voice = voice
        self.memory = memory

    def start(self, topic: str) -> TrainingSession:
        return TrainingSession(topic, self.eyes, self.hands, self.voice)

    def execute_task(self, goal: str) -> bool:
        """Run an ad-hoc computer task via the vision + action loop."""
        session = TrainingSession(goal, self.eyes, self.hands, self.voice)
        return session.try_task()

    def run_procedure(self, name: str) -> bool:
        proc = self.memory.load_procedure(name)
        if not proc:
            return False
        session = TrainingSession(name, self.eyes, self.hands, self.voice)
        session.steps = [{"description": s["description"], "screenshot_b64": ""} for s in proc.get("steps", [])]
        return session.try_task()

    def list_procedures(self) -> list:
        return self.memory.list_procedures()

    def start_observe(self, duration_minutes: int = 60) -> ObserveSession:
        return ObserveSession(duration_minutes, self.eyes, self.hands, self.voice, self.memory)
