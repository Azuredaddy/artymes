import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—'
  try {
    return new Intl.DateTimeFormat('en-GB', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    }).format(new Date(dateStr))
  } catch {
    return dateStr
  }
}

export function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

export function priorityLabel(p: number): string {
  const map: Record<number, string> = { 1: 'Critical', 2: 'High', 3: 'Medium', 4: 'Low' }
  return map[p] ?? `Priority ${p}`
}

export function priorityColor(p: number): string {
  const map: Record<number, string> = {
    1: 'text-red-400 bg-red-400/10',
    2: 'text-orange-400 bg-orange-400/10',
    3: 'text-yellow-400 bg-yellow-400/10',
    4: 'text-zinc-400 bg-zinc-400/10',
  }
  return map[p] ?? 'text-zinc-400 bg-zinc-400/10'
}

const TICKET_TYPES: Record<string, string[]> = {
  password_reset: ['password', 'reset', 'locked out', "can't login", 'cant login', 'login', 'mfa', 'authenticator', 'two factor', 'sign in', 'access denied', 'forgot password'],
  email_issue: ['email', 'outlook', 'mailbox', 'mail', 'smtp', 'inbox', 'calendar', 'teams'],
  new_user: ['new user', 'new employee', 'new starter', 'onboard', 'create account', 'new account', 'setup user'],
  offboarding: ['offboard', 'leaver', 'termination', 'disable account', 'left the company', 'remove user'],
  software_install: ['install', 'software', 'application', 'app', 'upgrade', 'update software'],
  device_issue: ['slow', 'frozen', 'not responding', 'restart', 'crash', 'blue screen', 'bsod', 'reboot', 'not working'],
  network_issue: ['network', 'wifi', 'internet', 'vpn', 'connectivity', 'no connection', 'offline'],
  printer: ['printer', 'print', 'scanning', 'scanner', 'copier'],
}

export function classifyTicket(title: string, description: string): { type: string; confidence: number; keywords: string[] } {
  const text = `${title} ${description}`.toLowerCase()
  const scores: Record<string, { count: number; matched: string[] }> = {}

  for (const [type, keywords] of Object.entries(TICKET_TYPES)) {
    const matched = keywords.filter(kw => text.includes(kw))
    if (matched.length > 0) scores[type] = { count: matched.length, matched }
  }

  if (Object.keys(scores).length === 0) {
    return { type: 'general', confidence: 20, keywords: [] }
  }

  const best = Object.entries(scores).sort((a, b) => b[1].count - a[1].count)[0]
  const confidence = Math.min(95, 40 + best[1].count * 20)
  return { type: best[0], confidence, keywords: best[1].matched }
}

export function playbookForType(type: string): string {
  const map: Record<string, string> = {
    password_reset: 'M365 Password Reset',
    email_issue: 'Email / Outlook Troubleshoot',
    new_user: 'New User Onboarding',
    offboarding: 'User Offboarding',
    software_install: 'Software Installation',
    device_issue: 'Device Reboot / Health Check',
    network_issue: 'Network Connectivity Check',
    printer: 'Printer Troubleshoot',
    general: 'Manual Review Required',
  }
  return map[type] ?? 'Manual Review Required'
}
