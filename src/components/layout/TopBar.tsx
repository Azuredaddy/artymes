import type { PageId } from '@/lib/types'
import { useTraining } from '@/store/training'
import { RefreshCw } from 'lucide-react'

const PAGE_TITLES: Record<PageId, string> = {
  dashboard: 'Dashboard',
  training: 'Training — Learn from Unassigned Tickets',
  ready: 'Ready Queue',
  review: 'Needs Review',
  integrations: 'Integrations',
  settings: 'Settings',
}

interface Props {
  page: PageId
  onRefresh?: () => void
  refreshing?: boolean
}

export function TopBar({ page, onRefresh, refreshing }: Props) {
  const { lastFetchedAt, totalFetched } = useTraining()

  return (
    <header className="flex items-center justify-between px-6 py-4 border-b border-border bg-card/50">
      <div>
        <h1 className="text-base font-semibold text-foreground">{PAGE_TITLES[page]}</h1>
        {lastFetchedAt && (
          <p className="text-xs text-muted-foreground mt-0.5">
            Last synced {new Date(lastFetchedAt).toLocaleTimeString()} — {totalFetched} tickets loaded
          </p>
        )}
      </div>
      {onRefresh && (
        <button
          onClick={onRefresh}
          disabled={refreshing}
          className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium bg-primary/10 hover:bg-primary/20 text-primary rounded-lg transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
          {refreshing ? 'Syncing…' : 'Sync Now'}
        </button>
      )}
    </header>
  )
}
