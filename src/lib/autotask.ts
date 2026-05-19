import type { AutotaskCredentials, Ticket, TicketNote, TicketHistory } from './types'

interface ProxyRequest {
  endpoint: string
  method: 'GET' | 'POST' | 'PATCH'
  body?: object
  credentials: AutotaskCredentials
}

async function callProxy(proxyUrl: string, req: ProxyRequest): Promise<unknown> {
  const resp = await fetch(proxyUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!resp.ok) {
    const text = await resp.text()
    throw new Error(`Proxy error ${resp.status}: ${text}`)
  }
  return resp.json()
}

export async function discoverZone(username: string): Promise<string> {
  const resp = await fetch(
    `https://webservices.autotask.net/atservicesrest/v1.0/zoneInformation?user=${encodeURIComponent(username)}`
  )
  if (!resp.ok) throw new Error('Zone discovery failed — check your username')
  const data = await resp.json() as { url: string }
  return data.url.replace(/\/$/, '')
}

export async function testConnection(
  credentials: AutotaskCredentials,
  proxyUrl: string
): Promise<boolean> {
  const result = await callProxy(proxyUrl, {
    endpoint: '/Tickets/query',
    method: 'POST',
    body: { filter: [{ op: 'gt', field: 'id', value: 0 }], MaxRecords: 1 },
    credentials,
  }) as { items?: unknown[] }
  return Array.isArray(result?.items)
}

export async function fetchUnassignedTickets(
  credentials: AutotaskCredentials,
  proxyUrl: string,
  afterId = 0
): Promise<{ items: Ticket[]; pageDetails: { nextPageUrl: string | null; count: number } }> {
  const filter: object[] = [
    { op: 'notExist', field: 'assignedResourceID' },
    { op: 'noteq', field: 'status', value: 5 },
  ]
  if (afterId > 0) filter.push({ op: 'gt', field: 'id', value: afterId })

  const result = await callProxy(proxyUrl, {
    endpoint: '/Tickets/query',
    method: 'POST',
    body: { filter },
    credentials,
  })
  return result as { items: Ticket[]; pageDetails: { nextPageUrl: string | null; count: number } }
}

export async function fetchTicketNotes(
  credentials: AutotaskCredentials,
  proxyUrl: string,
  ticketId: number
): Promise<{ items: TicketNote[] }> {
  const result = await callProxy(proxyUrl, {
    endpoint: '/TicketNotes/query',
    method: 'POST',
    body: { filter: [{ op: 'eq', field: 'ticketID', value: ticketId }] },
    credentials,
  })
  return result as { items: TicketNote[] }
}

export async function fetchTicketHistory(
  credentials: AutotaskCredentials,
  proxyUrl: string,
  ticketId: number
): Promise<{ items: TicketHistory[] }> {
  const result = await callProxy(proxyUrl, {
    endpoint: '/TicketHistory/query',
    method: 'POST',
    body: { filter: [{ op: 'eq', field: 'ticketID', value: ticketId }] },
    credentials,
  })
  return result as { items: TicketHistory[] }
}

export async function fetchCompanyName(
  credentials: AutotaskCredentials,
  proxyUrl: string,
  companyId: number
): Promise<string> {
  const result = await callProxy(proxyUrl, {
    endpoint: `/Companies/${companyId}`,
    method: 'GET',
    credentials,
  }) as { item?: { companyName?: string } }
  return result?.item?.companyName ?? `Company ${companyId}`
}
