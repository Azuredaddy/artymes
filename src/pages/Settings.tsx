import { useState } from 'react'
import { TopBar } from '@/components/layout/TopBar'
import { useSettings } from '@/store/settings'
import { useTraining } from '@/store/training'

export function Settings() {
  const { confidenceThreshold, artyName, setConfidenceThreshold, setArtyName, clearCredentials } = useSettings()
  const { clearAll } = useTraining()
  const [name, setName] = useState(artyName)
  const [threshold, setThreshold] = useState(confidenceThreshold)
  const [cleared, setCleared] = useState(false)

  const save = () => {
    setArtyName(name)
    setConfidenceThreshold(threshold)
  }

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <TopBar page="settings" />
      <div className="flex-1 overflow-y-auto p-6 space-y-6 max-w-lg">

        <div className="bg-card border border-border rounded-xl p-6 space-y-5">
          <h2 className="text-sm font-semibold text-foreground">ARTY Behaviour</h2>

          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">Assistant Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full bg-accent border border-border rounded-lg px-3 py-2.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">
              Confidence Threshold — <span className="text-primary font-semibold">{threshold}%</span>
            </label>
            <input
              type="range"
              min={40}
              max={95}
              value={threshold}
              onChange={(e) => setThreshold(Number(e.target.value))}
              className="w-full accent-blue-500"
            />
            <div className="flex justify-between text-xs text-muted-foreground mt-1">
              <span>40% (more tickets ready)</span>
              <span>95% (very strict)</span>
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              Tickets above this confidence go to Ready Queue. Below goes to Needs Review.
            </p>
          </div>

          <button
            onClick={save}
            className="w-full py-2.5 bg-primary text-white font-semibold text-sm rounded-lg hover:bg-primary/90 transition-colors"
          >
            Save Settings
          </button>
        </div>

        <div className="bg-card border border-red-500/20 rounded-xl p-6 space-y-3">
          <h2 className="text-sm font-semibold text-red-400">Danger Zone</h2>
          <p className="text-xs text-muted-foreground">These actions cannot be undone.</p>
          <button
            onClick={() => { clearAll(); setCleared(true) }}
            className="w-full py-2.5 border border-red-500/30 text-red-400 text-sm rounded-lg hover:bg-red-500/10 transition-colors"
          >
            Clear All Training Data
          </button>
          <button
            onClick={() => clearCredentials()}
            className="w-full py-2.5 border border-red-500/30 text-red-400 text-sm rounded-lg hover:bg-red-500/10 transition-colors"
          >
            Disconnect Autotask
          </button>
          {cleared && <p className="text-xs text-emerald-400">Training data cleared.</p>}
        </div>
      </div>
    </div>
  )
}
