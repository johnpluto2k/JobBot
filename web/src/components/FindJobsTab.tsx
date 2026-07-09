import { useState, useEffect } from 'react'
import { Search, Loader2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { ErrorNote } from '@/components/ErrorNote'
import { JobsTable } from '@/components/JobsTable'
import { KpiCard } from '@/components/KpiCard'
import { api, type SearchResult } from '@/lib/api'
import { useAsync } from '@/lib/useAsync'

const SITE_LABELS: Record<string, string> = {
  indeed: 'Indeed',
  linkedin: 'LinkedIn',
  glassdoor: 'Glassdoor',
  zip_recruiter: 'ZipRecruiter',
  google: 'Google Jobs',
}

const siteLabel = (s: string) => SITE_LABELS[s] ?? s

const STORAGE_KEY_RESULT = 'jobbot.findjobs.result'

function loadCachedResult(): SearchResult | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEY_RESULT)
    return stored ? JSON.parse(stored) : null
  } catch {
    return null
  }
}

function saveCachedResult(result: SearchResult | null) {
  try {
    if (result) {
      localStorage.setItem(STORAGE_KEY_RESULT, JSON.stringify(result))
    } else {
      localStorage.removeItem(STORAGE_KEY_RESULT)
    }
  } catch {
    // Silently fail if localStorage is full
  }
}

export function FindJobsTab() {
  const info = useAsync(api.cycles, [])
  const [cycleKey, setCycleKey] = useState<string | null>(null)
  const [tracks, setTracks] = useState<string[]>([])
  const [sites, setSites] = useState<string[]>([])
  const [resultsPer, setResultsPer] = useState(10)
  const [location, setLocation] = useState('Washington, DC')
  const [remote, setRemote] = useState(true)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<SearchResult | null>(() => loadCachedResult())
  const [resultTimestamp, setResultTimestamp] = useState<number | null>(() => {
    const cached = loadCachedResult()
    return cached ? Date.now() : null
  })

  useEffect(() => {
    if (info.data && cycleKey === null) {
      setCycleKey(info.data.cycles[0]?.key ?? '')
      setTracks(info.data.default_tracks)
      setSites(info.data.default_sites)
    }
  }, [info.data, cycleKey])

  useEffect(() => {
    saveCachedResult(result)
  }, [result])

  function toggleTrack(t: string) {
    setTracks((s) => (s.includes(t) ? s.filter((x) => x !== t) : [...s, t]))
  }

  function toggleSite(t: string) {
    setSites((s) => (s.includes(t) ? s.filter((x) => x !== t) : [...s, t]))
  }

  async function run() {
    const cycle = info.data?.cycles.find((c) => c.key === cycleKey)
    if (!cycle || tracks.length === 0 || sites.length === 0) return
    setRunning(true)
    setError(null)
    try {
      const r = await api.search({ tracks, kind: cycle.kind, location, remote, results_per: resultsPer, sites })
      setResult(r)
      setResultTimestamp(Date.now())
    } catch (e) {
      setError(String((e as Error).message ?? e))
    } finally {
      setRunning(false)
    }
  }

  if (info.loading) return <div className="h-64 animate-pulse rounded-xl border border-border bg-card" />
  if (info.error || !info.data) return <ErrorNote error={info.error ?? 'No cycle data returned.'} />

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Search size={17} style={{ color: 'var(--primary)' }} /> Find jobs by cycle &amp; track
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Graduating {info.data.graduation_date}. Live-scrapes{' '}
            {sites.length ? sites.map(siteLabel).join(', ') : 'your selected job boards'} and scores each posting
            against your profile.
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

          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Job boards</p>
            <div className="flex flex-wrap gap-2">
              {info.data.sites.map((t) => (
                <button key={t} onClick={() => toggleSite(t)}>
                  <Badge variant={sites.includes(t) ? 'default' : 'secondary'} className="cursor-pointer py-1">
                    {siteLabel(t)}
                  </Badge>
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap items-end gap-4">
            <label className="min-w-[12rem] flex-1">
              <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Location
              </span>
              <Input value={location} onChange={(e) => setLocation(e.target.value)} />
            </label>
            <label className="min-w-[12rem] flex-1">
              <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Results per role: {resultsPer}
              </span>
              <input
                type="range"
                min={5}
                max={50}
                step={5}
                value={resultsPer}
                onChange={(e) => setResultsPer(Number(e.target.value))}
                className="h-9 w-full accent-[var(--primary)]"
              />
            </label>
            <label className="flex items-center gap-2 pb-2.5 text-sm">
              <input type="checkbox" checked={remote} onChange={(e) => setRemote(e.target.checked)} className="accent-[var(--primary)]" />
              Remote-friendly
            </label>
          </div>

          {running && (
            <p className="text-xs text-muted-foreground">
              Scraping can take 20–60s and is occasionally rate-limited — hang tight.
            </p>
          )}
          {error && <ErrorNote error={error} title="Search failed." showStartHint={false} />}

          <div className="flex justify-end border-t border-border pt-4">
            <Button onClick={run} disabled={running || tracks.length === 0 || sites.length === 0}>
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
        </CardContent>
      </Card>

      {result && (
        <>
          {resultTimestamp && (
            <p className="text-xs text-muted-foreground">
              Results from {new Date(resultTimestamp).toLocaleString()} {!running && '(cached — run search to refresh)'}
            </p>
          )}
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
