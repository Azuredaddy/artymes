import json
import time
import random
from datetime import datetime
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from rich.console import Console

console = Console()

ACTION_SYSTEM_PROMPT = """You are ARTY, an AI assistant controlling a Windows computer. You are given a screenshot and a task to complete.

Respond ONLY with a JSON object — no markdown, no explanation, just raw JSON:
{
  "thought": "brief note on what you see and why",
  "action": "direct_type|focus_window|click|double_click|right_click|move|type|press|hotkey|scroll|open|wait|done",
  "params": {},
  "narration": "what you say out loud (casual, first person)"
}

MOST RELIABLE actions — prefer these:
- direct_type: {"app": "Notepad", "text": "money", "new_line": true}
  Types text directly into a named app window using Windows accessibility. No coordinates needed.
  new_line: true = press Enter first (to go to a new line). ALWAYS use this for typing text into apps.
- focus_window: {"title": "Notepad"}
  Brings named window to front and clicks into it.

Coordinate-based actions (use only when direct_type/focus_window aren't enough):
- click / double_click / right_click / move: {"x": int, "y": int}
- scroll: {"x": int, "y": int, "amount": int}

Other actions:
- type: {"text": "string"}  — types at current cursor (ONLY if window already focused)
- press: {"key": "enter|tab|escape|backspace|delete|space|home|end|ctrl+end|..."}
- hotkey: {"keys": ["ctrl", "s"]}
  Common browser hotkeys: new tab=["ctrl","t"], close tab=["ctrl","w"], new window=["ctrl","n"], refresh=["ctrl","r"], address bar=["ctrl","l"]
- open: {"app": "notepad|calculator|chrome|..."}
- wait: {"seconds": float}
- done: {}  — ONLY after you have actually performed all required actions in this session

Rules:
- For ANY typing task: use direct_type with the app name, NOT click + type
- Do NOT click near the top 40px of windows (title bar — will move/close window)
- Never repeat an action already listed in history
- NEVER return done on step 1 unless the task truly requires zero actions
- If the task says "open X", always open it even if X is already visible — a new instance may be needed
- Only return done after you have executed every step the user asked for"""

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

        for step_num in range(max_steps):
            screenshot_b64, x_scale, y_scale = self.eyes.capture_all_with_scale()

            # Build history text so Claude knows what's already been done
            history_text = ""
            if action_history:
                history_text = "\n\nActions already taken (do NOT repeat these):\n" + "\n".join(
                    f"  {i+1}. {a.get('narration', a.get('action', '?'))}"
                    for i, a in enumerate(action_history)
                )

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
                                "text": f"Task: {task_desc}{history_text}\n\nStep {step_num + 1} — what is the NEXT action?",
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

            # Loop detection — if the same action type repeats 3 times in a row, bail
            if len(action_history) >= 3:
                last3 = [a.get("action") for a in action_history[-3:]]
                if len(set(last3)) == 1 and last3[0] == atype:
                    console.print("  [yellow]ARTY: Looks like I'm going in circles.[/yellow]")
                    self.voice.speak("I seem to be going in circles on this one.")
                    return False

            # Scale coordinates from Claude's image space → real screen pixels
            params = action.get("params", {})
            if atype in ("click", "double_click", "right_click", "move") and "x" in params:
                params["x"] = int(params["x"] * x_scale)
                params["y"] = int(params["y"] * y_scale)
                action["params"] = params
            elif atype == "scroll" and "x" in params:
                params["x"] = int(params["x"] * x_scale)
                params["y"] = int(params["y"] * y_scale)
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
