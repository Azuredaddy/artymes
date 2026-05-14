"""
Artymes — ARTY AI Employee
Phase 2: Eyes & Hands (screen capture + computer control + training)
"""

import os
import sys
import uuid
import random
import re
import requests
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from colorama import init as colorama_init

colorama_init()
console = Console()

_ACTION_RE = re.compile(
    r'\b(open|launch|start up|close|minimize|maximise|maximize|pull up|bring up|'
    r'type|click|press|scroll|go to|navigate to|search for|switch to|tab over|'
    r'copy|paste|select all|undo|redo|save|create a new|make a new)\b',
    re.IGNORECASE
)

def _is_computer_action(text: str) -> bool:
    """True if the user is asking ARTY to do something on the computer."""
    return bool(_ACTION_RE.search(text))

COMMANDS = {
    "/help":    "Show this help",
    "/tasks":   "Show open tasks ARTY has flagged",
    "/train":   "Enter training mode — teach ARTY a task",
    "/recall":  "List all procedures ARTY has learned",
    "/do":      "Run a saved procedure: /do <name>",
    "/type":    "Type instead of using the mic this session",
    "/mic":     "Switch back to mic input",
    "/version": "Show ARTY version and check for updates",
    "/quit":    "Shut down ARTY",
}

TRY_SIGNALS = {"your turn", "you try", "have a go", "try it", "give it a go", "now you", "off you go"}
SAVE_SIGNALS = {"save", "save that", "remember that", "save it", "keep that"}
EXIT_SIGNALS = {"exit training", "stop training", "end training", "done training", "leave training", "finish training"}


def make_banner(version: str) -> str:
    return f"""
 █████╗ ██████╗ ████████╗██╗   ██╗███╗   ███╗███████╗███████╗
██╔══██╗██╔══██╗╚══██╔══╝╚██╗ ██╔╝████╗ ████║██╔════╝██╔════╝
███████║██████╔╝   ██║    ╚████╔╝ ██╔████╔██║█████╗  ███████╗
██╔══██║██╔══██╗   ██║     ╚██╔╝  ██║╚██╔╝██║██╔══╝  ╚════██║
██║  ██║██║  ██║   ██║      ██║   ██║ ╚═╝ ██║███████╗███████║
╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝      ╚═╝   ╚═╝     ╚═╝╚══════╝╚══════╝
        Project Artymes — ARTY AI Employee  v{version}
"""


def check_for_update(current_version: str, url: str) -> str | None:
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            latest = r.text.strip()
            if latest != current_version:
                return latest
    except Exception:
        pass
    return None


def print_banner(version: str):
    console.print(Panel(make_banner(version), style="bold cyan", expand=False))
    console.print()


def print_help():
    console.print(Panel(
        "\n".join(f"  [cyan]{k}[/cyan]  {v}" for k, v in COMMANDS.items()),
        title="ARTY Commands", style="dim"
    ))


def show_version(version: str, update_url: str, voice):
    console.print(f"\n  [green]ARTY:[/green] I'm on version [cyan]{version}[/cyan]. Checking for updates...")
    voice.speak(f"I'm on version {version}. Checking for updates.")
    latest = check_for_update(version, update_url)
    if latest:
        msg = f"There's a newer version {latest} available. Run the installer to update."
        console.print(f"  [yellow]Update available: v{latest}[/yellow]")
    else:
        msg = "I'm fully up to date. Nice."
        console.print("  [green]Up to date.[/green]")
    voice.speak(msg)


def show_tasks(brain, voice):
    tasks = brain.get_tasks()
    if not tasks:
        msg = "No open tasks right now. Clean slate."
        console.print(f"\n  [green]ARTY:[/green] {msg}")
        voice.speak(msg)
        return
    console.print(Panel(
        "\n".join(f"  [{t['id']}] {t['title']} (confidence: {t['confidence']:.0%})" for t in tasks),
        title="Open Tasks", style="yellow"
    ))


def show_procedures(trainer, voice):
    procs = trainer.list_procedures()
    if not procs:
        msg = "I haven't learned any procedures yet. Teach me something!"
        console.print(f"\n  [green]ARTY:[/green] {msg}")
        voice.speak(msg)
        return
    console.print(Panel(
        "\n".join(f"  • {p['name']}" for p in procs),
        title="Learned Procedures", style="green"
    ))
    voice.speak(f"I know {len(procs)} procedure{'s' if len(procs) != 1 else ''}.")


def _get_input(use_mic, ears):
    if use_mic:
        return ears.listen()
    return input("\n  You > ").strip()


def _is_signal(text: str, signals: set) -> bool:
    t = text.lower().strip().rstrip(".")
    return any(t == s or t.endswith(s) for s in signals)


def training_mode(trainer, brain, voice, use_mic, ears):
    from brain.personality import (
        ARTY_TRAINING_WATCH_PHRASES,
        ARTY_TRAINING_TRY_PHRASES,
        ARTY_TRAINING_SUCCESS_PHRASES,
        ARTY_TRAINING_FAIL_PHRASES,
    )

    console.print("\n[yellow bold]  ── TRAINING MODE ──[/yellow bold]")
    console.print("[dim]  Say what you're doing as you do it. Say 'your turn' when ready for ARTY to try.[/dim]")
    console.print("[dim]  Say 'save that' to save, 'exit training' to leave.[/dim]\n")

    prompt = "What task are we working on today?"
    console.print(f"  [green]ARTY:[/green] {prompt}")
    voice.speak(prompt)

    topic = _get_input(use_mic, ears)
    if not topic or _is_signal(topic, EXIT_SIGNALS):
        voice.speak("No problem, maybe another time.")
        return

    session = trainer.start(topic)
    msg = f"Got it — {topic}. Walk me through it step by step, narrate as you go, and I'll watch. Say 'your turn' when you want me to try."
    console.print(f"  [green]ARTY:[/green] {msg}")
    voice.speak(msg)

    tried = False

    while True:
        try:
            user_input = _get_input(use_mic, ears)
            if not user_input:
                continue

            lower = user_input.lower().strip()

            if _is_signal(lower, EXIT_SIGNALS):
                voice.speak("Leaving training mode. Nice session.")
                break

            elif _is_signal(lower, SAVE_SIGNALS):
                session_record = session.to_record()
                brain.memory.save_procedure(session_record["topic"], session_record["steps"])
                msg = f"Saved. I'll remember how to {topic} from now on."
                console.print(f"  [green]ARTY:[/green] {msg}")
                voice.speak(msg)
                break

            elif _is_signal(lower, TRY_SIGNALS):
                phrase = random.choice(ARTY_TRAINING_TRY_PHRASES)
                console.print(f"  [green]ARTY:[/green] {phrase}")
                voice.speak(phrase)
                success = session.try_task()
                tried = True
                if success:
                    result_msg = random.choice(ARTY_TRAINING_SUCCESS_PHRASES)
                else:
                    result_msg = random.choice(ARTY_TRAINING_FAIL_PHRASES)
                console.print(f"  [green]ARTY:[/green] {result_msg}")
                voice.speak(result_msg)

            else:
                # User is narrating a step they're demonstrating
                session.record_step(user_input)
                ack = random.choice(ARTY_TRAINING_WATCH_PHRASES)
                console.print(f"  [green]ARTY:[/green] {ack}")
                voice.speak(ack)

        except KeyboardInterrupt:
            voice.speak("Training interrupted. Want to save what we covered?")
            break


def run():
    from config import ARTY_VERSION, GITHUB_VERSION_URL
    print_banner(ARTY_VERSION)

    console.print("[dim]Initialising ARTY brain...[/dim]")

    latest = check_for_update(ARTY_VERSION, GITHUB_VERSION_URL)
    if latest:
        console.print(f"  [yellow]Update available: v{latest} — run the installer to upgrade.[/yellow]\n")

    from config import ANTHROPIC_API_KEY, ENV_PATH
    if not ANTHROPIC_API_KEY or not ANTHROPIC_API_KEY.startswith("sk-"):
        console.print(Panel(
            "  [red]ANTHROPIC_API_KEY is missing.[/red]\n\n"
            f"  Looking for .env at:\n  [cyan]{ENV_PATH}[/cyan]\n\n"
            "  Open that file and paste your key from [cyan]console.anthropic.com[/cyan]\n"
            "  Save as UTF-8 [bold]without BOM[/bold] (use VS Code or Notepad++, not Notepad)",
            title="Setup Required", style="red"
        ))
        input("\nPress Enter to exit.")
        return

    from brain.claude_client import ArtyBrain
    from voice.stt import ArtyEars
    from voice.tts import ArtyVoice
    from eyes.screen import ArtyEyes
    from hands.control import ArtyHands
    from brain.trainer import ArtyTrainer
    from config import PUSH_TO_TALK, WAKE_WORD
    from brain.personality import ARTY_GREETING

    brain = ArtyBrain()
    ears = ArtyEars()
    voice = ArtyVoice()
    eyes = ArtyEyes()
    hands = ArtyHands()
    trainer = ArtyTrainer(eyes, hands, voice, brain.memory)

    session_id = str(uuid.uuid4())
    brain.set_session(session_id)

    monitor_count = eyes.get_monitor_count()
    console.print(f"[bold green]ARTY is online.[/bold green]  Session: {session_id[:8]}  Monitors: {monitor_count}\n")
    console.print(f"  [green]ARTY:[/green] {ARTY_GREETING}")
    voice.speak(ARTY_GREETING)

    use_mic = True

    while True:
        try:
            if use_mic:
                if not PUSH_TO_TALK:
                    user_input = ears.listen()
                else:
                    input("  [Press ENTER then speak]")
                    user_input = ears.listen()
            else:
                user_input = input("\n  You > ").strip()

            if not user_input:
                continue

            if user_input.lower().startswith("/"):
                cmd = user_input.lower().strip()
                if cmd == "/quit":
                    msg = "Shutting down. Later."
                    console.print(f"\n  [green]ARTY:[/green] {msg}")
                    voice.speak(msg)
                    break
                elif cmd == "/help":
                    print_help()
                elif cmd == "/tasks":
                    show_tasks(brain, voice)
                elif cmd == "/train":
                    training_mode(trainer, brain, voice, use_mic, ears)
                elif cmd == "/recall":
                    show_procedures(trainer, voice)
                elif cmd.startswith("/do "):
                    proc_name = cmd[4:].strip()
                    if not proc_name:
                        console.print("  [red]Usage: /do <procedure name>[/red]")
                    else:
                        voice.speak(f"Running procedure: {proc_name}")
                        success = trainer.run_procedure(proc_name)
                        if not success:
                            voice.speak(f"I don't have a procedure called {proc_name} — or it didn't work.")
                elif cmd == "/version":
                    show_version(ARTY_VERSION, GITHUB_VERSION_URL, voice)
                elif cmd == "/type":
                    use_mic = False
                    console.print("  [dim]Switched to keyboard input.[/dim]")
                elif cmd == "/mic":
                    use_mic = True
                    console.print("  [dim]Switched to mic input.[/dim]")
                continue

            console.print(f"\n  [bold white]You:[/bold white] {user_input}")

            if _is_computer_action(user_input):
                ack = random.choice(["On it.", "Sure, give me a sec.", "Right, on it.", "Yep, doing that now."])
                console.print(f"  [green]ARTY:[/green] {ack}")
                voice.speak(ack)
                success = trainer.execute_task(user_input)
                if not success:
                    offer = random.choice([
                        "I got stuck on that. Want to show me how and I'll learn it?",
                        "I couldn't crack that one. Want to walk me through it in training mode?",
                        "Hmm, that didn't go to plan. Want to teach me the right way?",
                    ])
                    console.print(f"  [green]ARTY:[/green] {offer}")
                    voice.speak(offer)
                    confirm = _get_input(use_mic, ears)
                    if confirm and any(w in confirm.lower() for w in ["yes", "yeah", "sure", "go on", "yep", "ok", "alright"]):
                        training_mode(trainer, brain, voice, use_mic, ears)
                continue

            reply, needs_help = brain.think_streaming(user_input, voice)
            console.print(f"  [green]ARTY:[/green] {reply}")

            if needs_help:
                task_id = brain.log_task(
                    title=user_input[:80],
                    description=f"ARTY flagged uncertainty on: {user_input}",
                    confidence=0.3
                )
                console.print(f"  [yellow][Task #{task_id} logged — ARTY needs help with this one][/yellow]")

        except KeyboardInterrupt:
            console.print("\n\n  [dim]Ctrl+C detected.[/dim]")
            msg = "Alright, I'll catch you later."
            console.print(f"  [green]ARTY:[/green] {msg}")
            voice.speak(msg)
            break
        except Exception as e:
            console.print(f"  [red]Error: {e}[/red]")
            continue


if __name__ == "__main__":
    run()
