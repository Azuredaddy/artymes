import { useState } from 'react'
import { TopBar } from '@/components/layout/TopBar'
import { useSettings } from '@/store/settings'
import { discoverZone, testConnection } from '@/lib/autotask'
import { CheckCircle2, AlertTriangle, Loader2, Eye, EyeOff, ExternalLink } from 'lucide-react'

export function Integrations() {
  const { credentials, proxyUrl, setCredentials, setProxyUrl, setConnected, isConnected } = useSettings()

  const [form, setForm] = useState({
    username: credentials?.username ?? '',
    secret: credentials?.secret ?? '',
    integrationCode: credentials?.integrationCode ?? '',
    zoneUrl: credentials?.zoneUrl ?? '',
  })
  const [proxy, setProxy] = useState(proxyUrl)
  const [showSecret, setShowSecret] = useState(false)
  const [discovering, setDiscovering] = useState(false)
  const [testing, setTesting] = useState(false)
  const [status, setStatus] = useState<{ ok: boolean; msg: string } | null>(null)

  const handleDiscover = async () => {
    if (!form.username) return
    setDiscovering(true)
    setStatus(null)
    try {
      const url = await discoverZone(form.username)
      setForm((f) => ({ ...f, zoneUrl: url }))
      setStatus({ ok: true, msg: `Zone discovered: ${url}` })
    } catch (e: unknown) {
      setStatus({ ok: false, msg: e instanceof Error ? e.message : 'Discovery failed' })
    } finally {
      setDiscovering(false)
    }
  }

  const handleTest = async () => {
    if (!form.username || !form.secret || !form.integrationCode || !form.zoneUrl || !proxy) {
      setStatus({ ok: false, msg: 'Fill all fields including the Proxy URL before testing.' })
      return
    }
    setTesting(true)
    setStatus(null)
    try {
      const creds = { ...form }
      const ok = await testConnection(creds, proxy)
      if (ok) {
        setCredentials(creds)
        setProxyUrl(proxy)
        setConnected(true)
        setStatus({ ok: true, msg: 'Connected successfully! Credentials saved.' })
      } else {
        setStatus({ ok: false, msg: 'Connection test failed — check your credentials.' })
      }
    } catch (e: unknown) {
      setStatus({ ok: false, msg: e instanceof Error ? e.message : 'Connection failed' })
      setConnected(false)
    } finally {
      setTesting(false)
    }
  }

  const field = (label: string, key: keyof typeof form, placeholder: string, type = 'text') => (
    <div>
      <label className="block text-xs font-medium text-muted-foreground mb-1.5">{label}</label>
      {key === 'secret' ? (
        <div className="relative">
          <input
            type={showSecret ? 'text' : 'password'}
            value={form[key]}
            onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
            placeholder={placeholder}
            className="w-full bg-accent border border-border rounded-lg px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary pr-10"
          />
          <button
            type="button"
            onClick={() => setShowSecret(!showSecret)}
            className="absolute right-2.5 top-2.5 text-muted-foreground hover:text-foreground"
          >
            {showSecret ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        </div>
      ) : (
        <input
          type={type}
          value={form[key]}
          onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
          placeholder={placeholder}
          className="w-full bg-accent border border-border rounded-lg px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
        />
      )}
    </div>
  )

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <TopBar page="integrations" />
      <div className="flex-1 overflow-y-auto p-6 space-y-6 max-w-2xl">

        {/* Autotask section */}
        <div className="bg-card border border-border rounded-xl p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-foreground">Autotask PSA</h2>
            {isConnected && (
              <span className="flex items-center gap-1.5 text-xs text-emerald-400 bg-emerald-400/10 px-2.5 py-1 rounded-full">
                <CheckCircle2 className="w-3 h-3" /> Connected
              </span>
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            Create an API-only user in Autotask: Admin → Resources → API Users. The integration code is assigned during API user setup.
          </p>

          {field('API Username (email)', 'username', 'apiuser@yourdomain.com')}
          {field('API Secret / Password', 'secret', '••••••••')}
          {field('Integration Code', 'integrationCode', 'ASHJKLFDKAHKASLFH85LSA905H')}

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-medium text-muted-foreground">Zone URL</label>
              <button
                onClick={handleDiscover}
                disabled={discovering || !form.username}
                className="text-xs text-primary hover:underline flex items-center gap-1 disabled:opacity-40"
              >
                {discovering && <Loader2 className="w-3 h-3 animate-spin" />}
                Auto-discover
              </button>
            </div>
            <input
              type="text"
              value={form.zoneUrl}
              onChange={(e) => setForm((f) => ({ ...f, zoneUrl: e.target.value }))}
              placeholder="https://webservices6.autotask.net"
              className="w-full bg-accent border border-border rounded-lg px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
        </div>

        {/* Proxy / Supabase section */}
        <div className="bg-card border border-border rounded-xl p-6 space-y-4">
          <h2 className="text-sm font-semibold text-foreground">API Proxy (Required)</h2>
          <p className="text-xs text-muted-foreground">
            Browsers cannot call Autotask directly due to CORS. Deploy the included Supabase edge function at
            <code className="mx-1 bg-accent px-1.5 py-0.5 rounded text-foreground">supabase/functions/autotask-proxy/</code>
            and paste its URL here.
          </p>
          <div className="bg-accent/50 rounded-lg p-3 text-xs text-muted-foreground font-mono">
            https://YOUR-PROJECT.supabase.co/functions/v1/autotask-proxy
          </div>
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">Proxy URL</label>
            <input
              type="url"
              value={proxy}
              onChange={(e) => setProxy(e.target.value)}
              placeholder="https://your-project.supabase.co/functions/v1/autotask-proxy"
              className="w-full bg-accent border border-border rounded-lg px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
          <a
            href="https://supabase.com/docs/guides/functions"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
          >
            Supabase Edge Functions docs <ExternalLink className="w-3 h-3" />
          </a>
        </div>

        {/* Status / error */}
        {status && (
          <div className={`flex items-start gap-2 p-4 rounded-xl text-sm border ${
            status.ok
              ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
              : 'bg-red-500/10 border-red-500/20 text-red-400'
          }`}>
            {status.ok ? <CheckCircle2 className="w-4 h-4 flex-shrink-0 mt-0.5" /> : <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />}
            {status.msg}
          </div>
        )}

        <button
          onClick={handleTest}
          disabled={testing}
          className="w-full py-2.5 bg-primary text-white font-semibold text-sm rounded-lg hover:bg-primary/90 disabled:opacity-40 transition-colors flex items-center justify-center gap-2"
        >
          {testing && <Loader2 className="w-4 h-4 animate-spin" />}
          {testing ? 'Testing connection…' : 'Test & Save Connection'}
        </button>

        <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-4 text-xs text-amber-300">
          <p className="font-semibold mb-1">Training Mode — Read Only</p>
          <p>ARTY will only read tickets. No updates, notes, or status changes will be made to Autotask during training.</p>
        </div>
      </div>
    </div>
  )
}
