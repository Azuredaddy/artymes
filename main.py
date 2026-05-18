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

# Stopwords that are never a company name
_NOT_COMPANY = {
    "me", "my", "the", "a", "an", "us", "our", "you", "your", "it", "its",
    "autotask", "ticket", "tickets", "this", "that", "them", "their",
    "one", "any", "all", "some", "there", "here", "now", "please", "i",
}

def _is_computer_action(text: str) -> bool:
    return bool(_ACTION_RE.search(text))

def _ticket_create_intent(text: str) -> str | None:
    """Detect 'create/make/open/add a ticket' intent. Returns company name or '' if no company."""
    lower = text.lower()
    if not re.search(r'\b(?:create|make|open|add|raise|log|new)\b.{0,20}\bticket\b', lower):
        return None
    # Try to extract company name
    name = _extract_company_name(text)
    return name or ""


def _autotask_intent(text: str) -> tuple[str, str]:
    """Classify Autotask-related intent.
    Returns (intent, value) where intent is one of:
      'list_companies', 'list_tickets', 'company_tickets', 'none'
    and value is the company name for 'company_tickets', else ''.
    Uses simple keyword matching — robust to natural language variation.
    """
    lower = text.lower()
    words = set(lower.split())

    has_autotask  = "autotask" in lower
    has_companies = "companies" in lower or "company" in lower or "clients" in lower or "client" in lower
    has_tickets   = "ticket" in lower or "tickets" in lower or "issues" in lower
    has_list      = any(w in lower for w in ("list", "show", "give", "get", "pull", "check", "find", "see", "view", "all"))

    # Company list
    if has_companies and (has_list or has_autotask):
        return "list_companies", ""

    # Tickets for a specific company — look for "company called X", "for X", "from X", "under X"
    company_name = _extract_company_name(text)
    if company_name and (has_tickets or has_autotask):
        return "company_tickets", company_name

    # General ticket list
    if has_tickets and (has_list or has_autotask):
        return "list_tickets", ""

    # Catch bare "autotask" queries that don't fit above
    if has_autotask and has_list:
        return "list_tickets", ""

    return "none", ""

def _extract_company_name(text: str) -> str | None:
    """Pull a company name from text. Looks for explicit markers like
    'company called X', 'for X', 'from X'. Returns None if nothing clear found."""
    lower = text.lower()

    # Explicit: "company called/named X" or "client called/named X"
    m = re.search(
        r'\b(?:company|client|account)\s+(?:called\s+|named\s+|is\s+)?'
        r'([A-Za-z][A-Za-z0-9\s&\'-]{1,39})',
        text, re.IGNORECASE
    )
    if m:
        name = m.group(1).strip().rstrip(".,?!")
        if name.split()[0].lower() not in _NOT_COMPANY:
            return name

    # "tickets for/from/with/under X" or "anything for X"
    m = re.search(
        r'\b(?:tickets?|issues?|anything)\b.{0,25}'
        r'\b(?:for|from|with|under|about)\s+'
        r'([A-Za-z][A-Za-z0-9\s&\'-]{1,39})',
        text, re.IGNORECASE
    )
    if m:
        name = m.group(1).strip().rstrip(".,?!")
        if name.split()[0].lower() not in _NOT_COMPANY:
            return name

    return None

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
    "/testmouse": "Verify pyautogui mouse control works",
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


def _version_tuple(v: str) -> tuple:
    """Convert '1.6.5' → (1, 6, 5) for numeric comparison."""
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except Exception:
        return (0,)


def auto_update(current_version: str, update_url: str):
    """Check GitHub for a newer version. If found, git pull + pip install + restart."""
    import subprocess
    import time

    console.print("[dim]Checking for updates...[/dim]", end=" ")
    latest = check_for_update(current_version, update_url)
    if not latest:
        console.print("[dim]Up to date.[/dim]")
        return

    # Only update if the remote version is strictly newer
    if _version_tuple(latest) <= _version_tuple(current_version):
        console.print(f"[dim]Up to date (remote: v{latest}).[/dim]")
        return

    console.print(f"\n  [yellow]New version available: v{latest}  (you have v{current_version})[/yellow]")
    console.print("  [cyan]Updating now...[/cyan]")

    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Pull latest code
    try:
        result = subprocess.run(
            ["git", "pull", "origin", "main"],
            cwd=script_dir,
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            console.print(f"  [red]git pull failed — update skipped.[/red]")
            console.print(f"  [dim]{result.stderr.strip()[:200]}[/dim]")
            return
        console.print("  [green]Code updated.[/green]")
    except FileNotFoundError:
        console.print("  [red]git not found — install Git for Windows and re-run.[/red]")
        return
    except Exception as e:
        console.print(f"  [red]git pull error: {e}[/red]")
        return

    # Install any new/changed dependencies
    req_path = os.path.join(script_dir, "requirements.txt")
    if os.path.exists(req_path):
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", req_path, "--quiet", "--disable-pip-version-check"],
                timeout=120,
            )
            console.print("  [green]Dependencies checked.[/green]")
        except Exception as e:
            console.print(f"  [yellow]pip install warning: {e}[/yellow]")

    console.print(f"\n  [bold green]Restarting as v{latest}...[/bold green]\n")
    time.sleep(1)

    # Spawn new process then exit cleanly (more reliable than os.execv on Windows)
    subprocess.Popen([sys.executable] + sys.argv)
    sys.exit(0)


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


def _handle_create_ticket(user_input: str, company_hint: str, ticket_brain, brain, voice):
    """Resolve company, generate a subject if needed, and create an Autotask ticket."""
    at = ticket_brain._get_autotask()
    company_id = None
    company_name = company_hint

    if company_hint:
        companies = at.search_companies_by_name(company_hint)
        if not companies:
            first = company_hint.split()[0]
            if first != company_hint:
                companies = at.search_companies_by_name(first)
        if companies:
            company_id = companies[0]["id"]
            company_name = companies[0].get("companyName", company_hint)

    if company_id is None:
        msg = (
            f"I couldn't find '{company_hint}' in Autotask — "
            "do you want to try a different name?"
        ) if company_hint else (
            "Which company should I create the ticket for?"
        )
        console.print(f"  [green]ARTY:[/green] {msg}")
        voice.speak(msg)
        return

    # Determine title
    lower = user_input.lower()
    auto_subject = any(w in lower for w in ("make up", "test", "random", "whatever", "you decide", "make one up"))
    subj_m = re.search(r'\bsubject\s+(?:is\s+)?["\']?(.+?)(?:["\']|$)', user_input, re.IGNORECASE)

    if subj_m:
        title = subj_m.group(1).strip().rstrip('.,"\' ')
    elif auto_subject:
        try:
            resp = brain.client.messages.create(
                model=brain.model,
                max_tokens=40,
                messages=[{
                    "role": "user",
                    "content": f"Generate a short realistic IT support ticket subject line for {company_name}. One line only, no quotes.",
                }],
            )
            title = resp.content[0].text.strip().strip('"\'')
        except Exception:
            title = f"Test ticket — {company_name}"
    else:
        title = "General Support Request"

    console.print(f"  [dim]Creating ticket for {company_name}: '{title}'...[/dim]")
    ticket = at.create_ticket(title=title, company_id=company_id)
    if ticket:
        num = ticket.get("ticketNumber") or ticket.get("id", "?")
        msg = f"Done — ticket #{num} created for {company_name}. Subject: '{title}'."
        console.print(f"  [green]ARTY:[/green] {msg}")
        voice.speak(msg)
    else:
        msg = "I hit an error creating the ticket — check the Autotask API credentials and integration code."
        console.print(f"  [red]ARTY:[/red] {msg}")
        voice.speak(msg)


def _list_companies(ticket_brain, voice):
    """List all companies in Autotask."""
    console.print("  [dim]Fetching company list from Autotask...[/dim]")
    try:
        at = ticket_brain._get_autotask()
        # Empty filter returns all companies
        data = at._post("Companies/query", {"filter": [{"field": "isActive", "op": "eq", "value": True}]})
        companies = data.get("items", [])
    except Exception as e:
        console.print(f"  [red]Autotask error: {e}[/red]")
        voice.speak("Couldn't pull the company list — check the connection.")
        return
    if not companies:
        voice.speak("No companies found in Autotask.")
        return
    rows = [f"  [cyan]{c.get('companyName','?')}[/cyan]  [dim](id: {c.get('id')})[/dim]"
            for c in companies[:50]]
    console.print(Panel("\n".join(rows),
                        title=f"[bold yellow]Companies ({len(companies)})[/bold yellow]",
                        border_style="yellow"))
    voice.speak(f"I can see {len(companies)} companies in Autotask.")


def _search_tickets_for_company(company_name: str, ticket_brain, voice):
    """Search Autotask for open tickets matching a company name and display results."""
    console.print(f"  [dim]Searching Autotask for tickets from '{company_name}'...[/dim]")
    try:
        at = ticket_brain._get_autotask()
        tickets, matched_name = at.search_tickets_by_company_name(company_name)
    except Exception as e:
        console.print(f"  [red]Autotask error: {e}[/red]")
        voice.speak("I hit an error connecting to Autotask — worth checking the credentials.")
        return

    if not matched_name:
        msg = f"I couldn't find a company matching '{company_name}' in Autotask."
        console.print(f"  [green]ARTY:[/green] {msg}")
        voice.speak(msg)
        return

    if not tickets:
        msg = f"No open tickets for {matched_name} right now — all clear."
        console.print(f"  [green]ARTY:[/green] {msg}")
        voice.speak(msg)
        return

    rows = [
        f"  [cyan]#{t.get('ticketNumber', t['id'])}[/cyan]  "
        f"[white]{t.get('title', '')[:60]}[/white]"
        for t in tickets
    ]
    console.print(Panel(
        "\n".join(rows),
        title=f"[bold yellow]Open Tickets — {matched_name} ({len(tickets)})[/bold yellow]",
        border_style="yellow",
    ))
    voice.speak(
        f"I found {len(tickets)} open ticket{'s' if len(tickets) != 1 else ''} "
        f"for {matched_name}. Use /ticket and the ID to work on one."
    )


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


def _email_intent(text: str) -> str | None:
    """Detect email send intent. Returns recipient name/address or None.
    Catches: 'send email to X', 'send a new email to X', 'email to X',
             'new email to X', 'compose email to X', 'email X a message'."""
    NOT_RECIP = {"me", "my", "the", "a", "an", "him", "her", "them", "it",
                 "us", "you", "your", "this", "that", "niraj"}

    # Broad: anything with "email/mail ... to NAME" in any order
    patterns = [
        r'\b(?:email|mail|message)\s+to\s+([A-Za-z][A-Za-z0-9\s\.\-]{1,35})',
        r'\bsend\b.{0,30}\bto\s+([A-Za-z][A-Za-z0-9\s\.\-]{1,35})',
        r'\bnew\s+(?:email|mail)\s+(?:to\s+)?([A-Za-z][A-Za-z0-9\s\.\-]{1,35})',
        r'\bcompose\b.{0,20}\bto\s+([A-Za-z][A-Za-z0-9\s\.\-]{1,35})',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            recipient = m.group(1).strip().rstrip(".,?! ")
            # Take only the first word if it's clearly a name (stops at prepositions)
            first_word = recipient.split()[0].lower() if recipient else ""
            if first_word and first_word not in NOT_RECIP:
                # Return first 1–3 words (name, not a full sentence)
                name_words = [w for w in recipient.split()[:3]
                              if w.lower() not in {"a", "an", "the", "new", "email", "mail"}]
                name = " ".join(name_words).strip()
                if name:
                    return name
    return None


TEXT_MODE_PHRASES = {
    "switch to text", "switch to typing", "text mode", "type mode",
    "keyboard mode", "use keyboard", "use text", "switch to keyboard",
    "type instead", "let me type", "i'll type", "typing mode",
    "switch to type function", "type function", "text input",
}

def run(start_text_mode: bool = False):
    from config import ARTY_VERSION, GITHUB_VERSION_URL
    print_banner(ARTY_VERSION)

    auto_update(ARTY_VERSION, GITHUB_VERSION_URL)

    console.print("[dim]Initialising ARTY brain...[/dim]")

    from config import ANTHROPIC_API_KEY, ENV_PATH, AUTOTASK_USE_MOUSE
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
    from brain.computer_use import ArtyComputerUse
    from config import PUSH_TO_TALK, WAKE_WORD
    from brain.personality import ARTY_GREETING

    brain = ArtyBrain()
    ears = ArtyEars()
    voice = ArtyVoice()
    eyes = ArtyEyes()
    hands = ArtyHands()
    trainer = ArtyTrainer(eyes, hands, voice, brain.memory)
    computer_use = ArtyComputerUse(eyes, voice)

    # Ticket brain — lazy-loads Autotask client on first use
    from brain.ticket_brain import ArtyTicketBrain
    ticket_brain = ArtyTicketBrain(voice=voice)

    session_id = str(uuid.uuid4())
    brain.set_session(session_id)

    from hands.control import _HAS_WINCTRL, _HAS_GW, _HAS_CLIPBOARD
    monitor_count = eyes.get_monitor_count()
    win32_status = "[green]win32 ready[/green]" if _HAS_WINCTRL else "[yellow]win32 unavailable[/yellow]"
    debug_status = "  [magenta]DEBUG ON[/magenta]" if os.environ.get("ARTY_DEBUG") == "1" else ""
    console.print(f"[bold green]ARTY is online.[/bold green]  Session: {session_id[:8]}  Monitors: {monitor_count}  {win32_status}  [cyan]Computer Use: ON[/cyan]{debug_status}\n")
    console.print(f"  [green]ARTY:[/green] {ARTY_GREETING}")
    voice.speak(ARTY_GREETING)

    use_mic = not start_text_mode
    if not use_mic:
        console.print("  [dim]Starting in text mode — type your messages. Use /mic to switch to voice.[/dim]")
    last_action_goal = None

    # Email composition state — persists across turns while gathering details
    _email_draft: dict | None = None   # {to, subject, body} — None = no email in progress

    # Lazy Outlook COM instance
    _outlook = None
    def _get_outlook():
        nonlocal _outlook
        if _outlook is None:
            from hands.outlook_com import ArtyOutlook
            _outlook = ArtyOutlook()
        return _outlook

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
                elif cmd == "/testmouse":
                    import pyautogui
                    w, h = pyautogui.size()
                    cx, cy = w // 2, h // 2
                    start_x, start_y = pyautogui.position()
                    console.print(f"\n  [yellow]── /testmouse ──[/yellow]")
                    console.print(f"  Screen size  : {w}×{h}")
                    console.print(f"  Current pos  : ({start_x}, {start_y})")
                    console.print(f"  Moving to    : ({cx}, {cy})")
                    try:
                        pyautogui.moveTo(cx, cy, duration=0.5)
                        time.sleep(0.3)
                        new_x, new_y = pyautogui.position()
                        moved = abs(new_x - cx) < 5 and abs(new_y - cy) < 5
                        if moved:
                            console.print("  Result       : [green]Mouse moved OK[/green]")
                            voice.speak("Mouse is working fine.")
                        else:
                            console.print(f"  Result       : [red]Mouse did NOT move (still at {new_x},{new_y})[/red]")
                            voice.speak("Mouse did not move — check pyautogui.")
                        pyautogui.moveTo(start_x, start_y, duration=0.3)
                    except Exception as e:
                        console.print(f"  [red]pyautogui error: {e}[/red]")
                        voice.speak(f"pyautogui threw an error: {str(e)[:60]}")
                elif cmd == "/type":
                    use_mic = False
                    console.print("  [dim]Switched to keyboard input.[/dim]")
                elif cmd == "/mic":
                    use_mic = True
                    console.print("  [dim]Switched to mic input.[/dim]")
                continue

            console.print(f"\n  [bold white]You:[/bold white] {user_input}")

            # Voice trigger to switch to text mode
            if use_mic and any(p in user_input.lower() for p in TEXT_MODE_PHRASES):
                use_mic = False
                msg = "Switching to text mode — type your messages, press Enter to send."
                console.print(f"  [green]ARTY:[/green] {msg}")
                voice.speak(msg)
                continue

            _debug_mode = os.environ.get("ARTY_DEBUG", "0") == "1"
            if _debug_mode:
                console.print(f"  [dim cyan][ROUTE] checking: '{user_input[:60]}'[/dim cyan]")
                console.print(f"  [dim cyan][ROUTE] is_action={_is_computer_action(user_input)}  last_goal={bool(last_action_goal)}[/dim cyan]")

            # ── Autotask intents (checked before generic computer-action) ─────────
            # Skip API routes when mouse mode is on — let vision loop handle it
            if not AUTOTASK_USE_MOUSE:
                _create_company = _ticket_create_intent(user_input)
                if _create_company is not None:
                    _handle_create_ticket(user_input, _create_company, ticket_brain, brain, voice)
                    continue

                _at_intent, _at_value = _autotask_intent(user_input)
                if _at_intent == "list_companies":
                    _list_companies(ticket_brain, voice)
                    continue
                elif _at_intent == "company_tickets":
                    _search_tickets_for_company(_at_value, ticket_brain, voice)
                    continue
                elif _at_intent == "list_tickets":
                    _show_tickets(ticket_brain, voice)
                    continue

            # ── Email composition via Outlook COM ─────────────────────────────────
            _recip = _email_intent(user_input)
            if _recip:
                # Start a new email draft
                _email_draft = {"to": _recip, "subject": None, "body": None}
                msg = f"Sure — email to {_recip}. What's the subject?"
                console.print(f"  [green]ARTY:[/green] {msg}")
                voice.speak(msg)
                continue

            if _email_draft is not None:
                txt = user_input.strip()
                lower_txt = txt.lower()

                # Detect cancel
                if any(w in lower_txt for w in ("cancel", "forget it", "never mind", "stop")):
                    _email_draft = None
                    msg = "Email cancelled — no problem."
                    console.print(f"  [green]ARTY:[/green] {msg}")
                    voice.speak(msg)
                    continue

                # Detect "make it up" / "you decide" / "test" — generate via Claude
                _make_up = any(p in lower_txt for p in (
                    "make it up", "make one up", "you decide", "you choose",
                    "whatever", "anything", "just test", "test email",
                    "make something up", "surprise me", "up to you",
                    "use your imagination", "just make",
                ))

                def _generate_field(field: str, recipient: str) -> str:
                    try:
                        resp = brain.client.messages.create(
                            model=brain.model, max_tokens=60,
                            messages=[{"role": "user", "content":
                                f"Write a short realistic email {field} for a test email to {recipient}. "
                                f"One line only, no quotes, no explanation."}],
                        )
                        return resp.content[0].text.strip().strip('"\'')
                    except Exception:
                        return f"Test {field} for {recipient}"

                # Extract explicit subject/body markers
                subj_m = re.search(r'\bsubject\s+(?:is\s+|line\s+is\s+)?["\']?(.+?)(?:\band\b|body|email is|message is|$)', txt, re.IGNORECASE)
                body_m = re.search(r'\b(?:body|email|message|content)\s+(?:is\s+|says?\s+)?["\']?(.+)', txt, re.IGNORECASE)

                if subj_m:
                    _email_draft["subject"] = subj_m.group(1).strip().rstrip("\"'.,")
                if body_m:
                    _email_draft["body"] = body_m.group(1).strip().rstrip("\"'.,")

                # "Make it up" — generate whichever fields are still missing
                if _make_up:
                    if _email_draft["subject"] is None:
                        _email_draft["subject"] = _generate_field("subject", _email_draft["to"])
                    if _email_draft["body"] is None:
                        _email_draft["body"] = _generate_field("body", _email_draft["to"])
                elif not subj_m and not body_m:
                    # Plain text — fill missing fields in order
                    if _email_draft["subject"] is None:
                        _email_draft["subject"] = txt
                    elif _email_draft["body"] is None:
                        _email_draft["body"] = txt

                # Still missing fields — ask
                if _email_draft["subject"] is None:
                    msg = "Got it — what should the subject be? Or say 'make it up' and I'll pick one."
                    console.print(f"  [green]ARTY:[/green] {msg}")
                    voice.speak(msg)
                    continue
                if _email_draft["body"] is None:
                    msg = f"Subject is '{_email_draft['subject']}'. What should the email say? Or say 'make it up'."
                    console.print(f"  [green]ARTY:[/green] {msg}")
                    voice.speak(msg)
                    continue

                # Try Outlook COM first, fall back to keyboard control
                console.print(f"  [dim]Opening Outlook draft — To: {_email_draft['to']}  Subject: {_email_draft['subject']}[/dim]")
                com_ok = False
                try:
                    ol = _get_outlook()
                    com_ok = ol.send_email(
                        to=_email_draft["to"],
                        subject=_email_draft["subject"],
                        body=_email_draft["body"],
                        display_first=True,
                    )
                except Exception as e:
                    console.print(f"  [yellow]Outlook COM unavailable ({type(e).__name__}) — using keyboard fallback[/yellow]")

                if com_ok:
                    msg = (f"Done — draft open in Outlook to {_email_draft['to']}, "
                           f"subject '{_email_draft['subject']}'. Hit Send when ready.")
                    console.print(f"  [green]ARTY:[/green] {msg}")
                    voice.speak(msg)
                else:
                    # Keyboard fallback: Ctrl+N in Outlook, tab through fields
                    console.print("  [dim]Trying keyboard fallback...[/dim]")
                    goal = (
                        f"Open a new email in Outlook. "
                        f"To: {_email_draft['to']}. "
                        f"Subject: {_email_draft['subject']}. "
                        f"Body: {_email_draft['body']}. "
                        f"Leave it open as a draft for the user to review."
                    )
                    success = trainer.execute_task(goal)
                    if success:
                        msg = f"Done via keyboard — email draft is open in Outlook."
                    else:
                        msg = "Couldn't open Outlook. Is it running? Try opening it manually first."
                    console.print(f"  [green]ARTY:[/green] {msg}")
                    voice.speak(msg)

                _email_draft = None
                continue

            if _is_computer_action(user_input):
                last_action_goal = user_input
                ack = random.choice(["On it.", "Sure, give me a sec.", "Right, on it.", "Yep, doing that now."])
                console.print(f"  [green]ARTY:[/green] {ack}")
                voice.speak(ack)
                success = computer_use.execute_task(user_input)
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
                success = computer_use.execute_task(last_action_goal)
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
    import argparse
    parser = argparse.ArgumentParser(description="ARTY AI Employee")
    parser.add_argument("--text", "-t", action="store_true",
                        help="Start in text/keyboard mode instead of mic")
    args = parser.parse_args()
    run(start_text_mode=args.text)
