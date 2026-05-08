"""
Artymes — ARTY AI Employee
Phase 1: Core Brain (voice I/O + Claude + memory)
"""

import os
import sys
import uuid
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from colorama import init as colorama_init

colorama_init()
console = Console()

BANNER = """
 █████╗ ██████╗ ████████╗██╗   ██╗███╗   ███╗███████╗███████╗
██╔══██╗██╔══██╗╚══██╔══╝╚██╗ ██╔╝████╗ ████║██╔════╝██╔════╝
███████║██████╔╝   ██║    ╚████╔╝ ██╔████╔██║█████╗  ███████╗
██╔══██║██╔══██╗   ██║     ╚██╔╝  ██║╚██╔╝██║██╔══╝  ╚════██║
██║  ██║██║  ██║   ██║      ██║   ██║ ╚═╝ ██║███████╗███████║
╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝      ╚═╝   ╚═╝     ╚═╝╚══════╝╚══════╝
           Project Artymes — ARTY AI Employee v1.0
"""

COMMANDS = {
    "/help":   "Show this help",
    "/tasks":  "Show open tasks ARTY has flagged",
    "/train":  "Enter training mode — teach ARTY something",
    "/type":   "Type instead of using the mic this session",
    "/mic":    "Switch back to mic input",
    "/quit":   "Shut down ARTY",
}


def print_banner():
    console.print(Panel(BANNER, style="bold cyan", expand=False))
    console.print()


def print_help():
    console.print(Panel(
        "\n".join(f"  [cyan]{k}[/cyan]  {v}" for k, v in COMMANDS.items()),
        title="ARTY Commands", style="dim"
    ))


def training_mode(brain, voice):
    console.print("\n[yellow]Training mode — type what you want to teach ARTY.[/yellow]")
    console.print("[dim]Format: TOPIC | CONTENT (e.g. 'refunds | Customer refunds go via the portal at...')[/dim]")
    raw = input("  Train > ").strip()
    if "|" in raw:
        topic, content = raw.split("|", 1)
        phrase = brain.learn(topic.strip(), content.strip(), source="manual_training")
        console.print(f"\n  [green]ARTY:[/green] {phrase}")
        voice.speak(phrase)
    else:
        console.print("  [red]Use format: TOPIC | CONTENT[/red]")


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


def run():
    print_banner()

    console.print("[dim]Initialising ARTY brain...[/dim]")
    from brain.claude_client import ArtyBrain
    from voice.stt import ArtyEars
    from voice.tts import ArtyVoice
    from config import PUSH_TO_TALK, WAKE_WORD
    from brain.personality import ARTY_GREETING

    brain = ArtyBrain()
    ears = ArtyEars()
    voice = ArtyVoice()

    session_id = str(uuid.uuid4())
    brain.set_session(session_id)

    use_mic = True
    console.print(f"[bold green]ARTY is online.[/bold green]  Session: {session_id[:8]}\n")
    console.print(f"  [green]ARTY:[/green] {ARTY_GREETING}")
    voice.speak(ARTY_GREETING)

    while True:
        try:
            # ── Get input ──────────────────────────────────────────────────────
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

            # ── Commands ───────────────────────────────────────────────────────
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
                    training_mode(brain, voice)
                elif cmd == "/type":
                    use_mic = False
                    console.print("  [dim]Switched to keyboard input.[/dim]")
                elif cmd == "/mic":
                    use_mic = True
                    console.print("  [dim]Switched to mic input.[/dim]")
                continue

            # ── Normal conversation ────────────────────────────────────────────
            console.print(f"\n  [bold white]You:[/bold white] {user_input}")
            reply, needs_help = brain.think(user_input)
            console.print(f"  [green]ARTY:[/green] {reply}")
            voice.speak(reply)

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
