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
  "thought": "brief note on what you see and why you're taking this action",
  "action": "click|double_click|right_click|move|type|press|hotkey|scroll|open|wait|done",
  "params": {},
  "narration": "what you say out loud as you do this (casual, first person)"
}

Params by action type:
- click / double_click / right_click / move: {"x": int, "y": int}
- type: {"text": "string to type"}
- press: {"key": "enter|tab|escape|backspace|delete|space|..."}
- hotkey: {"keys": ["win", "r"]}  or ["ctrl","c"] etc
- scroll: {"x": int, "y": int, "amount": int}  positive=up negative=down
- open: {"app": "notepad|calculator|chrome|..."}
- wait: {"seconds": float}
- done: {}  — use ONLY when the task is fully complete

Coordinates are real pixel positions. Click the CENTER of elements.
After each action you will receive a new screenshot showing current state."""

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

    def try_task(self, max_steps: int = 25) -> bool:
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

        for step_num in range(max_steps):
            screenshot_b64 = self.eyes.capture_all()

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
                                "text": f"Task: {task_desc}\n\nStep {step_num + 1} — what should I do?",
                            },
                        ],
                    }],
                )

                raw = response.content[0].text.strip()
                # Strip markdown fences if Claude adds them
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

            try:
                self.hands.execute_action(action)
                time.sleep(0.9)
            except Exception as e:
                console.print(f"  [red]Action failed: {e}[/red]")
                self.voice.speak(f"Ran into a problem — {str(e)[:60]}")
                return False

        self.voice.speak("I've hit my step limit. I'll need a bit more guidance on this one.")
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

    def run_procedure(self, name: str) -> bool:
        proc = self.memory.load_procedure(name)
        if not proc:
            return False
        session = TrainingSession(name, self.eyes, self.hands, self.voice)
        session.steps = [{"description": s["description"], "screenshot_b64": ""} for s in proc.get("steps", [])]
        return session.try_task()

    def list_procedures(self) -> list:
        return self.memory.list_procedures()
