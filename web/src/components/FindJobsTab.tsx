import { useState } from 'react'
import { Search, Loader2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { JobsTable } from '@/components/JobsTable'
import { KpiCard } from '@/components/KpiCard'
import { api, type SearchResult } from '@/lib/api'
import { useAsync } from '@/lib/useAsync'

export function FindJobsTab() {
  const info = useAsync(api.cycles, [])
  const [cycleKey, setCycleKey] = useState<string | null>(null)
  const [tracks, setTracks] = useState<string[]>([])
  const [location, setLocation] = useState('Washington, DC')
  const [remote, setRemote] = useState(true)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<SearchResult | null>(null)

  // Seed selections once cycles load.
  if (info.data && cycleKey === null) {
    setCycleKey(info.data.cycles[0]?.key ?? '')
    setTracks(info.data.default_tracks)
  }

  function toggleTrack(t: string) {
    setTracks((s) => (s.includes(t) ? s.filter((x) => x !== t) : [...s, t]))
  }

  async function run() {
    const cycle = info.data?.cycles.find((c) => c.key === cycleKey)
    if (!cycle || tracks.length === 0) return
    setRunning(true)
    setError(null)
    try {
      const r = await api.search({ tracks, kind: cycle.kind, location, remote, results_per: 10 })
      setResult(r)
    } catch (e) {
      setError(String((e as Error).message ?? e))
    } finally {
      setRunning(false)
    }
  }

  if (info.loading) return <div className="h-64 animate-pulse rounded-xl border border-border bg-card" />
  if (info.error || !info.data) return <Card className="p-6 text-sm text-destructive">{info.error}</Card>

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Search size={17} style={{ color: 'var(--primary)' }} /> Find jobs by cycle &amp; track
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Graduating {info.data.graduation_date}. Live-scrapes Indeed and scores each posting against your profile.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Hiring cycle</p>
            <div className="flex flex-wrap gap-2">
              {info.data.cycles.map((c) => (
                <button
                  key={c.key}
                  onClick={() => setCycleKey(c.key)}
                  className={`rounded-lg border px-3 py-1.5 text-sm transition-colors ${
                    cycleKey === c.key
                      ? 'border-transparent bg-primary text-primary-foreground'
                      : 'border-border bg-card hover:bg-muted'
                  }`}
                >
                  {c.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Career tracks</p>
            <div className="flex flex-wrap gap-2">
              {info.data.tracks.map((t) => (
                <button key={t} onClick={() => toggleTrack(t)}>
                  <Badge variant={tracks.includes(t) ? 'default' : 'secondary'} className="cursor-pointer py-1">
                    {t}
                  </Badge>
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap items-end gap-4">
            <label className="flex-1 min-w-[12rem]">
              <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Location
              </span>
              <Input value={location} onChange={(e) => setLocation(e.target.value)} />
            </label>
            <label className="flex items-center gap-2 pb-2.5 text-sm">
              <input type="checkbox" checked={remote} onChange={(e) => setRemote(e.target.checked)} className="accent-[var(--primary)]" />
              Remote-friendly
            </label>
            <Button onClick={run} disabled={running || tracks.length === 0}>
              {running ? (
                <>
                  <Loader2 className="animate-spin" /> Searching…
                </>
              ) : (
                <>
                  <Search /> Search job boards
                </>
              )}
            </Button>
          </div>
          {running && (
            <p className="text-xs text-muted-foreground">
              Scraping can take 20–60s and is occasionally rate-limited — hang tight.
            </p>
          )}
          {error && <p className="text-sm text-destructive">{error}</p>}
        </CardContent>
      </Card>

      {result && (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <KpiCard label="Scraped" value={result.scraped} accent="slate" />
            <KpiCard label="On-target" value={result.n_on_target} sub={`of ${result.n_total} scored`} accent="green" />
            <KpiCard label="Saved to pipeline" value={result.saved} accent="indigo" />
            <KpiCard label="Off-target hidden" value={result.n_total - result.n_on_target} accent="amber" />
          </div>
          <p className="text-sm text-muted-foreground">On-target matches (classified to one of your career fields):</p>
          <JobsTable jobs={result.on_target} />
        </>
      )}
    </div>
  )
}
