import { TopBar } from '@/components/layout/TopBar'
import { useTraining } from '@/store/training'
import { TicketCard } from '@/components/tickets/TicketCard'
import { CheckCircle2, Lock } from 'lucide-react'

export function ReadyQueue() {
  const { tickets } = useTraining()
  const ready = tickets.filter((t) => t.artyAnalysis && t.artyAnalysis.confidence >= 75)

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <TopBar page="ready" />
      <div className="flex-1 overflow-y-auto p-6 space-y-4">

        <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-4 flex items-center gap-3 text-sm text-amber-300">
          <Lock className="w-4 h-4 flex-shrink-0" />
          <span>Automation is locked during training. ARTY will act on these tickets once training is complete and you approve the playbooks.</span>
        </div>

        {ready.length === 0 ? (
          <div className="flex flex-col items-center py-16 text-muted-foreground">
            <CheckCircle2 className="w-10 h-10 mb-3 opacity-30" />
            <p className="text-sm font-medium">No high-confidence tickets yet</p>
            <p className="text-xs mt-1">Go to Training and fetch unassigned tickets first</p>
          </div>
        ) : (
          <>
            <p className="text-xs text-muted-foreground">{ready.length} tickets ARTY is confident it can handle (≥75%)</p>
            <div className="space-y-3">
              {ready.map((t) => <TicketCard key={t.id} ticket={t} />)}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
