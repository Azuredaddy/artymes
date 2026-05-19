import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { TicketWithDetails, Playbook } from '@/lib/types'

interface TrainingState {
  tickets: TicketWithDetails[]
  playbooks: Playbook[]
  lastFetchedAt: string | null
  totalFetched: number
  setTickets: (tickets: TicketWithDetails[]) => void
  addTickets: (tickets: TicketWithDetails[]) => void
  updateTicket: (id: number, updates: Partial<TicketWithDetails>) => void
  setPlaybooks: (playbooks: Playbook[]) => void
  updatePlaybook: (id: string, updates: Partial<Playbook>) => void
  setLastFetched: (at: string) => void
  setTotalFetched: (n: number) => void
  clearAll: () => void
}

export const useTraining = create<TrainingState>()(
  persist(
    (set) => ({
      tickets: [],
      playbooks: [],
      lastFetchedAt: null,
      totalFetched: 0,
      setTickets: (tickets) => set({ tickets }),
      addTickets: (newTickets) =>
        set((s) => {
          const existing = new Set(s.tickets.map((t) => t.id))
          const merged = [...s.tickets, ...newTickets.filter((t) => !existing.has(t.id))]
          return { tickets: merged }
        }),
      updateTicket: (id, updates) =>
        set((s) => ({
          tickets: s.tickets.map((t) => (t.id === id ? { ...t, ...updates } : t)),
        })),
      setPlaybooks: (playbooks) => set({ playbooks }),
      updatePlaybook: (id, updates) =>
        set((s) => ({
          playbooks: s.playbooks.map((p) => (p.id === id ? { ...p, ...updates } : p)),
        })),
      setLastFetched: (lastFetchedAt) => set({ lastFetchedAt }),
      setTotalFetched: (totalFetched) => set({ totalFetched }),
      clearAll: () => set({ tickets: [], playbooks: [], lastFetchedAt: null, totalFetched: 0 }),
    }),
    { name: 'arty-training' }
  )
)
