import { useState } from 'react'
import { Loader2, Plus, Check } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { api } from '@/lib/api'

// CLAUDE.md calls manual intake "the primary way to log jobs", but until now the
// only way to do it was the CLI (`python -m job_bot.intake ...`) - the sole caller
// of api.intake in the whole app was the "Link to application" button on a
// generated resume. Logging a job you just applied to is the single most frequent
// action in this system, so it belongs on screen.
const PORTALS = ['linkedin', 'indeed', 'handshake', 'workday', 'greenhouse',
  'glassdoor', 'ziprecruiter', 'jobright', 'smith', 'email', 'other']
const STATUSES = ['applied', 'interview', 'rejected', 'offer', 'saved']

interface Props {
  /** Called after a successful save so the caller can refetch its data. */
  onLogged?: () => void
  /** Button text when collapsed. */
  label?: string
}

function todayIso() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export function LogJobForm({ onLogged, label = 'Log a job' }: Props) {
  const [open, setOpen] = useState(false)
  const [url, setUrl] = useState('')
  const [company, setCompany] = useState('')
  const [title, setTitle] = useState('')
  const [portal, setPortal] = useState('linkedin')
  const [status, setStatus] = useState('applied')
  const [appliedOn, setAppliedOn] = useState(todayIso)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState<string | null>(null)

  // The URL is optional: plenty of applications go through a portal whose
  // posting link isn't handy, and a required field meant they never got logged.
  const ready = company.trim() && title.trim()

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!ready || saving) return
    setSaving(true)
    setError(null)
    setSaved(null)
    try {
      const res = await api.track({
        url: url.trim() || undefined, company: company.trim(), title: title.trim(), portal, status,
        applied_on: appliedOn || undefined,
      })
      // The API answers validation failures with HTTP 200 and an {error} body, so
      // checking response.ok alone would show a success that never happened.
      if (res?.error) {
        setError(res.error)
        return
      }
      setSaved(`${res.company_name ?? company} — ${res.job_title ?? title}`)
      setUrl(''); setCompany(''); setTitle(''); setStatus('applied'); setAppliedOn(todayIso())
      onLogged?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  if (!open) {
    return (
      <div className="flex items-center gap-3">
        <Button onClick={() => setOpen(true)}>
          <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
          {label}
        </Button>
        {saved && (
          <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <Check className="h-4 w-4" aria-hidden="true" />
            Logged {saved}
          </span>
        )}
      </div>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Log a job you applied to</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="grid gap-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="grid gap-1 text-sm">
              <span className="text-muted-foreground">Company</span>
              <Input value={company} onChange={(e) => setCompany(e.target.value)}
                placeholder="KPMG" autoFocus required />
            </label>
            <label className="grid gap-1 text-sm">
              <span className="text-muted-foreground">Job title</span>
              <Input value={title} onChange={(e) => setTitle(e.target.value)}
                placeholder="IT Audit Associate" required />
            </label>
          </div>
          <label className="grid gap-1 text-sm">
            <span className="text-muted-foreground">Posting URL <span className="text-xs">(optional)</span></span>
            <Input value={url} onChange={(e) => setUrl(e.target.value)}
              placeholder="https://..." inputMode="url" />
          </label>
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="grid gap-1 text-sm">
              <span className="text-muted-foreground">Where you found it</span>
              <select value={portal} onChange={(e) => setPortal(e.target.value)}
                className="h-9 rounded-md border border-input bg-transparent px-3 text-sm">
                {PORTALS.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </label>
            <label className="grid gap-1 text-sm">
              <span className="text-muted-foreground">Status</span>
              <select value={status} onChange={(e) => setStatus(e.target.value)}
                className="h-9 rounded-md border border-input bg-transparent px-3 text-sm">
                {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
            <label className="grid gap-1 text-sm">
              <span className="text-muted-foreground">Applied on</span>
              <Input type="date" value={appliedOn} max={todayIso()}
                onChange={(e) => setAppliedOn(e.target.value)} />
            </label>
          </div>

          {error && (
            <p role="alert" className="text-sm text-red-600">{error}</p>
          )}

          <div className="flex items-center gap-2">
            <Button type="submit" disabled={!ready || saving}>
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />}
              {saving ? 'Logging…' : 'Log it'}
            </Button>
            <Button type="button" variant="outline" onClick={() => { setOpen(false); setError(null) }}>
              Cancel
            </Button>
            <span className="text-xs text-muted-foreground">
              Re-logging the same URL (or company + title) updates that application instead of duplicating it.
            </span>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}
