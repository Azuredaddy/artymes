import { cn } from '@/lib/utils'
import type { PageId } from '@/lib/types'
import { useSettings } from '@/store/settings'
import { useTraining } from '@/store/training'
import {
  LayoutDashboard, Brain, CheckCircle2, AlertCircle,
  Plug, Settings, Bot, Wifi, WifiOff,
} from 'lucide-react'

const NAV: { id: PageId; label: string; icon: React.ElementType }[] = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'training', label: 'Training', icon: Brain },
  { id: 'ready', label: 'Ready Queue', icon: CheckCircle2 },
  { id: 'review', label: 'Needs Review', icon: AlertCircle },
  { id: 'integrations', label: 'Integrations', icon: Plug },
  { id: 'settings', label: 'Settings', icon: Settings },
]

interface Props {
  current: PageId
  onChange: (id: PageId) => void
}

export function Sidebar({ current, onChange }: Props) {
  const { isConnected, artyName } = useSettings()
  const { tickets } = useTraining()

  const readyCount = tickets.filter(
    (t) => t.artyAnalysis && t.artyAnalysis.confidence >= 75
  ).length
  const reviewCount = tickets.filter(
    (t) => !t.artyAnalysis || t.artyAnalysis.confidence < 75
  ).length

  const badges: Partial<Record<PageId, number>> = {
    ready: readyCount,
    review: reviewCount,
  }

  return (
    <aside className="flex flex-col w-60 min-h-screen bg-card border-r border-border">
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 py-5 border-b border-border">
        <div className="w-9 h-9 rounded-xl bg-primary/20 flex items-center justify-center flex-shrink-0">
          <Bot className="w-5 h-5 text-primary" />
        </div>
        <div>
          <p className="font-bold text-foreground leading-none">{artyName}</p>
          <p className="text-xs text-muted-foreground mt-0.5">AI Ticket Assistant</p>
        </div>
      </div>

      {/* Connection badge */}
      <div className="px-4 py-3 border-b border-border">
        <div className={cn(
          'flex items-center gap-2 text-xs px-3 py-1.5 rounded-md',
          isConnected
            ? 'bg-emerald-500/10 text-emerald-400'
            : 'bg-zinc-500/10 text-zinc-400'
        )}>
          {isConnected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
          {isConnected ? 'Autotask Connected' : 'Not Connected'}
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {NAV.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => onChange(id)}
            className={cn(
              'w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
              current === id
                ? 'bg-primary/15 text-primary'
                : 'text-muted-foreground hover:bg-accent hover:text-foreground'
            )}
          >
            <span className="flex items-center gap-3">
              <Icon className="w-4 h-4 flex-shrink-0" />
              {label}
            </span>
            {badges[id] !== undefined && badges[id]! > 0 && (
              <span className={cn(
                'text-xs px-1.5 py-0.5 rounded-full font-semibold',
                id === 'ready' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-orange-500/20 text-orange-400'
              )}>
                {badges[id]}
              </span>
            )}
          </button>
        ))}
      </nav>

      {/* Training mode notice */}
      <div className="px-4 pb-5">
        <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg px-3 py-2.5 text-xs text-amber-300">
          <p className="font-semibold mb-0.5">Training Mode Active</p>
          <p className="text-amber-300/70">Read-only — no tickets will be changed</p>
        </div>
      </div>
    </aside>
  )
}
