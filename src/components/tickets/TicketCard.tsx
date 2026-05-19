import { useState } from 'react'
import { cn, formatDate, priorityLabel, priorityColor, timeAgo } from '@/lib/utils'
import type { TicketWithDetails } from '@/lib/types'
import { ChevronDown, ChevronUp, FileText, Clock, Building2, Hash, Brain, Eye } from 'lucide-react'

interface Props {
  ticket: TicketWithDetails
  onLoadDetails?: (id: number) => void
  loadingDetails?: boolean
}

export function TicketCard({ ticket, onLoadDetails, loadingDetails }: Props) {
  const [expanded, setExpanded] = useState(false)
  const analysis = ticket.artyAnalysis

  const confidenceColor = !analysis ? 'text-zinc-400' :
    analysis.confidence >= 75 ? 'text-emerald-400' :
    analysis.confidence >= 50 ? 'text-yellow-400' : 'text-orange-400'

  return (
    <div className={cn(
      'bg-card border rounded-xl transition-all',
      analysis?.confidence !== undefined && analysis.confidence >= 75
        ? 'border-emerald-500/20'
        : analysis?.confidence !== undefined && analysis.confidence >= 50
        ? 'border-yellow-500/20'
        : 'border-border'
    )}>
      {/* Header row */}
      <div className="flex items-start gap-4 p-4">
        {/* Priority indicator */}
        <div className={cn(
          'text-xs font-semibold px-2 py-1 rounded-md flex-shrink-0 mt-0.5',
          priorityColor(ticket.priority)
        )}>
          {priorityLabel(ticket.priority)}
        </div>

        {/* Main content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-foreground truncate">{ticket.title}</p>
              <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                <span className="flex items-center gap-1">
                  <Hash className="w-3 h-3" />
                  {ticket.ticketNumber || `#${ticket.id}`}
                </span>
                {ticket.companyName && (
                  <span className="flex items-center gap-1">
                    <Building2 className="w-3 h-3" />
                    {ticket.companyName}
                  </span>
                )}
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {timeAgo(ticket.createDateTime)}
                </span>
              </div>
            </div>

            {/* ARTY confidence badge */}
            {analysis && (
              <div className="flex-shrink-0 text-right">
                <div className={cn('text-sm font-bold', confidenceColor)}>
                  {analysis.confidence}%
                </div>
                <div className="text-xs text-muted-foreground">confidence</div>
              </div>
            )}
          </div>

          {/* ARTY analysis pill */}
          {analysis && (
            <div className="flex items-center gap-2 mt-2">
              <span className="flex items-center gap-1 text-xs bg-primary/10 text-primary px-2 py-0.5 rounded-full">
                <Brain className="w-3 h-3" />
                {analysis.suggestedPlaybook}
              </span>
              {analysis.keywords.slice(0, 3).map((kw) => (
                <span key={kw} className="text-xs bg-accent text-muted-foreground px-2 py-0.5 rounded-full">
                  {kw}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Expand button */}
        <button
          onClick={() => {
            if (!expanded && !ticket.notes?.length && onLoadDetails) {
              onLoadDetails(ticket.id)
            }
            setExpanded(!expanded)
          }}
          className="flex-shrink-0 p-1.5 rounded-lg hover:bg-accent text-muted-foreground transition-colors"
        >
          {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div className="border-t border-border px-4 pb-4 pt-3 space-y-4">

          {/* Description */}
          {ticket.description && (
            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5">Description</p>
              <p className="text-sm text-foreground/80 whitespace-pre-wrap leading-relaxed">{ticket.description}</p>
            </div>
          )}

          {/* ARTY reasoning */}
          {analysis && (
            <div className="bg-primary/5 border border-primary/20 rounded-lg p-3">
              <p className="text-xs font-semibold text-primary mb-1 flex items-center gap-1">
                <Brain className="w-3 h-3" /> ARTY Analysis
              </p>
              <p className="text-xs text-foreground/70">{analysis.reasoning}</p>
              <div className="mt-2 flex items-center gap-2">
                <span className="text-xs text-muted-foreground">Type:</span>
                <span className="text-xs font-medium text-foreground">{analysis.ticketType.replace(/_/g, ' ')}</span>
                {analysis.automationAction && (
                  <>
                    <span className="text-muted-foreground">·</span>
                    <span className="text-xs text-muted-foreground">Action:</span>
                    <span className="text-xs font-medium text-primary">{analysis.automationAction}</span>
                  </>
                )}
              </div>
            </div>
          )}

          {loadingDetails && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Eye className="w-3.5 h-3.5 animate-pulse" />
              Loading notes and history…
            </div>
          )}

          {/* Notes */}
          {ticket.notes?.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                Notes ({ticket.notes.length})
              </p>
              <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                {ticket.notes.map((note) => (
                  <div key={note.id} className="bg-accent/50 rounded-lg p-3">
                    {note.title && (
                      <p className="text-xs font-semibold text-foreground mb-1">{note.title}</p>
                    )}
                    <p className="text-xs text-foreground/80 whitespace-pre-wrap">{note.description}</p>
                    <p className="text-xs text-muted-foreground mt-1.5">{formatDate(note.createDateTime)}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* History */}
          {ticket.history?.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                <FileText className="w-3 h-3 inline mr-1" />
                History ({ticket.history.length} changes)
              </p>
              <div className="space-y-1 max-h-48 overflow-y-auto pr-1">
                {ticket.history.map((h) => (
                  <div key={h.id} className="flex items-start gap-2 text-xs">
                    <span className="text-muted-foreground flex-shrink-0 w-32">{formatDate(h.date)}</span>
                    <span className="text-foreground/70">{h.action}: {h.detail}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Metadata */}
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <span className="text-muted-foreground">Created: </span>
              <span className="text-foreground">{formatDate(ticket.createDateTime)}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Last activity: </span>
              <span className="text-foreground">{formatDate(ticket.lastActivityDate)}</span>
            </div>
            {ticket.dueDateTime && (
              <div>
                <span className="text-muted-foreground">Due: </span>
                <span className="text-foreground">{formatDate(ticket.dueDateTime)}</span>
              </div>
            )}
          </div>

          <div className="pt-1 border-t border-border text-xs text-amber-400/70 flex items-center gap-1.5">
            <span>Training Mode — </span>
            <span>ARTY is observing only. No changes will be made to this ticket.</span>
          </div>
        </div>
      )}
    </div>
  )
}
