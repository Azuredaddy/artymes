import { useState, useCallback } from 'react'
import { useSettings } from '@/store/settings'
import { useTraining } from '@/store/training'
import { TopBar } from '@/components/layout/TopBar'
import { TicketCard } from '@/components/tickets/TicketCard'
import { fetchUnassignedTickets, fetchTicketNotes, fetchTicketHistory } from '@/lib/autotask'
import { classifyTicket, playbookForType } from '@/lib/utils'
import type { TicketWithDetails, ArtyAnalysis } from '@/lib/types'
import { Brain, Loader2, AlertTriangle, CheckCircle2, Inbox, Filter, SortAsc } from 'lucide-react'

type SortKey = 'date' | 'priority' | 'confidence'
type FilterKey = 'all' | 'high' | 'medium' | 'low'

function analyseTicket(ticket: TicketWithDetails): ArtyAnalysis {
  const { type, confidence, keywords } = classifyTicket(ticket.title, ticket.description ?? '')
  const playbook = playbookForType(type)
  const canAutomate = ['password_reset', 'email_issue', 'device_issue'].includes(type) && confidence >= 70
  const automationMap: Record<string, string> = {
    password_reset: 'Reset via Partner Center',
    device_issue: 'Reboot via RMM',
  }

  let reasoning = `Matched ticket type "${type.replace(/_/g, ' ')}" based on keywords: ${keywords.join(', ') || 'general context'}. `
  reasoning += confidence >= 75
    ? `High confidence — ARTY should be able to handle this autonomously once authorised.`
    : confidence >= 50
    ? `Medium confidence — ARTY recognises this pattern but may need human guidance.`
    : `Low confidence — this ticket type is not yet well understood by ARTY.`

  return {
    ticketType: type,
    confidence,
    keywords,
    suggestedPlaybook: playbook,
    reasoning,
    canAutomate,
    automationAction: automationMap[type],
  }
}

export function Training() {
  const { credentials, proxyUrl, isConnected } = useSettings()
  const { tickets, addTickets, updateTicket, setLastFetched, setTotalFetched, totalFetched, lastFetchedAt } = useTraining()

  const [fetching, setFetching] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [progress, setProgress] = useState({ current: 0, total: 0 })
  const [loadingDetailsFor, setLoadingDetailsFor] = useState<number | null>(null)
  const [sortKey, setSortKey] = useState<SortKey>('date')
  const [filterKey, setFilterKey] = useState<FilterKey>('all')
  const [search, setSearch] = useState('')

  const handleFetch = useCallback(async () => {
    if (!credentials || !proxyUrl) {
      setError('Configure Autotask credentials in Integrations first.')
      return
    }
    setFetching(true)
    setError(null)

    try {
      let afterId = 0
      let allTickets: TicketWithDetails[] = []
      let page = 0

      while (true) {
        page++
        setProgress({ current: allTickets.length, total: allTickets.length + 500 })

        const result = await fetchUnassignedTickets(credentials, proxyUrl, afterId)
        const batch = result.items ?? []
        if (batch.length === 0) break

        const enriched: TicketWithDetails[] = batch.map((t) => ({
          ...t,
          notes: [],
          history: [],
          artyAnalysis: analyseTicket({ ...t, notes: [], history: [] }),
        }))

        allTickets = [...allTickets, ...enriched]
        addTickets(enriched)
        setProgress({ current: allTickets.length, total: allTickets.length })

        if (!result.pageDetails?.nextPageUrl || batch.length < 500) break
        afterId = Math.max(...batch.map((t) => t.id))
      }

      setTotalFetched(allTickets.length)
      setLastFetched(new Date().toISOString())
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unknown error during fetch')
    } finally {
      setFetching(false)
    }
  }, [credentials, proxyUrl, addTickets, setLastFetched, setTotalFetched])

  const handleLoadDetails = useCallback(async (ticketId: number) => {
    if (!credentials || !proxyUrl) return
    setLoadingDetailsFor(ticketId)
    try {
      const [notesRes, historyRes] = await Promise.all([
        fetchTicketNotes(credentials, proxyUrl, ticketId),
        fetchTicketHistory(credentials, proxyUrl, ticketId),
      ])
      const ticket = tickets.find((t) => t.id === ticketId)
      if (ticket) {
        const updated = {
          ...ticket,
          notes: notesRes.items ?? [],
          history: historyRes.items ?? [],
        }
        updateTicket(ticketId, { notes: updated.notes, history: updated.history, artyAnalysis: analyseTicket(updated) })
      }
    } catch (e) {
      console.error('Failed to load details', e)
    } finally {
      setLoadingDetailsFor(null)
    }
  }, [credentials, proxyUrl, tickets, updateTicket])

  const filtered = tickets
    .filter((t) => {
      if (filterKey === 'high') return t.artyAnalysis && t.artyAnalysis.confidence >= 75
      if (filterKey === 'medium') return t.artyAnalysis && t.artyAnalysis.confidence >= 50 && t.artyAnalysis.confidence < 75
      if (filterKey === 'low') return !t.artyAnalysis || t.artyAnalysis.confidence < 50
      return true
    })
    .filter((t) => {
      if (!search) return true
      const q = search.toLowerCase()
      return t.title.toLowerCase().includes(q) ||
        (t.companyName ?? '').toLowerCase().includes(q) ||
        (t.description ?? '').toLowerCase().includes(q)
    })
    .sort((a, b) => {
      if (sortKey === 'priority') return a.priority - b.priority
      if (sortKey === 'confidence') return (b.artyAnalysis?.confidence ?? 0) - (a.artyAnalysis?.confidence ?? 0)
      return new Date(b.createDateTime).getTime() - new Date(a.createDateTime).getTime()
    })

  const highConf = tickets.filter((t) => t.artyAnalysis && t.artyAnalysis.confidence >= 75).length
  const midConf = tickets.filter((t) => t.artyAnalysis && t.artyAnalysis.confidence >= 50 && t.artyAnalysis.confidence < 75).length
  const lowConf = tickets.filter((t) => !t.artyAnalysis || t.artyAnalysis.confidence < 50).length

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <TopBar page="training" onRefresh={handleFetch} refreshing={fetching} />

      <div className="flex-1 overflow-y-auto p-6 space-y-6">

        {/* Status cards */}
        <div className="grid grid-cols-4 gap-4">
          {[
            { label: 'Unassigned Tickets', value: totalFetched, color: 'text-foreground', sub: lastFetchedAt ? 'Last synced' : 'Not synced yet' },
            { label: 'ARTY Can Handle', value: highConf, color: 'text-emerald-400', sub: '≥75% confidence' },
            { label: 'Needs Learning', value: midConf, color: 'text-yellow-400', sub: '50–74% confidence' },
            { label: 'Unknown Type', value: lowConf, color: 'text-orange-400', sub: '<50% confidence' },
          ].map((s) => (
            <div key={s.label} className="bg-card border border-border rounded-xl p-4">
              <p className="text-xs text-muted-foreground">{s.label}</p>
              <p className={`text-2xl font-bold mt-1 ${s.color}`}>{s.value}</p>
              <p className="text-xs text-muted-foreground mt-1">{s.sub}</p>
            </div>
          ))}
        </div>

        {/* Fetch panel */}
        {tickets.length === 0 && !fetching && (
          <div className="bg-card border border-border rounded-xl p-8 text-center">
            <div className="w-14 h-14 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-4">
              <Brain className="w-7 h-7 text-primary" />
            </div>
            <h2 className="text-base font-semibold text-foreground mb-2">Ready to Train ARTY</h2>
            <p className="text-sm text-muted-foreground max-w-md mx-auto mb-4">
              ARTY will fetch all unassigned tickets from Autotask and analyse them to learn patterns.
              No tickets will be modified — this is <strong className="text-foreground">read-only</strong>.
            </p>
            {!isConnected && (
              <p className="text-xs text-amber-400 mb-4 flex items-center justify-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5" />
                Connect Autotask in Integrations before fetching
              </p>
            )}
            <button
              onClick={handleFetch}
              disabled={!isConnected || fetching}
              className="px-5 py-2.5 bg-primary text-white text-sm font-semibold rounded-lg hover:bg-primary/90 disabled:opacity-40 transition-colors"
            >
              Start Training Fetch
            </button>
          </div>
        )}

        {/* Fetching progress */}
        {fetching && (
          <div className="bg-card border border-border rounded-xl p-5 flex items-center gap-4">
            <Loader2 className="w-5 h-5 text-primary animate-spin flex-shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-medium text-foreground">Fetching unassigned tickets…</p>
              <p className="text-xs text-muted-foreground mt-0.5">{progress.current} tickets loaded so far</p>
              <div className="mt-2 h-1.5 bg-accent rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary rounded-full transition-all"
                  style={{ width: progress.total > 0 ? `${(progress.current / progress.total) * 100}%` : '30%' }}
                />
              </div>
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 text-sm text-red-400 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
            {error}
          </div>
        )}

        {/* Ticket list */}
        {tickets.length > 0 && (
          <>
            {/* Filters & search */}
            <div className="flex items-center gap-3 flex-wrap">
              <div className="relative flex-1 min-w-48">
                <input
                  type="text"
                  placeholder="Search tickets…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="w-full bg-card border border-border rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              <div className="flex items-center gap-1.5">
                <Filter className="w-3.5 h-3.5 text-muted-foreground" />
                {(['all', 'high', 'medium', 'low'] as FilterKey[]).map((f) => (
                  <button
                    key={f}
                    onClick={() => setFilterKey(f)}
                    className={`px-2.5 py-1.5 text-xs rounded-lg font-medium transition-colors ${
                      filterKey === f ? 'bg-primary/15 text-primary' : 'bg-accent text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    {f === 'all' ? 'All' : f === 'high' ? 'High Conf' : f === 'medium' ? 'Mid Conf' : 'Low Conf'}
                  </button>
                ))}
              </div>

              <div className="flex items-center gap-1.5">
                <SortAsc className="w-3.5 h-3.5 text-muted-foreground" />
                {(['date', 'priority', 'confidence'] as SortKey[]).map((s) => (
                  <button
                    key={s}
                    onClick={() => setSortKey(s)}
                    className={`px-2.5 py-1.5 text-xs rounded-lg font-medium transition-colors capitalize ${
                      sortKey === s ? 'bg-primary/15 text-primary' : 'bg-accent text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>

              <span className="text-xs text-muted-foreground ml-auto">{filtered.length} tickets</span>
            </div>

            {filtered.length === 0 ? (
              <div className="flex flex-col items-center py-12 text-muted-foreground">
                <Inbox className="w-8 h-8 mb-2" />
                <p className="text-sm">No tickets match your filter</p>
              </div>
            ) : (
              <div className="space-y-3">
                {filtered.map((ticket) => (
                  <TicketCard
                    key={ticket.id}
                    ticket={ticket}
                    onLoadDetails={handleLoadDetails}
                    loadingDetails={loadingDetailsFor === ticket.id}
                  />
                ))}
              </div>
            )}

            <div className="flex items-center justify-between pt-2 text-xs text-muted-foreground">
              <span className="flex items-center gap-1.5 text-emerald-400">
                <CheckCircle2 className="w-3.5 h-3.5" />
                Training mode active — all data is read-only
              </span>
              <button onClick={handleFetch} disabled={fetching} className="text-primary hover:underline">
                Sync more tickets
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
