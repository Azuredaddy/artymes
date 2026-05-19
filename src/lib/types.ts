export interface AutotaskCredentials {
  username: string
  secret: string
  integrationCode: string
  zoneUrl: string
}

export interface AppSettings {
  credentials: AutotaskCredentials | null
  proxyUrl: string
  confidenceThreshold: number
  isConnected: boolean
}

export interface Ticket {
  id: number
  ticketNumber: string
  title: string
  description: string
  status: number
  statusName?: string
  priority: number
  priorityName?: string
  queueID: number | null
  ticketType: number
  companyID: number
  companyName?: string
  contactID: number | null
  assignedResourceID: number | null
  createDateTime: string
  lastActivityDate: string
  dueDateTime: string | null
  estimatedHours: number | null
  hoursToBeScheduled: number | null
}

export interface TicketNote {
  id: number
  ticketID: number
  title: string
  description: string
  noteType: number
  publish: number
  createDateTime: string
  lastActivityDate: string
  creatorResourceID: number | null
}

export interface TicketHistory {
  id: number
  ticketID: number
  action: string
  date: string
  detail: string
  resourceID: number | null
}

export interface TicketWithDetails extends Ticket {
  notes: TicketNote[]
  history: TicketHistory[]
  artyAnalysis?: ArtyAnalysis
}

export interface ArtyAnalysis {
  ticketType: string
  confidence: number
  keywords: string[]
  suggestedPlaybook: string
  reasoning: string
  canAutomate: boolean
  automationAction?: string
}

export interface Playbook {
  id: string
  name: string
  triggerKeywords: string[]
  resolutionSteps: string[]
  automationAction: string
  confidence: number
  approved: boolean
  ticketCount: number
  createdAt: string
}

export interface TrainingSession {
  id: string
  startedAt: string
  ticketsFetched: number
  patternsFound: number
  status: 'idle' | 'fetching' | 'analysing' | 'complete' | 'error'
  error?: string
}

export type PageId = 'dashboard' | 'training' | 'ready' | 'review' | 'integrations' | 'settings'
