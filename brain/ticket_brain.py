"""
ArtyTicketBrain — Reads Autotask tickets, classifies them, matches procedures,
presents a plan, and executes with user confirmation.

Security: ticket content (PII) is never written to ChromaDB or SQLite.
Only procedure templates (the HOW, not the WHO) are persisted.
"""
import json
import time
import anthropic
from datetime import datetime
from rich.console import Console
from rich.panel import Panel

console = Console()

# ── ticket type taxonomy ──────────────────────────────────────────────────────

TICKET_TYPES = {
    "password_reset":    ["password", "reset", "locked out", "can't log in", "cannot login",
                          "forgot password", "account locked", "mfa", "authenticator"],
    "email_change":      ["change email", "update email", "new email", "email address",
                          "display name", "rename", "name change"],
    "new_user":          ["new user", "new staff", "new employee", "new account",
                          "create account", "onboarding", "new starter"],
    "offboarding":       ["leave", "left", "terminated", "offboard", "disable account",
                          "remove access", "ex-staff"],
    "software_install":  ["install", "need software", "application", "setup"],
    "email_issue":       ["email not working", "not receiving", "outlook", "mail issue",
                          "email problem", "sending email", "receiving email"],
    "general":           [],  # fallback
}


def classify_ticket(description: str) -> str:
    """Fast keyword-based classifier. Returns ticket type key."""
    desc_lower = description.lower()
    for ttype, keywords in TICKET_TYPES.items():
        if any(kw in desc_lower for kw in keywords):
            return ttype
    return "general"


# ── procedure library ─────────────────────────────────────────────────────────

DEFAULT_PROCEDURES = {
    "password_reset": {
        "name": "M365 Password Reset",
        "steps": [
            "Ask ARTY to confirm the user's display name and email from the ticket",
            "Open Partner Centre or admin.microsoft.com and navigate to the correct tenant",
            "Search for the user by name or email",
            "Reset the password — generate a temp password and require change on next login",
            "Add a note to the Autotask ticket with the temp password instructions",
            "Send the user an email with the temp password (do NOT include password in ticket note visible to all)",
            "Close the Autotask ticket",
        ],
        "needs_m365": True,
        "needs_email": True,
    },
    "email_change": {
        "name": "M365 Display Name / Email Change",
        "steps": [
            "Confirm what needs changing — display name, email alias, or primary email",
            "Navigate to the correct tenant in Partner Centre / admin.microsoft.com",
            "Find the user and update name or email as requested",
            "If primary email changed, confirm old address is kept as alias",
            "Update the Autotask ticket with what was changed",
            "Notify the user of the change by email",
            "Close the ticket",
        ],
        "needs_m365": True,
        "needs_email": True,
    },
    "new_user": {
        "name": "New User Setup",
        "steps": [
            "Get full name, email format, department, manager, licence type from ticket",
            "Create M365 account in correct tenant with matching email format",
            "Assign appropriate licence",
            "Add to relevant groups/distribution lists",
            "Set temp password and require change on next login",
            "Update ticket and send welcome email to manager/new user",
            "Close ticket",
        ],
        "needs_m365": True,
        "needs_email": True,
    },
    "offboarding": {
        "name": "User Offboarding",
        "steps": [
            "Confirm the user to offboard and last working date",
            "Block sign-in on the M365 account",
            "Remove from distribution lists and shared mailboxes (or keep mailbox — ask)",
            "Revoke active sessions / MFA devices",
            "Convert mailbox to shared if needed",
            "Update ticket and confirm with manager",
            "Close ticket",
        ],
        "needs_m365": True,
        "needs_email": True,
    },
    "general": {
        "name": "General Ticket",
        "steps": [
            "Read the ticket carefully",
            "Ask the user (Bill) what action to take",
            "Follow Bill's instructions",
            "Update and close the ticket when done",
        ],
        "needs_m365": False,
        "needs_email": False,
    },
}


class ArtyTicketBrain:

    def __init__(self, voice=None):
        from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.model  = CLAUDE_MODEL
        self.voice  = voice
        self._seen_ticket_ids: set = set()

        # Lazy-init heavy dependencies
        self._autotask  = None
        self._outlook   = None

    def _get_autotask(self):
        if self._autotask is None:
            from brain.autotask import ArtyAutotask
            self._autotask = ArtyAutotask()
        return self._autotask

    def _get_outlook(self):
        if self._outlook is None:
            from hands.outlook_com import ArtyOutlook
            self._outlook = ArtyOutlook()
        return self._outlook

    # ── speaking helper ───────────────────────────────────────────────────────

    def _say(self, text: str):
        console.print(f"  [green]ARTY:[/green] {text}")
        if self.voice:
            self.voice.speak(text)

    # ── ticket polling ────────────────────────────────────────────────────────

    def check_for_tickets(self) -> dict | None:
        """Poll Autotask for a new ticket not yet seen. Returns ticket dict or None."""
        try:
            at = self._get_autotask()
            tickets = at.get_open_tickets(max_results=20)
            for t in tickets:
                if t["id"] not in self._seen_ticket_ids:
                    return t
            return None
        except Exception as e:
            console.print(f"  [red][TicketBrain] poll error: {e}[/red]")
            return None

    def mark_seen(self, ticket_id: int):
        self._seen_ticket_ids.add(ticket_id)

    # ── classification + planning ─────────────────────────────────────────────

    def classify_and_plan(self, ticket: dict) -> dict:
        """Classify a ticket and build an action plan.
        Returns {type, procedure, summary, company_name, ticket_number}.
        Ticket content is used only in memory — not persisted."""
        at           = self._get_autotask()
        summary      = at.summarise_for_arty(ticket)
        company_name = at.get_company_name(ticket.get("companyID", 0))
        ticket_num   = ticket.get("ticketNumber", str(ticket.get("id")))

        # Fast keyword classification first
        full_text  = f"{ticket.get('title','')} {ticket.get('description','')}"
        ttype      = classify_ticket(full_text)
        procedure  = DEFAULT_PROCEDURES.get(ttype, DEFAULT_PROCEDURES["general"])

        # Ask Claude to refine and extract key facts (user name, what's needed)
        claude_summary = self._ask_claude_to_summarise(summary, ttype)

        return {
            "ticket_id":    ticket["id"],
            "ticket_number": ticket_num,
            "company_name": company_name,
            "type":         ttype,
            "procedure":    procedure,
            "raw_summary":  summary,
            "arty_summary": claude_summary,
        }

    def _ask_claude_to_summarise(self, ticket_text: str, ttype: str) -> str:
        """Ask Claude to extract the key facts from a ticket in one sentence.
        E.g. 'User John Smith at Contoso needs a password reset.'"""
        try:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=200,
                messages=[{
                    "role": "user",
                    "content": (
                        f"Summarise this IT support ticket in one sentence. "
                        f"Include: who needs help, what company, what's needed. "
                        f"Ticket type detected: {ttype}.\n\n{ticket_text}"
                    ),
                }],
            )
            return resp.content[0].text.strip()
        except Exception:
            return ticket_text[:200]

    # ── announce ticket to user ───────────────────────────────────────────────

    def announce_ticket(self, plan: dict) -> bool:
        """Tell the user about the ticket and ask if they want to work on it.
        Returns True if user wants to proceed."""
        proc = plan["procedure"]
        console.print(Panel(
            f"[bold]Ticket #{plan['ticket_number']}[/bold]\n"
            f"Company: [cyan]{plan['company_name']}[/cyan]\n"
            f"Type:    [yellow]{proc['name']}[/yellow]\n\n"
            f"[dim]{plan['arty_summary']}[/dim]\n\n"
            f"[bold]My plan:[/bold]\n" +
            "\n".join(f"  {i+1}. {s}" for i, s in enumerate(proc["steps"])),
            title="[bold yellow]ARTY — New Ticket[/bold yellow]",
            border_style="yellow",
        ))

        msg = (
            f"I've got ticket {plan['ticket_number']} — {plan['arty_summary']}. "
            f"I'm planning to {proc['name'].lower()}. "
            f"Want to do this one together?"
        )
        self._say(msg)
        return True  # caller handles user's yes/no input

    # ── step-by-step execution ────────────────────────────────────────────────

    def start_ticket(self, plan: dict):
        """Mark ticket in-progress and walk through steps with the user."""
        try:
            at = self._get_autotask()
            at.set_in_progress(plan["ticket_id"])
            at.add_note(
                plan["ticket_id"],
                f"ARTY is working on this ticket. Type: {plan['type']}.",
                publish=1,  # internal note
            )
        except Exception as e:
            console.print(f"  [dim red][TicketBrain] start_ticket note failed: {e}[/dim red]")

        self._say(
            f"Right, I've marked the ticket as in progress. "
            f"Let's go through it step by step — I'll tell you what I'm doing "
            f"and check with you before anything important."
        )

    def close_ticket(self, plan: dict, closing_note: str):
        """Add closing note and mark ticket complete."""
        try:
            at = self._get_autotask()
            at.close_ticket(plan["ticket_id"], closing_note)
            self._say(
                f"Ticket {plan['ticket_number']} is closed. "
                f"Good work — I've logged what we did."
            )
        except Exception as e:
            console.print(f"  [red][TicketBrain] close_ticket failed: {e}[/red]")
            self._say("I tried to close the ticket but hit an error — worth checking it manually.")

    def send_completion_email(self, plan: dict, to_email: str,
                              temp_password: str = "", extra_notes: str = ""):
        """Send a resolution email to the end user via Outlook COM."""
        ol      = self._get_outlook()
        subject = f"RE: Ticket #{plan['ticket_number']} — {plan['arty_summary'][:60]}"

        if temp_password:
            body = (
                f"Hi,\n\n"
                f"Your IT support ticket has been resolved.\n\n"
                f"Your temporary password is: {temp_password}\n"
                f"Please log in and change this password immediately.\n\n"
                f"{extra_notes}\n\n"
                f"Kind regards,\nSharp IT Support"
            )
        else:
            body = (
                f"Hi,\n\n"
                f"Your IT support ticket has been resolved.\n\n"
                f"{extra_notes}\n\n"
                f"Kind regards,\nSharp IT Support"
            )

        ol.send_email(to_email, subject, body, display_first=True)
        self._say("I've prepared the email — have a quick look and send when you're happy.")

    # ── procedure learning ────────────────────────────────────────────────────

    def learn_procedure(self, ticket_type: str, steps: list[str], notes: str = ""):
        """Store a learned procedure. Only the HOW is saved — no customer data."""
        if ticket_type not in DEFAULT_PROCEDURES:
            DEFAULT_PROCEDURES[ticket_type] = {
                "name": ticket_type.replace("_", " ").title(),
                "steps": steps,
                "needs_m365": True,
                "needs_email": True,
            }
        else:
            DEFAULT_PROCEDURES[ticket_type]["steps"] = steps
        console.print(f"  [green][TicketBrain] Procedure '{ticket_type}' updated ({len(steps)} steps)[/green]")
