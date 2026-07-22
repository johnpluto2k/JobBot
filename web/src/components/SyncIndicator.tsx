import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertCircle, RefreshCw } from 'lucide-react'
import { api, type SyncStatus } from '@/lib/api'

const POLL_MS = 30_000

function relTime(iso: string | null): string {
  if (!iso) return 'never'
  const ms = Date.now() - new Date(iso).getTime()
  if (!Number.isFinite(ms) || ms < 0) return 'just now'
  const min = Math.floor(ms / 60_000)
  if (min < 1) return 'just now'
  if (min < 60) return `${min}m ago`
  const h = Math.floor(min / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

/** Gmail sync chip: last sync time + new items, auto-refreshing, manual run. */
export function SyncIndicator() {
  const [status, setStatus] = useState<SyncStatus | null>(null)
  const [syncing, setSyncing] = useState(false)
  // Re-render each minute so the relative timestamp stays honest between polls.
  const [, setTick] = useState(0)
  const alive = useRef(true)

  const refresh = useCallback(() => {
    api
      .syncStatus()
      .then((s) => alive.current && setStatus(s))
      .catch(() => undefined)
  }, [])

  useEffect(() => {
    alive.current = true
    refresh()
    const poll = setInterval(refresh, POLL_MS)
    const tick = setInterval(() => setTick((t) => t + 1), 60_000)
    return () => {
      alive.current = false
      clearInterval(poll)
      clearInterval(tick)
    }
  }, [refresh])

  async function syncNow() {
    setSyncing(true)
    try {
      const s = await api.syncNow()
      if (alive.current) setStatus(s)
    } catch {
      refresh()
    } finally {
      if (alive.current) setSyncing(false)
    }
  }

  if (!status) return null
  const busy = syncing || status.running
  const newItems = status.last_result?.new

  return (
    <div className="flex items-center gap-2 rounded-full border border-border bg-card py-1 pl-3 pr-1 text-xs text-muted-foreground">
      {status.last_error ? (
        <span className="inline-flex items-center gap-1 text-red-600 dark:text-red-400" title={status.last_error}>
          <AlertCircle size={13} /> sync error
        </span>
      ) : (
        <span title={status.last_sync ? new Date(status.last_sync).toLocaleString() : undefined}>
          Gmail sync: <span className="font-medium text-foreground">{busy ? 'running…' : relTime(status.last_sync)}</span>
          {!busy && newItems != null && (
            <span className={newItems > 0 ? 'ml-1 font-medium text-primary' : 'ml-1'}>
              · {newItems} new
            </span>
          )}
        </span>
      )}
      <button
        onClick={syncNow}
        disabled={busy}
        title="Sync now"
        aria-label="Sync Gmail now"
        className="rounded-full p-1.5 transition-colors hover:bg-muted disabled:opacity-50"
      >
        <RefreshCw size={13} className={busy ? 'animate-spin' : ''} />
      </button>
    </div>
  )
}
