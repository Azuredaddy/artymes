"""
Artymes — ARTY AI Employee
Phase 2: Eyes & Hands (screen capture + computer control + training)
"""

import os
import sys
import uuid
import random
import re
import threading
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
    r'copy|paste|select all|undo|redo|save|create a new|make a new|'
    r'write|put|add|insert|place|drag|fill in|drop|'
    r'type in|write in|put in|add to|write on|write into)\b',
    re.IGNORECASE
)

def _is_computer_action(text: str) -> bool:
    """True if the user is asking ARTY to do something on the computer."""
    return bool(_ACTION_RE.search(text))

COMMANDS = {
    "/help":    "Show this help",
    "/tasks":   "Show open tasks ARTY has flagged",
    "/tickets": "Check Autotask for open tickets",
    "/ticket":  "Work on a specific ticket: /ticket <ticket-id>",
    "/train":   "Enter training mode — teach ARTY a task",
    "/watch":   "Observation mode — ARTY watches & logs to Notepad: /watch [minutes]",
    "/recall":  "List all procedures ARTY has learned",
    "/do":      "Run a saved procedure: /do <name>",
    "/type":    "Type instead of using the mic this session",
    "/mic":     "Switch back to mic input",
    "/version": "Show ARTY version and check for updates",
    "/test":    "Test typing: /test <app title> | <text to type>",
    "/quit":    "Shut down ARTY",
}

TRY_SIGNALS = {
    "your turn", "you try", "have a go", "try it", "give it a go",
    "now you", "off you go", "go for it", "go on then", "your time",
    "have a try", "try now", "give that a go", "you have a go",
    "can you try", "you do it", "try that", "go ahead",
}
CONFIRM_SIGNALS = {
    "yeah", "yes", "yep", "sure", "go on", "go ahead", "try again",
    "have another go", "try it again", "give it another go", "alright",
    "ok", "okay", "please", "do it", "crack on",
    "try once more", "one more time", "once more", "another go",
    "again", "retry", "try once", "try one more", "have a go again",
    "while more time", "more time", "try more", "give it another",
}
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
    t = text.lower().strip().strip(".,!? ")
    return any(t == s or t.endswith(s) or s in t for s in signals)


WATCH_STOP_SIGNALS = {
    "stop watching", "stop observation", "stop observe", "exit watch",
    "done watching", "end watch", "finish watching", "stop now",
}


def observe_mode(trainer, voice, use_mic, ears, duration_min: int = 60):
    console.print(f"\n[cyan bold]  ── OBSERVE MODE ({duration_min} min) ──[/cyan bold]")
    console.print("[dim]  ARTY will watch your screen and log notes to Notepad.[/dim]")
    console.print("[dim]  Say 'stop watching' at any time to end early.[/dim]\n")

    session = trainer.start_observe(duration_min)

    msg = (
        f"Going into watch mode for up to {duration_min} minutes. "
        "I'll log what I see quietly in the background — no windows will pop up. "
        "Say 'stop watching' whenever you're done."
    )
    console.print(f"  [green]ARTY:[/green] {msg}")
    voice.speak(msg)

    session.open_notepad()  # creates the log file, no UI

    obs_thread = threading.Thread(target=session.run, daemon=True)
    obs_thread.start()

    while not session._stop.is_set():
        console.print("  [dim cyan]  [ Listening... say 'stop watching' to end ][/dim cyan]")
        user_input = _get_input(use_mic, ears)
        if not user_input:
            continue
        lower = user_input.lower().strip()
        if any(s in lower for s in WATCH_STOP_SIGNALS):
            session.stop()
            break
        # User said something — log it as a note
        session._write_note(f"  [You: {user_input}]")
        ack = "Noted that."
        console.print(f"  [green]ARTY:[/green] {ack}")
        voice.speak(ack)

    obs_thread.join(timeout=5)
    count = len(session.observations)
    done_msg = f"Done watching. Logged {count} observation{'s' if count != 1 else ''} to Notepad."
    console.print(f"\n  [green]ARTY:[/green] {done_msg}")
    voice.speak(done_msg)


def training_mode(trainer, brain, voice, use_mic, ears):
    from brain.personality import (
        ARTY_TRAINING_WATCH_PHRASES,
        ARTY_TRAINING_TRY_PHRASES,
        ARTY_TRAINING_SUCCESS_PHRASES,
        ARTY_TRAINING_FAIL_PHRASES,
    )

    console.print("\n[yellow bold]  ── TRAINING MODE ──[/yellow bold]")
    console.print("[dim]  Narrate each step as you do it. Say 'your turn' when you want ARTY to try.[/dim]")
    console.print("[dim]  Say 'save that' to save the procedure. Say 'exit training' to leave.[/dim]\n")

    # Get topic — keep asking until we get something or user explicitly quits
    topic = ""
    for _ in range(3):
        prompt = "What task are we working on today?" if not topic else "Didn't catch that — what's the task?"
        console.print(f"  [green]ARTY:[/green] {prompt}")
        voice.speak(prompt)
        console.print("  [dim cyan]  [ Listening for task name... ][/dim cyan]")
        topic = _get_input(use_mic, ears)
        if topic:
            break

    if not topic or _is_signal(topic, EXIT_SIGNALS):
        voice.speak("No problem, maybe another time.")
        return

    session = trainer.start(topic)
    msg = f"Got it — {topic}. Walk me through it. Narrate what you're doing as you go, and I'll watch and take notes. Say 'your turn' when you're ready for me to have a go."
    console.print(f"  [green]ARTY:[/green] {msg}")
    voice.speak(msg)

    while True:
        try:
            console.print("  [dim cyan]  [ Listening... ][/dim cyan]")
            user_input = _get_input(use_mic, ears)
            if not user_input:
                continue

            lower = user_input.lower().strip()

            if _is_signal(lower, EXIT_SIGNALS):
                voice.speak("Leaving training mode.")
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
                if success:
                    result_msg = random.choice(ARTY_TRAINING_SUCCESS_PHRASES)
                else:
                    result_msg = random.choice(ARTY_TRAINING_FAIL_PHRASES)
                console.print(f"  [green]ARTY:[/green] {result_msg}")
                voice.speak(result_msg)
                # After trying, ask if they want to save
                if success:
                    save_prompt = "Want me to save that so I remember it next time?"
                    console.print(f"  [green]ARTY:[/green] {save_prompt}")
                    voice.speak(save_prompt)
                    console.print("  [dim cyan]  [ Listening... ][/dim cyan]")
                    save_reply = _get_input(use_mic, ears)
                    if save_reply and any(w in save_reply.lower() for w in ["yes", "yeah", "sure", "yep", "go on", "save"]):
                        brain.memory.save_procedure(topic, session.to_record()["steps"])
                        voice.speak(f"Saved. I've got {topic} locked in.")
                        break

            else:
                # User narrating a step
                session.record_step(user_input)
                ack = random.choice(ARTY_TRAINING_WATCH_PHRASES)
                console.print(f"  [green]ARTY:[/green] {ack}")
                voice.speak(ack)

        except KeyboardInterrupt:
            voice.speak("Training interrupted.")
            break


def _show_tickets(ticket_brain, voice):
    """Fetch and display open Autotask tickets."""
    console.print("  [dim]Checking Autotask...[/dim]")
    try:
        at      = ticket_brain._get_autotask()
        tickets = at.get_open_tickets(max_results=15)
    except Exception as e:
        msg = f"Couldn't reach Autotask: {e}"
        console.print(f"  [red]{msg}[/red]")
        voice.speak("I couldn't connect to Autotask — check the API credentials.")
        return

    if not tickets:
        msg = "No open tickets in the queue right now."
        console.print(f"  [green]ARTY:[/green] {msg}")
        voice.speak(msg)
        return

    rows = []
    for t in tickets:
        company = at.get_company_name(t.get("companyID", 0))
        rows.append(
            f"  [cyan]#{t.get('ticketNumber', t['id'])}[/cyan]  "
            f"[white]{t.get('title','')[:55]}[/white]  "
            f"[dim]({company})[/dim]"
        )
    console.print(Panel(
        "\n".join(rows),
        title=f"[bold yellow]Open Tickets ({len(tickets)})[/bold yellow]",
        border_style="yellow",
    ))
    voice.speak(f"I can see {len(tickets)} open ticket{'s' if len(tickets) != 1 else ''}. "
                "Use /ticket and the ID to work on one.")


def _work_ticket_by_id(ticket_id: int, ticket_brain, voice, use_mic, ears):
    """Load a ticket by ID, classify it, and walk the user through it."""
    console.print(f"  [dim]Loading ticket {ticket_id}...[/dim]")
    try:
        at     = ticket_brain._get_autotask()
        ticket = at.get_ticket(ticket_id)
    except Exception as e:
        console.print(f"  [red]Couldn't load ticket {ticket_id}: {e}[/red]")
        voice.speak(f"I couldn't load ticket {ticket_id}.")
        return

    if not ticket:
        voice.speak(f"Ticket {ticket_id} not found.")
        return

    plan = ticket_brain.classify_and_plan(ticket)
    ticket_brain.announce_ticket(plan)

    console.print("\n  [dim cyan]  Ready to start? (yes / no)[/dim cyan]")
    reply = _get_input(use_mic, ears)
    if not reply or not any(w in reply.lower() for w in
                            ["yes", "yeah", "yep", "go", "sure", "ok", "start", "ready"]):
        voice.speak("No problem — ticket is still open whenever you want to come back to it.")
        return

    ticket_brain.start_ticket(plan)

    # Step-by-step walkthrough — ARTY reads each step aloud and waits for confirmation
    steps = plan["procedure"]["steps"]
    for i, step in enumerate(steps, 1):
        console.print(f"\n  [bold yellow]Step {i}/{len(steps)}:[/bold yellow] {step}")
        voice.speak(f"Step {i}: {step}")

        console.print("  [dim cyan]  Done with this step? (yes / skip / stop)[/dim cyan]")
        reply = _get_input(use_mic, ears)
        if not reply:
            continue
        lower = reply.lower()
        if any(w in lower for w in ["stop", "cancel", "abort", "quit"]):
            voice.speak("Stopping. The ticket is still marked in progress.")
            return
        if any(w in lower for w in ["skip"]):
            voice.speak("Skipping that step.")
            continue
        # User said done / yes / etc — move to next step

    # All steps done — ask for closing note
    console.print("\n  [bold green]All steps complete.[/bold green]")
    voice.speak("All done. What should I put in the closing note?")
    console.print("  [dim cyan]  Closing note (or press Enter for default):[/dim cyan]")
    closing = _get_input(use_mic, ears)
    if not closing:
        closing = f"Resolved by ARTY — {plan['procedure']['name']} completed."

    ticket_brain.close_ticket(plan, closing)


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

    # Ticket brain — lazy-loads Autotask client on first use
    from brain.ticket_brain import ArtyTicketBrain
    ticket_brain = ArtyTicketBrain(voice=voice)

    session_id = str(uuid.uuid4())
    brain.set_session(session_id)

    from hands.control import _HAS_WINCTRL, _HAS_GW, _HAS_CLIPBOARD
    monitor_count = eyes.get_monitor_count()
    win32_status = "[green]win32 ready[/green]" if _HAS_WINCTRL else "[yellow]win32 unavailable — pywin32 not installed[/yellow]"
    debug_status = "  [magenta]DEBUG ON[/magenta]" if os.environ.get("ARTY_DEBUG") == "1" else ""
    console.print(f"[bold green]ARTY is online.[/bold green]  Session: {session_id[:8]}  Monitors: {monitor_count}  {win32_status}{debug_status}\n")
    console.print(f"  [green]ARTY:[/green] {ARTY_GREETING}")
    voice.speak(ARTY_GREETING)

    use_mic = True
    last_action_goal = None

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
                elif cmd.startswith("/watch"):
                    arg = cmd[6:].strip()
                    try:
                        mins = int(arg) if arg else 60
                    except ValueError:
                        mins = 60
                    observe_mode(trainer, voice, use_mic, ears, duration_min=mins)
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
                elif cmd == "/tickets":
                    _show_tickets(ticket_brain, voice)
                elif cmd.startswith("/ticket"):
                    arg = cmd[7:].strip()
                    if arg.isdigit():
                        _work_ticket_by_id(int(arg), ticket_brain, voice, use_mic, ears)
                    else:
                        console.print("  [red]Usage: /ticket <ticket-id>[/red]")
                elif cmd == "/version":
                    show_version(ARTY_VERSION, GITHUB_VERSION_URL, voice)
                elif cmd.startswith("/test"):
                    # /test <app title> | <text>
                    arg = user_input[5:].strip()
                    if "|" in arg:
                        app_title, test_text = arg.split("|", 1)
                        app_title, test_text = app_title.strip(), test_text.strip()
                    else:
                        app_title = arg.strip() or "Notepad"
                        test_text = "ARTY test"
                    console.print(f"\n  [yellow]── /test ──[/yellow]")
                    console.print(f"  Target app : [cyan]{app_title}[/cyan]")
                    console.print(f"  Text       : [cyan]{test_text}[/cyan]")
                    # Show visible windows for title matching help
                    wins = hands.list_windows()
                    matches = [w for w in wins if app_title.lower() in w.lower()]
                    console.print(f"  Windows matching '{app_title}': {matches or '[none — check title]'}")
                    # Try SendInput directly
                    from hands.win_control import sendinput_type_into, wm_char_type_into
                    console.print("  [dim]Trying SendInput...[/dim]")
                    ok1 = sendinput_type_into(app_title, test_text, new_line_first=True)
                    console.print(f"  SendInput: {'[green]OK[/green]' if ok1 else '[red]FAILED[/red]'}")
                    if not ok1:
                        console.print("  [dim]Trying WM_CHAR...[/dim]")
                        ok2 = wm_char_type_into(app_title, test_text, new_line_first=True)
                        console.print(f"  WM_CHAR  : {'[green]OK[/green]' if ok2 else '[red]FAILED[/red]'}")
                    if not ok1:
                        console.print("  [dim]Trying clipboard paste fallback...[/dim]")
                        focused = hands.click_into_window(app_title)
                        console.print(f"  Focus    : {'[green]OK[/green]' if focused else '[red]FAILED — window not found[/red]'}")
                        if focused:
                            import pyperclip, pyautogui
                            pyperclip.copy(test_text)
                            time.sleep(0.3)
                            pyautogui.hotkey("ctrl", "v")
                            console.print("  Clipboard: [green]pasted[/green]")
                elif cmd == "/type":
                    use_mic = False
                    console.print("  [dim]Switched to keyboard input.[/dim]")
                elif cmd == "/mic":
                    use_mic = True
                    console.print("  [dim]Switched to mic input.[/dim]")
                continue

            console.print(f"\n  [bold white]You:[/bold white] {user_input}")

            _debug_mode = os.environ.get("ARTY_DEBUG", "0") == "1"
            if _debug_mode:
                console.print(f"  [dim cyan][ROUTE] checking: '{user_input[:60]}'[/dim cyan]")
                console.print(f"  [dim cyan][ROUTE] is_action={_is_computer_action(user_input)}  last_goal={bool(last_action_goal)}[/dim cyan]")

            if _is_computer_action(user_input):
                last_action_goal = user_input
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
                else:
                    last_action_goal = None
                continue

            # Retry last action on confirmation phrase
            if last_action_goal and _is_signal(user_input.lower(), CONFIRM_SIGNALS):
                ack = random.choice(["Right, trying again.", "On it, another go.", "Let me try that again."])
                console.print(f"  [green]ARTY:[/green] {ack}")
                voice.speak(ack)
                success = trainer.execute_task(last_action_goal)
                if success:
                    last_action_goal = None
                else:
                    reply = "Still struggling with that one. Want to go into training mode so you can show me?"
                    console.print(f"  [green]ARTY:[/green] {reply}")
                    voice.speak(reply)
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
