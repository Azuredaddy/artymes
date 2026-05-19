import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { AutotaskCredentials } from '@/lib/types'

interface SettingsState {
  credentials: AutotaskCredentials | null
  proxyUrl: string
  confidenceThreshold: number
  artyName: string
  isConnected: boolean
  setCredentials: (c: AutotaskCredentials) => void
  setProxyUrl: (url: string) => void
  setConfidenceThreshold: (v: number) => void
  setArtyName: (name: string) => void
  setConnected: (v: boolean) => void
  clearCredentials: () => void
}

export const useSettings = create<SettingsState>()(
  persist(
    (set) => ({
      credentials: null,
      proxyUrl: '',
      confidenceThreshold: 75,
      artyName: 'ARTY',
      isConnected: false,
      setCredentials: (credentials) => set({ credentials }),
      setProxyUrl: (proxyUrl) => set({ proxyUrl }),
      setConfidenceThreshold: (confidenceThreshold) => set({ confidenceThreshold }),
      setArtyName: (artyName) => set({ artyName }),
      setConnected: (isConnected) => set({ isConnected }),
      clearCredentials: () => set({ credentials: null, isConnected: false }),
    }),
    { name: 'arty-settings' }
  )
)
