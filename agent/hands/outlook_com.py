"""
ArtyOutlook — Outlook COM automation via win32com.

Sends email, creates drafts, reads inbox — no coordinates, no screen scraping.
Works regardless of window position or which monitor Outlook is on.
"""
import time
from rich.console import Console

console = Console()

try:
    import win32com.client as _win32
    _HAS_COM = True
except ImportError:
    _HAS_COM = False


def _get_outlook():
    if not _HAS_COM:
        raise RuntimeError("win32com not available — install pywin32")
    try:
        return _win32.GetActiveObject("Outlook.Application")
    except Exception:
        return _win32.Dispatch("Outlook.Application")


class ArtyOutlook:

    # ── send / draft ──────────────────────────────────────────────────────────

    def send_email(self, to: str, subject: str, body: str,
                   cc: str = "", display_first: bool = True) -> bool:
        """Compose and send an email.
        display_first=True shows the draft for the user to review before sending.
        display_first=False sends immediately (use only when user has confirmed).
        """
        if not _HAS_COM:
            console.print("  [red][Outlook] pywin32 not installed[/red]")
            return False
        try:
            ol = _get_outlook()
            mail = ol.CreateItem(0)  # 0 = olMailItem
            mail.To      = to
            mail.Subject = subject
            mail.Body    = body
            if cc:
                mail.CC = cc
            if display_first:
                mail.Display()
                console.print("  [yellow][Outlook] Draft shown — waiting for user to review/send[/yellow]")
            else:
                mail.Send()
                console.print(f"  [green][Outlook] Email sent to {to}[/green]")
            return True
        except Exception as e:
            console.print(f"  [red][Outlook] send_email error: {e}[/red]")
            return False

    def create_draft(self, to: str, subject: str, body: str, cc: str = "") -> bool:
        """Create a draft without sending or displaying."""
        if not _HAS_COM:
            return False
        try:
            ol   = _get_outlook()
            mail = ol.CreateItem(0)
            mail.To      = to
            mail.Subject = subject
            mail.Body    = body
            if cc:
                mail.CC = cc
            mail.Save()
            console.print(f"  [green][Outlook] Draft saved for {to}[/green]")
            return True
        except Exception as e:
            console.print(f"  [red][Outlook] create_draft error: {e}[/red]")
            return False

    def reply_to_email(self, subject_contains: str, reply_body: str,
                       display_first: bool = True) -> bool:
        """Find an email by subject and reply to it. Used to add notes to
        Autotask tickets via the ticket email reply address."""
        if not _HAS_COM:
            return False
        try:
            ol     = _get_outlook()
            inbox  = ol.GetNamespace("MAPI").GetDefaultFolder(6)  # 6 = olFolderInbox
            items  = inbox.Items
            items.Sort("[ReceivedTime]", True)  # newest first
            for item in items:
                try:
                    if subject_contains.lower() in item.Subject.lower():
                        reply = item.Reply()
                        reply.Body = reply_body + "\n\n" + reply.Body
                        if display_first:
                            reply.Display()
                        else:
                            reply.Send()
                        console.print(f"  [green][Outlook] Reply created for '{item.Subject}'[/green]")
                        return True
                except Exception:
                    continue
            console.print(f"  [yellow][Outlook] No email found matching '{subject_contains}'[/yellow]")
            return False
        except Exception as e:
            console.print(f"  [red][Outlook] reply_to_email error: {e}[/red]")
            return False

    # ── read inbox ────────────────────────────────────────────────────────────

    def get_unread_count(self) -> int:
        if not _HAS_COM:
            return 0
        try:
            ol    = _get_outlook()
            inbox = ol.GetNamespace("MAPI").GetDefaultFolder(6)
            return inbox.UnReadItemCount
        except Exception:
            return 0

    def read_recent_emails(self, count: int = 10, unread_only: bool = False) -> list[dict]:
        """Return recent emails as dicts with subject/sender/preview only.
        Body is truncated to 500 chars — enough for ARTY to understand context
        without pulling large volumes of data into memory."""
        if not _HAS_COM:
            return []
        try:
            ol    = _get_outlook()
            inbox = ol.GetNamespace("MAPI").GetDefaultFolder(6)
            items = inbox.Items
            items.Sort("[ReceivedTime]", True)
            results = []
            checked = 0
            for item in items:
                if checked >= count * 3:  # stop scanning after 3× limit
                    break
                checked += 1
                try:
                    if unread_only and item.UnRead is False:
                        continue
                    results.append({
                        "subject":   item.Subject,
                        "sender":    item.SenderName,
                        "sender_email": item.SenderEmailAddress,
                        "received":  str(item.ReceivedTime),
                        "unread":    item.UnRead,
                        "preview":   (item.Body or "")[:500],
                        "entry_id":  item.EntryID,
                    })
                    if len(results) >= count:
                        break
                except Exception:
                    continue
            return results
        except Exception as e:
            console.print(f"  [red][Outlook] read_recent_emails error: {e}[/red]")
            return []

    def find_ticket_email(self, ticket_number: str) -> dict | None:
        """Find the Autotask notification email for a given ticket number.
        Returns email dict or None. Used to get the reply-to address for
        adding notes to Autotask without API calls."""
        emails = self.read_recent_emails(count=50)
        for e in emails:
            if ticket_number in e.get("subject", ""):
                return e
        return None

    # ── Teams message (via Outlook contacts / mailto fallback) ────────────────

    def check_teams_replies(self, keywords: list[str], lookback_count: int = 20) -> list[dict]:
        """Scan recent emails for Teams chat notifications containing keywords.
        Teams often delivers missed-chat notifications to Outlook inbox."""
        emails = self.read_recent_emails(count=lookback_count)
        hits = []
        for e in emails:
            text = (e["subject"] + " " + e["preview"]).lower()
            if any(k.lower() in text for k in keywords):
                hits.append(e)
        return hits
