import { TopBar } from '@/components/layout/TopBar'
import { useTraining } from '@/store/training'
import { TicketCard } from '@/components/tickets/TicketCard'
import { AlertCircle } from 'lucide-react'

export function NeedsReview() {
  const { tickets } = useTraining()
  const review = tickets.filter((t) => !t.artyAnalysis || t.artyAnalysis.confidence < 75)

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <TopBar page="review" />
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {review.length === 0 ? (
          <div className="flex flex-col items-center py-16 text-muted-foreground">
            <AlertCircle className="w-10 h-10 mb-3 opacity-30" />
            <p className="text-sm font-medium">No tickets needing review</p>
            <p className="text-xs mt-1">Go to Training and fetch unassigned tickets first</p>
          </div>
        ) : (
          <>
            <p className="text-xs text-muted-foreground">{review.length} tickets ARTY needs human guidance on</p>
            <div className="space-y-3">
              {review.map((t) => <TicketCard key={t.id} ticket={t} />)}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
