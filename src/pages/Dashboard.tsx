import { TopBar } from '@/components/layout/TopBar'
import { useTraining } from '@/store/training'
import { useSettings } from '@/store/settings'
import { Brain, CheckCircle2, AlertCircle, Ticket, ArrowRight, Plug } from 'lucide-react'
import type { PageId } from '@/lib/types'

interface Props {
  onNavigate: (page: PageId) => void
}

export function Dashboard({ onNavigate }: Props) {
  const { tickets, lastFetchedAt } = useTraining()
  const { isConnected, credentials } = useSettings()

  const highConf = tickets.filter((t) => t.artyAnalysis && t.artyAnalysis.confidence >= 75)
  const lowConf = tickets.filter((t) => !t.artyAnalysis || t.artyAnalysis.confidence < 75)

  const typeBreakdown = tickets.reduce<Record<string, number>>((acc, t) => {
    const type = t.artyAnalysis?.ticketType ?? 'general'
    acc[type] = (acc[type] ?? 0) + 1
    return acc
  }, {})

  const topTypes = Object.entries(typeBreakdown)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <TopBar page="dashboard" />
      <div className="flex-1 overflow-y-auto p-6 space-y-6">

        {/* Connection alert */}
        {!isConnected && (
          <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-4 flex items-start gap-3">
            <Plug className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-amber-300">Autotask not connected</p>
              <p className="text-xs text-amber-300/70 mt-0.5">Go to Integrations to enter your API credentials, then head to Training to fetch tickets.</p>
              <button onClick={() => onNavigate('integrations')} className="mt-2 text-xs text-primary hover:underline flex items-center gap-1">
                Go to Integrations <ArrowRight className="w-3 h-3" />
              </button>
            </div>
          </div>
        )}

        {/* Stat cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: 'Total Unassigned', value: tickets.length, icon: Ticket, color: 'text-foreground', bg: 'bg-zinc-500/10' },
            { label: 'ARTY Ready', value: highConf.length, icon: CheckCircle2, color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
            { label: 'Needs Review', value: lowConf.length, icon: AlertCircle, color: 'text-orange-400', bg: 'bg-orange-500/10' },
            { label: 'Patterns Learned', value: Object.keys(typeBreakdown).length, icon: Brain, color: 'text-primary', bg: 'bg-primary/10' },
          ].map((s) => (
            <div key={s.label} className="bg-card border border-border rounded-xl p-5">
              <div className={`w-9 h-9 ${s.bg} rounded-lg flex items-center justify-center mb-3`}>
                <s.icon className={`w-5 h-5 ${s.color}`} />
              </div>
              <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
              <p className="text-xs text-muted-foreground mt-1">{s.label}</p>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-4">
          {/* Ticket type breakdown */}
          <div className="bg-card border border-border rounded-xl p-5">
            <h2 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
              <Brain className="w-4 h-4 text-primary" /> Pattern Breakdown
            </h2>
            {topTypes.length === 0 ? (
              <p className="text-sm text-muted-foreground">No tickets analysed yet — go to Training to fetch tickets.</p>
            ) : (
              <div className="space-y-3">
                {topTypes.map(([type, count]) => (
                  <div key={type}>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-foreground capitalize">{type.replace(/_/g, ' ')}</span>
                      <span className="text-muted-foreground">{count} tickets</span>
                    </div>
                    <div className="h-1.5 bg-accent rounded-full overflow-hidden">
                      <div
                        className="h-full bg-primary rounded-full"
                        style={{ width: `${(count / tickets.length) * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Quick actions */}
          <div className="bg-card border border-border rounded-xl p-5">
            <h2 className="text-sm font-semibold text-foreground mb-4">Quick Actions</h2>
            <div className="space-y-2">
              {[
                { label: 'Start training fetch', page: 'training' as PageId, desc: 'Pull unassigned tickets' },
                { label: 'View ready queue', page: 'ready' as PageId, desc: `${highConf.length} tickets ARTY can handle` },
                { label: 'Review unknowns', page: 'review' as PageId, desc: `${lowConf.length} need human input` },
                { label: 'Connect integrations', page: 'integrations' as PageId, desc: isConnected ? `Connected as ${credentials?.username}` : 'Not connected' },
              ].map((a) => (
                <button
                  key={a.page}
                  onClick={() => onNavigate(a.page)}
                  className="w-full flex items-center justify-between px-3 py-2.5 rounded-lg bg-accent hover:bg-accent/70 text-left transition-colors group"
                >
                  <div>
                    <p className="text-sm text-foreground font-medium">{a.label}</p>
                    <p className="text-xs text-muted-foreground">{a.desc}</p>
                  </div>
                  <ArrowRight className="w-4 h-4 text-muted-foreground group-hover:text-primary transition-colors" />
                </button>
              ))}
            </div>
          </div>
        </div>

        {lastFetchedAt && (
          <p className="text-xs text-muted-foreground text-center">
            Last synced {new Date(lastFetchedAt).toLocaleString()} · Training mode active · No tickets modified
          </p>
        )}
      </div>
    </div>
  )
}
