"""
TicketTerminal — interactive ticket work + observation learning.

Usage:
  /tickets            → list open tickets, pick one to work on
  Inside a ticket:
    note <text>       → add internal note to ticket
    did  <what>       → record an action you took (ARTY learns)
    close <note>      → close ticket with closing note
    back              → back to ticket list
    help              → show commands

Learning:
  Every time you complete a ticket, ARTY records the ticket type,
  the company, and what you did. After a few repetitions it builds
  enough confidence to propose the steps itself.
"""

import json
import sqlite3
import os
from datetime import datetime, timezone
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console()

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "../data/ticket_playbook.db")

# Minimum observations before ARTY proposes an action autonomously
CONFIDENCE_THRESHOLD = 3


# ── database ──────────────────────────────────────────────────────────────────

def _db() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript("""
        CREATE TABLE IF NOT EXISTS observations (
            id           INTEGER PRIMARY KEY,
            ticket_type  TEXT,
            company_id   INTEGER,
            company_name TEXT,
            actions      TEXT,
            ticket_note  TEXT,
            created_at   TEXT
        );
        CREATE TABLE IF NOT EXISTS playbooks (
            id           INTEGER PRIMARY KEY,
            ticket_type  TEXT NOT NULL,
            company_id   INTEGER NOT NULL DEFAULT 0,
            company_name TEXT,
            steps        TEXT,
            quirks       TEXT,
            obs_count    INTEGER DEFAULT 0,
            updated_at   TEXT,
            UNIQUE(ticket_type, company_id)
        );
    """)
    con.commit()
    return con


def _save_observation(ticket_type: str, company_id: int, company_name: str,
                      actions: list[str], note: str):
    with _db() as con:
        con.execute(
            "INSERT INTO observations (ticket_type, company_id, company_name, "
            "actions, ticket_note, created_at) VALUES (?,?,?,?,?,?)",
            (ticket_type, company_id, company_name,
             json.dumps(actions), note, datetime.now(timezone.utc).isoformat()),
        )
        # Upsert playbook — merge new steps in
        existing = con.execute(
            "SELECT * FROM playbooks WHERE ticket_type=? AND company_id=?",
            (ticket_type, company_id)
        ).fetchone()
        now = datetime.now(timezone.utc).isoformat()
        if existing:
            merged = _merge_steps(json.loads(existing["steps"] or "[]"), actions)
            con.execute(
                "UPDATE playbooks SET steps=?, obs_count=obs_count+1, "
                "company_name=?, updated_at=? "
                "WHERE ticket_type=? AND company_id=?",
                (json.dumps(merged), company_name, now, ticket_type, company_id),
            )
        else:
            con.execute(
                "INSERT INTO playbooks (ticket_type, company_id, company_name, "
                "steps, obs_count, updated_at) VALUES (?,?,?,?,1,?)",
                (ticket_type, company_id, company_name,
                 json.dumps(actions), now),
            )


def _merge_steps(existing: list, new_steps: list) -> list:
    """Merge new action steps into existing list, deduplicating."""
    merged = list(existing)
    for step in new_steps:
        if not any(step.lower() in e.lower() or e.lower() in step.lower()
                   for e in merged):
            merged.append(step)
    return merged


def _get_playbook(ticket_type: str, company_id: int) -> dict | None:
    """Return playbook for this type + company, or just type-level, or None."""
    with _db() as con:
        row = con.execute(
            "SELECT * FROM playbooks WHERE ticket_type=? AND company_id=?",
            (ticket_type, company_id)
        ).fetchone()
        if row:
            return dict(row)
        # Fall back to global (company_id=0)
        row = con.execute(
            "SELECT * FROM playbooks WHERE ticket_type=? AND company_id=0",
            (ticket_type,)
        ).fetchone()
        return dict(row) if row else None


def _get_obs_count(ticket_type: str, company_id: int) -> int:
    with _db() as con:
        row = con.execute(
            "SELECT obs_count FROM playbooks WHERE ticket_type=? AND company_id=?",
            (ticket_type, company_id)
        ).fetchone()
        return row["obs_count"] if row else 0


# ── ticket type classifier ────────────────────────────────────────────────────

TICKET_TYPES = {
    "password_reset": ["password", "reset", "locked out", "can't log in", "cannot login",
                       "forgot password", "account locked", "sspr"],
    "mfa_reset":      ["mfa", "authenticator", "2fa", "two factor", "auth app",
                       "microsoft authenticator", "can't authenticate"],
    "mailbox_delegation": ["delegate", "delegation", "shared mailbox", "access to mailbox",
                           "full access", "send as", "send on behalf"],
    "new_user":       ["new user", "new staff", "new employee", "new account",
                       "create account", "onboarding", "new starter"],
    "offboarding":    ["leave", "left", "terminated", "offboard", "disable account",
                       "remove access", "ex-staff", "leaver"],
    "email_issue":    ["email not working", "not receiving", "outlook", "mail issue",
                       "sending email", "receiving email"],
    "email_change":   ["change email", "update email", "new email", "display name",
                       "rename", "name change"],
    "general":        [],
}


def _classify(text: str) -> str:
    low = text.lower()
    for ttype, keywords in TICKET_TYPES.items():
        if any(kw in low for kw in keywords):
            return ttype
    return "general"


# ── display helpers ───────────────────────────────────────────────────────────

_TYPE_LABEL = {
    "password_reset":     "[cyan]Password Reset[/cyan]",
    "mfa_reset":          "[magenta]MFA Reset[/magenta]",
    "mailbox_delegation": "[yellow]Mailbox Delegation[/yellow]",
    "new_user":           "[green]New User[/green]",
    "offboarding":        "[red]Offboarding[/red]",
    "email_issue":        "[blue]Email Issue[/blue]",
    "email_change":       "[blue]Email Change[/blue]",
    "general":            "[dim]General[/dim]",
}

_APPROVAL_REQUIRED = {"mailbox_delegation", "offboarding"}


def _type_label(ttype: str) -> str:
    return _TYPE_LABEL.get(ttype, ttype)


# ── main terminal class ───────────────────────────────────────────────────────

class TicketTerminal:

    def __init__(self, voice=None):
        self.voice = voice
        self._at   = None   # ArtyAutotask — lazy init

    def _say(self, text: str):
        console.print(f"  [green]ARTY:[/green] {text}")
        if self.voice:
            self.voice.speak_async(text)

    def _at_client(self):
        if self._at is None:
            from brain.autotask import ArtyAutotask
            self._at = ArtyAutotask()
        return self._at

    # ── ticket list ───────────────────────────────────────────────────────────

    def run(self):
        """Main entry point — show ticket list and loop."""
        console.print("\n[bold yellow]ARTY Ticket Terminal[/bold yellow]  [dim](type 'exit' to leave)[/dim]\n")

        while True:
            tickets = self._fetch_tickets()
            if not tickets:
                console.print("  [dim]No open tickets found.[/dim]")
                return

            self._show_list(tickets)
            console.print("\n  Type a row number to open it, or [bold]exit[/bold]: ", end="")
            choice = input().strip().lower()

            if choice in ("exit", "quit", "back", ""):
                return
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(tickets):
                    self._open_ticket(tickets[idx])
                else:
                    console.print("  [red]Out of range.[/red]")
            except ValueError:
                console.print("  [red]Enter a number or 'exit'.[/red]")

    def _fetch_tickets(self) -> list:
        try:
            at = self._at_client()
            tickets = at.get_open_tickets(max_results=30)
            # Enrich with company name + type
            enriched = []
            for t in tickets:
                company = at.get_company_name(t.get("companyID", 0))
                text = f"{t.get('title','')} {t.get('description','')}"
                ttype = _classify(text)
                enriched.append({**t, "_company": company, "_type": ttype})
            return enriched
        except Exception as e:
            console.print(f"  [red]Autotask error: {e}[/red]")
            return []

    def _show_list(self, tickets: list):
        table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold")
        table.add_column("#", style="dim", width=4)
        table.add_column("Ticket #", width=12)
        table.add_column("Company", width=22)
        table.add_column("Title", width=38)
        table.add_column("Type", width=20)

        for i, t in enumerate(tickets, 1):
            table.add_row(
                str(i),
                str(t.get("ticketNumber", t.get("id", "?"))),
                t["_company"][:22],
                (t.get("title", "")[:38]),
                _type_label(t["_type"]),
            )
        console.print(table)

    # ── single ticket work session ────────────────────────────────────────────

    def _open_ticket(self, ticket: dict):
        ttype      = ticket["_type"]
        company    = ticket["_company"]
        company_id = ticket.get("companyID", 0)
        tid        = ticket["id"]
        tnum       = ticket.get("ticketNumber", str(tid))
        title      = ticket.get("title", "")
        desc       = ticket.get("description", "") or ""

        playbook  = _get_playbook(ttype, company_id)
        obs_count = _get_obs_count(ttype, company_id)
        approval_needed = ttype in _APPROVAL_REQUIRED

        # Build panel content
        lines = [
            f"[bold]Ticket #{tnum}[/bold]   Company: [cyan]{company}[/cyan]",
            f"Type: {_type_label(ttype)}",
            "",
            f"[bold]Title:[/bold] {title}",
        ]
        if desc.strip():
            lines += ["", "[bold]Description:[/bold]", desc[:600]]

        if approval_needed:
            lines += ["", "[bold red]⚠ This ticket type requires approval before actioning.[/bold red]",
                      "Confirm approval is documented in the ticket before proceeding."]

        if playbook and obs_count >= 1:
            steps = json.loads(playbook.get("steps") or "[]")
            confidence = min(obs_count / CONFIDENCE_THRESHOLD, 1.0)
            conf_bar = "█" * int(confidence * 10) + "░" * (10 - int(confidence * 10))
            lines += [
                "",
                f"[bold]What I've learned ({obs_count} observation{'s' if obs_count != 1 else ''}, "
                f"confidence {conf_bar} {int(confidence*100)}%):[/bold]",
            ]
            for s in steps:
                lines.append(f"  • {s}")
            if obs_count >= CONFIDENCE_THRESHOLD:
                lines.append("")
                lines.append("[bold green]→ I'm confident enough to suggest the steps above.[/bold green]")
        else:
            lines += ["", "[dim]First time seeing this ticket type for this customer — I'll learn from you.[/dim]"]

        lines += [
            "",
            "[bold]Commands:[/bold]  "
            "[cyan]did <what you did>[/cyan]  "
            "[cyan]note <text>[/cyan]  "
            "[cyan]close <closing note>[/cyan]  "
            "[cyan]back[/cyan]  [cyan]help[/cyan]",
        ]

        console.print(Panel("\n".join(lines), title="[bold yellow]ARTY — Ticket[/bold yellow]",
                            border_style="yellow"))

        if obs_count >= CONFIDENCE_THRESHOLD:
            self._say(
                f"Ticket {tnum} for {company}. Based on what I've seen before, "
                f"I think I know how to handle this one — have a look at my suggested steps."
            )
        else:
            self._say(
                f"Ticket {tnum} for {company}. I'm watching and learning — "
                f"just action it as normal and tell me what you did when you're done."
            )

        actions_taken = []

        while True:
            console.print("\n  [dim]>[/dim] ", end="")
            raw = input().strip()
            if not raw:
                continue
            cmd, _, rest = raw.partition(" ")
            cmd = cmd.lower()

            if cmd == "back":
                return

            elif cmd == "help":
                console.print(
                    "  [bold]did[/bold] <action>     — record an action you took\n"
                    "  [bold]note[/bold] <text>      — add internal note to ticket\n"
                    "  [bold]close[/bold] <note>     — add closing note + mark complete\n"
                    "  [bold]back[/bold]             — return to ticket list\n"
                    "  [bold]approval[/bold]         — confirm approval has been obtained\n"
                )

            elif cmd == "approval":
                console.print("  [green]✓ Approval confirmed — noted.[/green]")
                actions_taken.append("Approval confirmed by engineer before actioning")

            elif cmd == "did":
                if not rest:
                    console.print("  [dim]What did you do? e.g. 'did reset password and cleared MFA'[/dim]")
                    continue
                actions_taken.append(rest)
                console.print(f"  [green]✓ Recorded:[/green] {rest}")

            elif cmd == "note":
                if not rest:
                    console.print("  [dim]Note text?[/dim]")
                    continue
                try:
                    self._at_client().add_note(tid, rest, publish=1)
                    console.print("  [green]✓ Note added to ticket.[/green]")
                except Exception as e:
                    console.print(f"  [red]Note failed: {e}[/red]")

            elif cmd == "close":
                closing_note = rest or "Resolved."
                if not actions_taken:
                    console.print("  [dim]Before closing — what did you do? (type 'did <action>' first, or just confirm)[/dim]")
                    console.print("  [dim]Press Enter to close anyway, or type what you did: [/dim]", end="")
                    extra = input().strip()
                    if extra:
                        actions_taken.append(extra)

                # Save observation
                if actions_taken:
                    _save_observation(ttype, company_id, company, actions_taken, closing_note)
                    console.print(f"  [dim cyan]Learned: {len(actions_taken)} action(s) recorded for '{ttype}' @ {company}[/dim cyan]")

                # Close ticket
                try:
                    at = self._at_client()
                    at.close_ticket(tid, closing_note)
                    self._say(f"Ticket {tnum} closed. I've recorded what you did — I'll remember it for next time.")
                except Exception as e:
                    console.print(f"  [red]Close failed: {e}[/red]")
                return

            else:
                console.print("  [dim]Unknown command. Type 'help' for options.[/dim]")
