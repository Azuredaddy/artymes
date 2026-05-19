import { useState } from 'react'
import { Sidebar } from '@/components/layout/Sidebar'
import { Dashboard } from '@/pages/Dashboard'
import { Training } from '@/pages/Training'
import { ReadyQueue } from '@/pages/ReadyQueue'
import { NeedsReview } from '@/pages/NeedsReview'
import { Integrations } from '@/pages/Integrations'
import { Settings } from '@/pages/Settings'
import type { PageId } from '@/lib/types'

export default function App() {
  const [page, setPage] = useState<PageId>('dashboard')

  const renderPage = () => {
    switch (page) {
      case 'dashboard': return <Dashboard onNavigate={setPage} />
      case 'training': return <Training />
      case 'ready': return <ReadyQueue />
      case 'review': return <NeedsReview />
      case 'integrations': return <Integrations />
      case 'settings': return <Settings />
    }
  }

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      <Sidebar current={page} onChange={setPage} />
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {renderPage()}
      </main>
    </div>
  )
}
