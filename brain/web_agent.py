"""
WebAgent — Playwright browser + Claude vision for reliable web task execution.

Instead of screenshot→coordinates→pyautogui (fragile), this opens a dedicated
Playwright browser tab and lets Claude control it via DOM-level actions:
click by text, fill by label, press keys — no pixel coordinates at all.
"""
import json
import time
import anthropic
from rich.console import Console
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

console = Console()

# ── known web app URLs ────────────────────────────────────────────────────────

WEB_APPS = {
    "outlook":  "https://outlook.office.com/mail/",
    "email":    "https://outlook.office.com/mail/",
    "gmail":    "https://mail.google.com/",
    "teams":    "https://teams.microsoft.com/",
    "autotask": None,   # filled from config at runtime
    "ticket":   None,   # same
}

# Keywords that map a task to a web app
_TASK_ROUTES = [
    (["send email", "new email", "email to", "compose email", "write email"], "outlook"),
    (["outlook", "office mail"], "outlook"),
    (["gmail"], "gmail"),
    (["autotask", "ticket", "service desk", "create ticket", "new ticket"], "autotask"),
    (["teams", "chat", "teams message"], "teams"),
]


def _detect_app(goal: str) -> str | None:
    """Return the web app key for a given task goal, or None."""
    lower = goal.lower()
    for keywords, app in _TASK_ROUTES:
        if any(kw in lower for kw in keywords):
            return app
    return None


def _get_app_url(app: str) -> str | None:
    """Return the URL for a given app key, loading Autotask URL from config if needed."""
    if app in ("autotask", "ticket"):
        try:
            from config import AUTOTASK_ZONE_URL
            if AUTOTASK_ZONE_URL:
                return AUTOTASK_ZONE_URL
        except Exception:
            pass
        return None
    return WEB_APPS.get(app)


SYSTEM_PROMPT = """You are ARTY, an AI assistant controlling a web browser to complete tasks.
You see a screenshot of the current browser page. Complete the task using browser_* actions.

Respond ONLY with a JSON object — no markdown, no explanation:
{
  "thought": "brief note on what you see and what to do next",
  "action": "browser_navigate|browser_click|browser_type|browser_fill|browser_press|browser_scroll|browser_back|done",
  "params": {},
  "narration": "what you say out loud (casual, first person, max 15 words)"
}

ACTIONS:
  browser_navigate: {"url": "https://..."}
  browser_click:    {"text": "New message"}                    ← click by visible text (BEST)
                    {"role": "button", "text": "Submit"}       ← click by role + text
                    {"selector": "button.send"}                ← CSS selector (fallback)
                    {"placeholder": "Search people"}           ← click input by placeholder
  browser_type:     {"text": "hello", "placeholder": "To"}    ← type into input (per-keystroke)
  browser_fill:     {"text": "hello", "label": "Subject"}     ← instantly fill a field
  browser_press:    {"key": "Enter"}  or  {"key": "Tab"}
  browser_scroll:   {"direction": "down", "amount": 3}
  browser_back:     {}
  done:             {}  ← ONLY when task is fully complete

OUTLOOK WEB EMAIL — exact sequence:
1. browser_click {"text": "New mail"}  or  {"text": "New message"}
2. browser_type  {"text": "recipient name", "placeholder": "To"}
3. If an autocomplete suggestion appears → browser_click {"text": "Name <email>"}
4. browser_press {"key": "Tab"}   ← move to Subject
5. browser_type  {"text": "subject text", "placeholder": "Subject"}  or  browser_fill with label
6. browser_click on the body area, then browser_type the body text
7. done {}  ← leave as draft (do not click Send unless told to)

AUTOTASK — clicking the plus to create a ticket:
1. browser_click {"text": "+"}  or  {"role": "button", "text": "+"}
2. browser_click {"text": "Ticket"}
3. Fill in company, title etc. using browser_fill / browser_type
4. done {}

RULES:
- Prefer browser_click with visible text — it never misses due to layout changes
- After filling a form field, Tab to the next field or click it directly
- If a dropdown or autocomplete appears, click the correct option text
- Never repeat the exact same action twice — try a different selector or text
- Only return done when the task is actually complete"""


class WebAgent:
    """Playwright-based web task agent. Opens its own browser tab."""

    def __init__(self, voice=None):
        self.voice = voice
        self._client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self._browser = None   # lazy-init

    def _get_browser(self):
        """Return the shared BrowserHands instance, starting it if needed."""
        if self._browser is None:
            from hands.browser import BrowserHands, _HAS_PLAYWRIGHT
            if not _HAS_PLAYWRIGHT:
                return None
            self._browser = BrowserHands()
        if not self._browser._page or self._browser._page.is_closed():
            self._browser.start()
        return self._browser

    def can_handle(self, goal: str) -> bool:
        """Return True if this agent can handle the task."""
        return _detect_app(goal) is not None

    def execute_task(self, goal: str, max_steps: int = 20) -> bool:
        """
        Complete a web task using Playwright + Claude vision.
        Returns True if completed successfully.
        """
        browser = self._get_browser()
        if browser is None:
            console.print("  [red]WebAgent: Playwright not installed.[/red]")
            console.print("  [dim]Run: pip install playwright && python -m playwright install chromium[/dim]")
            return False

        # Detect which app we need
        app = _detect_app(goal)
        url = _get_app_url(app) if app else None

        console.print(f"\n  [cyan]WebAgent: {goal[:80]}[/cyan]")

        # Navigate to the target URL if we know it
        if url:
            console.print(f"  [dim]  → navigating to {url}[/dim]")
            browser.navigate(url)
            time.sleep(2)
        else:
            console.print(f"  [dim]  → no URL for '{app}' — working with current page[/dim]")

        action_history = []

        for step in range(max_steps):
            # Screenshot the browser page (not the whole screen)
            b64 = browser.screenshot_b64()
            if not b64:
                console.print("  [red]WebAgent: couldn't take browser screenshot[/red]")
                return False

            history_text = ""
            if action_history:
                history_text = "\n\nActions already taken (do NOT repeat):\n" + "\n".join(
                    f"  {i+1}. {a.get('narration', a.get('action', '?'))}"
                    for i, a in enumerate(action_history)
                )

            try:
                response = self._client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=300,
                    system=SYSTEM_PROMPT,
                    messages=[{
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
                            },
                            {
                                "type": "text",
                                "text": f"Task: {goal}{history_text}\n\nStep {step + 1} — what is the NEXT action?",
                            },
                        ],
                    }],
                )
                raw = response.content[0].text.strip()
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
                action = json.loads(raw)
            except Exception as e:
                console.print(f"  [red]WebAgent planning error: {e}[/red]")
                return False

            atype = action.get("action", "")
            narration = action.get("narration", "")
            params = action.get("params", {})

            if narration:
                console.print(f"  [green]ARTY:[/green] {narration}")
                if self.voice:
                    self.voice.speak(narration)

            if atype == "done":
                return True

            # Loop detection
            if len(action_history) >= 2:
                last2 = [a.get("action") for a in action_history[-2:]]
                if len(set(last2)) == 1 and last2[0] == atype:
                    console.print("  [yellow]WebAgent: going in circles — stopping.[/yellow]")
                    return False

            console.print(f"  [dim]  → {atype} {params}[/dim]")
            action_history.append(action)

            # Map action → BrowserHands call
            try:
                if atype == "browser_navigate":
                    browser.navigate(params.get("url", ""))
                    time.sleep(1.5)
                elif atype == "browser_click":
                    browser.click(
                        text=params.get("text", ""),
                        selector=params.get("selector", ""),
                        role=params.get("role", ""),
                        placeholder=params.get("placeholder", ""),
                        label=params.get("label", ""),
                    )
                    time.sleep(0.6)
                elif atype == "browser_type":
                    browser.type_into(
                        text=params.get("text", ""),
                        selector=params.get("selector", ""),
                        placeholder=params.get("placeholder", ""),
                        label=params.get("label", ""),
                    )
                    time.sleep(0.4)
                elif atype == "browser_fill":
                    browser.fill(
                        text=params.get("text", ""),
                        selector=params.get("selector", ""),
                        placeholder=params.get("placeholder", ""),
                        label=params.get("label", ""),
                    )
                    time.sleep(0.3)
                elif atype == "browser_press":
                    browser.press_key(params.get("key", "Tab"))
                    time.sleep(0.3)
                elif atype == "browser_scroll":
                    browser.scroll(
                        direction=params.get("direction", "down"),
                        amount=int(params.get("amount", 3)),
                    )
                elif atype == "browser_back":
                    browser.go_back()
                    time.sleep(1.0)
            except Exception as e:
                console.print(f"  [red]WebAgent action error: {e}[/red]")
                # Don't bail — let Claude see the result and adapt

        console.print("  [yellow]WebAgent: hit step limit.[/yellow]")
        return False
