"""
ArtyAutotask — Autotask PSA REST API client.

Reads tickets, adds notes, updates status. No personal data is cached —
all ticket content is processed in memory only and never written to
ChromaDB or SQLite.
"""
import requests
import time
from datetime import datetime, timezone
from rich.console import Console

console = Console()

# Autotask tries multiple zone detection URLs — casing varies by environment
ZONE_DETECT_URLS = [
    "https://webservices2.autotask.net/ATServicesRest/v1.0/zoneInformation?user={email}",
    "https://webservices2.autotask.net/atservicesrest/v1.0/zoneInformation?user={email}",
]

# Autotask ticket status IDs (standard defaults — may differ per account)
STATUS_NEW        = 1
STATUS_IN_PROGRESS = 8
STATUS_WAITING    = 9
STATUS_COMPLETE   = 5

# Ticket queue/resource filter — set via .env
AUTOTASK_QUEUE_ID    = None  # optional: filter by queue
AUTOTASK_RESOURCE_ID = None  # optional: filter by assigned resource


class AutotaskError(Exception):
    pass


class ArtyAutotask:

    def __init__(self):
        from config import (AUTOTASK_API_USER, AUTOTASK_API_SECRET,
                            AUTOTASK_INTEGRATION_CODE, AUTOTASK_ZONE_URL)
        self.user    = AUTOTASK_API_USER
        self.secret  = AUTOTASK_API_SECRET
        self.int_code = AUTOTASK_INTEGRATION_CODE

        if AUTOTASK_ZONE_URL:
            # If user gave a full API base URL use it directly, otherwise append the path
            if "ATServicesRest" in AUTOTASK_ZONE_URL:
                self.base = AUTOTASK_ZONE_URL.rstrip("/")
            else:
                self.base = AUTOTASK_ZONE_URL.rstrip("/") + "/ATServicesRest/v1.0"
        else:
            self.base = self._detect_zone()

        console.print(f"  [dim cyan][Autotask] base URL: {self.base}[/dim cyan]")

    # ── zone detection ────────────────────────────────────────────────────────

    def _detect_zone(self) -> str:
        last_err = ""
        for detect_url in ZONE_DETECT_URLS:
            url = detect_url.format(email=requests.utils.quote(self.user, safe="@."))
            try:
                r = requests.get(url, timeout=10)
                if not r.ok:
                    last_err = f"HTTP {r.status_code} from {url}"
                    continue
                data = r.json()
                zone_url = data.get("url", "").rstrip("/")
                if not zone_url:
                    last_err = f"No 'url' field in zone response: {data}"
                    continue
                full_base = zone_url + "/ATServicesRest/v1.0"
                console.print(f"  [dim cyan][Autotask] zone detected: {full_base}[/dim cyan]")
                return full_base
            except Exception as e:
                last_err = str(e)
                continue
        raise AutotaskError(
            f"Could not detect Autotask zone. Last error: {last_err}\n"
            f"Add AUTOTASK_ZONE_URL to your .env (e.g. https://webservices6.autotask.net)"
        )

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    def _headers(self) -> dict:
        h = {
            "UserName": self.user,
            "Secret":   self.secret,
            "Content-Type": "application/json",
        }
        if self.int_code:
            h["ApiIntegrationCode"] = self.int_code
        return h

    def _url(self, path: str) -> str:
        return f"{self.base}/{path}"

    def _get(self, path: str, params: dict = None) -> dict:
        full = self._url(path)
        r = requests.get(full, headers=self._headers(), params=params, timeout=15)
        if not r.ok:
            raise AutotaskError(f"GET {full} → {r.status_code}: {r.text[:300]}")
        return r.json()

    def _post(self, path: str, body: dict) -> dict:
        full = self._url(path)
        r = requests.post(full, headers=self._headers(), json=body, timeout=15)
        if not r.ok:
            raise AutotaskError(f"POST {full} → {r.status_code}: {r.text[:300]}")
        return r.json()

    def _patch(self, path: str, body: dict) -> dict:
        full = self._url(path)
        r = requests.patch(full, headers=self._headers(), json=body, timeout=15)
        if not r.ok:
            raise AutotaskError(f"PATCH {full} → {r.status_code}: {r.text[:300]}")
        return r.json()

    # ── ticket queries ────────────────────────────────────────────────────────

    def get_open_tickets(self, max_results: int = 20) -> list[dict]:
        """Return open tickets. Filters by queue/resource if configured.
        Returns minimal fields — full detail fetched per-ticket to avoid bulk PII load."""
        filters = [
            {"field": "status", "op": "noteq", "value": STATUS_COMPLETE},
        ]
        if AUTOTASK_QUEUE_ID:
            filters.append({"field": "queueID", "op": "eq", "value": AUTOTASK_QUEUE_ID})
        if AUTOTASK_RESOURCE_ID:
            filters.append({"field": "assignedResourceID", "op": "eq",
                            "value": AUTOTASK_RESOURCE_ID})

        body = {
            "filter": [{"op": "and", "items": filters}],
            "MaxRecords": max_results,
            "includeFields": ["id", "title", "status", "queueID",
                              "companyID", "contactID", "ticketNumber",
                              "createDate", "priority"],
        }
        try:
            data = self._post("Tickets/query", body)
            return data.get("items", [])
        except AutotaskError as e:
            console.print(f"  [red][Autotask] get_open_tickets: {e}[/red]")
            return []

    def get_ticket(self, ticket_id: int) -> dict | None:
        """Fetch full ticket detail. NOT cached — processed in memory only."""
        try:
            data = self._get(f"Tickets/{ticket_id}")
            return data.get("item")
        except AutotaskError as e:
            console.print(f"  [red][Autotask] get_ticket {ticket_id}: {e}[/red]")
            return None

    def get_ticket_description(self, ticket_id: int) -> str:
        """Return the ticket description/body text only — no PII metadata."""
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return ""
        return ticket.get("description", "") or ticket.get("title", "")

    def get_company_name(self, company_id: int) -> str:
        """Look up company name by ID."""
        try:
            data = self._get(f"Companies/{company_id}")
            return data.get("item", {}).get("companyName", f"Company {company_id}")
        except AutotaskError:
            return f"Company {company_id}"

    def search_companies_by_name(self, name: str) -> list[dict]:
        """Find companies whose name contains the search string."""
        body = {
            "filter": [{"op": "and", "items": [
                {"field": "companyName", "op": "contains", "value": name},
                {"field": "isActive", "op": "eq", "value": True},
            ]}],
            "MaxRecords": 10,
            "includeFields": ["id", "companyName"],
        }
        try:
            data = self._post("Companies/query", body)
            return data.get("items", [])
        except AutotaskError as e:
            console.print(f"  [red][Autotask] search_companies: {e}[/red]")
            return []

    def get_tickets_for_company(self, company_id: int, max_results: int = 10) -> list[dict]:
        """Return open tickets for a specific company ID."""
        body = {
            "filter": [{"op": "and", "items": [
                {"field": "companyID", "op": "eq", "value": company_id},
                {"field": "status", "op": "noteq", "value": STATUS_COMPLETE},
            ]}],
            "MaxRecords": max_results,
            "includeFields": ["id", "title", "status", "ticketNumber",
                              "companyID", "contactID", "createDate", "priority"],
        }
        try:
            data = self._post("Tickets/query", body)
            return data.get("items", [])
        except AutotaskError as e:
            console.print(f"  [red][Autotask] get_tickets_for_company: {e}[/red]")
            return []

    def search_tickets_by_company_name(self, company_name: str) -> tuple[list, str]:
        """Find open tickets for a company by fuzzy name search.
        Returns (tickets, matched_company_name). Tries partial match first."""
        companies = self.search_companies_by_name(company_name)
        if not companies:
            # Try first word only in case of transcription variation
            first_word = company_name.split()[0]
            if first_word != company_name:
                companies = self.search_companies_by_name(first_word)
        if not companies:
            return [], ""
        best = companies[0]
        tickets = self.get_tickets_for_company(best["id"])
        return tickets, best["companyName"]

    # ── ticket actions ────────────────────────────────────────────────────────

    def add_note(self, ticket_id: int, note_text: str,
                 note_type: int = 1, publish: int = 2) -> bool:
        """Add a note to a ticket.
        note_type 1 = Task/Note. publish 2 = All users (1 = internal only).
        """
        body = {
            "ticketID":   ticket_id,
            "noteType":   note_type,
            "publish":    publish,
            "title":      "ARTY Update",
            "description": note_text,
            "createDateTime": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self._post("TicketNotes", body)
            console.print(f"  [green][Autotask] Note added to ticket {ticket_id}[/green]")
            return True
        except AutotaskError as e:
            console.print(f"  [red][Autotask] add_note failed: {e}[/red]")
            return False

    def update_status(self, ticket_id: int, status_id: int) -> bool:
        """Update ticket status by ID."""
        try:
            self._patch(f"Tickets/{ticket_id}", {"id": ticket_id, "status": status_id})
            console.print(f"  [green][Autotask] Ticket {ticket_id} status → {status_id}[/green]")
            return True
        except AutotaskError as e:
            console.print(f"  [red][Autotask] update_status failed: {e}[/red]")
            return False

    def close_ticket(self, ticket_id: int, closing_note: str = "") -> bool:
        """Add closing note and mark ticket complete."""
        if closing_note:
            self.add_note(ticket_id, closing_note, publish=2)
        return self.update_status(ticket_id, STATUS_COMPLETE)

    def set_in_progress(self, ticket_id: int) -> bool:
        return self.update_status(ticket_id, STATUS_IN_PROGRESS)

    # ── ticket summary (safe for Claude — no raw PII) ─────────────────────────

    def summarise_for_arty(self, ticket: dict) -> str:
        """Build a concise summary string for ARTY to reason about.
        Company name is included (needed to find the right M365 tenant) but
        contact personal details are not passed to Claude."""
        company_name = self.get_company_name(ticket.get("companyID", 0))
        return (
            f"Ticket #{ticket.get('ticketNumber', ticket.get('id'))}\n"
            f"Company: {company_name}\n"
            f"Title: {ticket.get('title', '')}\n"
            f"Description: {ticket.get('description', '')}\n"
            f"Priority: {ticket.get('priority', 'Normal')}"
        )

    # ── polling ────────────────────────────────────────────────────────────────

    def poll_for_new_ticket(self, last_seen_ids: set, max_results: int = 10) -> dict | None:
        """Return the first ticket not in last_seen_ids, or None.
        Call on a timer — ARTY checks periodically and announces when one arrives."""
        tickets = self.get_open_tickets(max_results)
        for t in tickets:
            if t["id"] not in last_seen_ids:
                return t
        return None
