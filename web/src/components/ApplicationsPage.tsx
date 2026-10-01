import { Fragment, useState } from 'react'
import { ChevronDown, ChevronRight, EyeOff, Loader2, Mail, RefreshCw } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ErrorNote } from '@/components/ErrorNote'
import { LogJobForm } from '@/components/LogJobForm'
import { TableToolbar } from '@/components/TableToolbar'
import {
  api,
  STATUS_VARIANT,
  type Application,
  type Position,
  type PositionStatus,
  type StatusKey,
} from '@/lib/api'
import { matches } from '@/lib/search'
import { useAsync } from '@/lib/useAsync'

// Date-only strings parse as UTC midnight; anchor to local midnight so a US
// user doesn't see every date one day early.
function fmtDate(iso: string | null, withYear = false) {
  if (!iso) return '—'
  return new Date(`${iso}T00:00:00`).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    ...(withYear ? { year: 'numeric' } : {}),
  })
}

const STATUS_ORDER: StatusKey[] = ['interviewing', 'in_review', 'offer', 'ghosted', 'rejected']
const STATUS_TEXT: Record<StatusKey, string> = {
  offer: 'Offer',
  interviewing: 'Interviewing',
  in_review: 'In review',
  ghosted: 'Ghosted',
  rejected: 'Rejected',
}

const POSITION_VARIANT: Record<PositionStatus, 'green' | 'violet' | 'blue' | 'amber' | 'red'> = {
  applied: 'blue',
  assessment: 'amber',
  interview: 'violet',
  rejected: 'red',
  offer: 'green',
}
const POSITION_TEXT: Record<PositionStatus, string> = {
  applied: 'Applied',
  assessment: 'Assessment',
  interview: 'Interview',
  rejected: 'Rejected',
  offer: 'Offer',
}
const EDITABLE: PositionStatus[] = ['applied', 'interview', 'rejected', 'offer']

const SOURCE_TEXT: Record<Position['source'], string> = {
  logged: 'Logged',
  gmail: 'From Gmail',
  imported: 'Imported',
}

type Filter = 'active' | 'all' | StatusKey

/** Applications tracker: one row per company, expandable to its positions. */
export function ApplicationsPage({
  refreshToken = 0,
  onChanged,
}: {
  /** Changes when data moved elsewhere (a background Gmail sync) — refetch. */
  refreshToken?: number
  /** Called after an edit here, so the rest of the dashboard refetches too. */
  onChanged?: () => void
}) {
  const [version, setVersion] = useState(0)
  const [allHistory, setAllHistory] = useState(false)
  const [filter, setFilter] = useState<Filter>('active')
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState<Set<string>>(new Set())
  const [syncing, setSyncing] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const apps = useAsync(() => api.applications(allHistory), [version, allHistory, refreshToken])
  const summary = useAsync(api.summary, [])
  const hidden = useAsync(api.hiddenCompanies, [version, refreshToken])
  const since = summary.data?.since

  function refresh() {
    // The parent bumps refreshToken in response; without a parent, refetch here.
    if (onChanged) onChanged()
    else setVersion((v) => v + 1)
  }

  async function syncGmail() {
    setSyncing(true)
    setActionError(null)
    try {
      const s = await api.syncNow()
      if (s.last_error) setActionError(`Gmail sync: ${s.last_error}`)
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err))
    } finally {
      setSyncing(false)
      refresh()
    }
  }

  // Every mutation goes through here: one spinner key, one error slot, one refetch.
  async function act(key: string, fn: () => Promise<{ error?: string } | undefined>) {
    setBusy(key)
    setActionError(null)
    try {
      const res = await fn()
      if (res?.error) setActionError(res.error)
      else refresh()
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }

  const all = apps.data ?? []
  const counts: Record<string, number> = { all: all.length, active: 0 }
  for (const a of all) {
    counts[a.status] = (counts[a.status] ?? 0) + 1
    if (a.status === 'in_review' || a.status === 'interviewing' || a.status === 'offer') counts.active += 1
  }
  const openPositions = all.reduce((n, a) => n + (a.status === 'rejected' ? 0 : a.open_positions), 0)

  const shown = all
    .filter((a) =>
      filter === 'all'
        ? true
        : filter === 'active'
          ? a.status === 'in_review' || a.status === 'interviewing' || a.status === 'offer'
          : a.status === filter,
    )
    .filter((a) => matches([a.company, a.field, ...a.roles, ...a.positions_detail.map((p) => p.role)], query))
    .sort((x, y) => {
      const rank = STATUS_ORDER.indexOf(x.status) - STATUS_ORDER.indexOf(y.status)
      if (filter === 'all' && rank) return rank
      // Newest application first — what you just sent is what you're looking for.
      return (y.last_applied ?? y.last_seen ?? '').localeCompare(x.last_applied ?? x.last_seen ?? '')
    })

  function toggle(company: string) {
    setOpen((prev) => {
      const next = new Set(prev)
      if (next.has(company)) next.delete(company)
      else next.add(company)
      return next
    })
  }

  const chips: { key: Filter; label: string }[] = [
    { key: 'active', label: 'Active' },
    ...STATUS_ORDER.map((k) => ({ key: k as Filter, label: STATUS_TEXT[k] })),
    { key: 'all', label: 'All' },
  ]

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          <span className="font-medium text-foreground">{all.length}</span> companies ·{' '}
          <span className="font-medium text-foreground">{openPositions}</span> open positions ·{' '}
          {allHistory || !since ? 'all history' : `since ${fmtDate(since, true)}`}. Built from what you log plus
          application receipts, interviews and rejections in Gmail.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          {since && (
            <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <input type="checkbox" checked={allHistory} onChange={(e) => setAllHistory(e.target.checked)} />
              Include older history
            </label>
          )}
          <Button variant="outline" size="sm" onClick={syncGmail} disabled={syncing}>
            <RefreshCw className={syncing ? 'animate-spin' : ''} aria-hidden="true" />
            {syncing ? 'Checking Gmail…' : 'Check Gmail now'}
          </Button>
        </div>
      </div>

      <LogJobForm onLogged={refresh} label="Log an application" />

      <TableToolbar
        value={query}
        onChange={setQuery}
        placeholder="Search company, role, field…"
        shown={shown.length}
        total={all.length}
      >
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter by status">
          {chips.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setFilter(key)}
              aria-pressed={filter === key}
              className={`rounded-full border px-2.5 py-1 text-xs transition-colors ${
                filter === key
                  ? 'border-primary bg-primary/10 font-medium text-primary'
                  : 'border-border text-muted-foreground hover:bg-muted'
              }`}
            >
              {label} <span className="tabular-nums opacity-70">{counts[key] ?? 0}</span>
            </button>
          ))}
        </div>
      </TableToolbar>

      {actionError && <ErrorNote error={actionError} />}

      {apps.error && !apps.data ? (
        <ErrorNote error={apps.error} />
      ) : apps.loading && !apps.data ? (
        <div className="h-64 animate-pulse rounded-xl border border-border bg-card" />
      ) : !shown.length ? (
        <Card className="p-10 text-center text-sm text-muted-foreground">
          {all.length
            ? 'Nothing matches this filter.'
            : 'No applications yet this season. Log one above, or check Gmail for receipts.'}
        </Card>
      ) : (
        <Card className="overflow-hidden p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-8" />
                <TableHead>Company</TableHead>
                <TableHead>Latest role</TableHead>
                <TableHead>Applied</TableHead>
                <TableHead className="hidden md:table-cell">Last activity</TableHead>
                <TableHead className="text-right">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {shown.map((a) => (
                <CompanyRows
                  key={a.company}
                  app={a}
                  expanded={open.has(a.company)}
                  onToggle={() => toggle(a.company)}
                  busy={busy}
                  act={act}
                />
              ))}
            </TableBody>
          </Table>
        </Card>
      )}

      {!!hidden.data?.length && (
        <p className="text-xs text-muted-foreground">
          Hidden as not an application:{' '}
          {hidden.data.map((c, i) => (
            <Fragment key={c}>
              {i > 0 && ', '}
              {c}{' '}
              <button
                className="underline underline-offset-2 hover:text-foreground"
                disabled={busy === `unhide:${c}`}
                onClick={() => act(`unhide:${c}`, () => api.hideCompany(c, false))}
              >
                restore
              </button>
            </Fragment>
          ))}
        </p>
      )}
    </div>
  )
}

function CompanyRows({
  app: a,
  expanded,
  onToggle,
  busy,
  act,
}: {
  app: Application
  expanded: boolean
  onToggle: () => void
  busy: string | null
  act: (key: string, fn: () => Promise<{ error?: string } | undefined>) => void
}) {
  const positions = a.positions_detail
  const latest = positions.find((p) => p.role) ?? null
  const more = positions.length - (latest ? 1 : 0)
  const Chevron = expanded ? ChevronDown : ChevronRight

  return (
    <Fragment>
      <TableRow className="cursor-pointer" onClick={onToggle} aria-expanded={expanded}>
        <TableCell className="pr-0 text-muted-foreground">
          <Chevron size={16} aria-hidden="true" />
        </TableCell>
        <TableCell className="font-medium text-foreground">
          {a.company}
          <span className="block text-xs font-normal text-muted-foreground">{a.field}</span>
        </TableCell>
        <TableCell className="max-w-[22rem] text-muted-foreground">
          <span className="line-clamp-1">{latest?.role ?? (a.roles[0] || '—')}</span>
          {more > 0 && (
            <span className="text-xs">
              +{more} more position{more > 1 ? 's' : ''}
            </span>
          )}
        </TableCell>
        <TableCell className="tabular-nums text-muted-foreground">{fmtDate(a.last_applied)}</TableCell>
        <TableCell className="hidden tabular-nums text-muted-foreground md:table-cell">
          {fmtDate(a.last_seen)}
        </TableCell>
        <TableCell className="text-right">
          {a.reached_interview && a.status !== 'interviewing' && (
            <span className="mr-1.5" style={{ color: 'var(--status-violet)' }} title="Reached an interview">
              ★
            </span>
          )}
          {a.reapplied && (
            <Badge
              variant="outline"
              className="mr-1.5 text-muted-foreground"
              title="An earlier application here was rejected; this is a new one"
            >
              Re-applied
            </Badge>
          )}
          <Badge variant={STATUS_VARIANT[a.status]}>{a.status_label}</Badge>
        </TableCell>
      </TableRow>
      {expanded && (
        <TableRow className="bg-muted/30 hover:bg-muted/30">
          <TableCell />
          <TableCell colSpan={5} className="py-3">
            <ul className="space-y-2">
              {positions.length === 0 && (
                <li className="text-sm text-muted-foreground">
                  No specific position on file — this company is here because of an interview or rejection email.
                </li>
              )}
              {positions.map((p, i) => (
                <PositionRow key={`${p.job_id ?? p.gmail_id ?? i}`} company={a.company} p={p} busy={busy} act={act} />
              ))}
            </ul>
            <div className="mt-3 flex justify-end">
              <Button
                variant="ghost"
                size="sm"
                disabled={busy === `hide:${a.company}`}
                title="Remove this company from the tracker (e.g. a scam invite or a mailing list)"
                onClick={() => act(`hide:${a.company}`, () => api.hideCompany(a.company))}
              >
                <EyeOff aria-hidden="true" /> Not an application
              </Button>
            </div>
          </TableCell>
        </TableRow>
      )}
    </Fragment>
  )
}

function PositionRow({
  company,
  p,
  busy,
  act,
}: {
  company: string
  p: Position
  busy: string | null
  act: (key: string, fn: () => Promise<{ error?: string } | undefined>) => void
}) {
  const key = `pos:${p.job_id ?? p.gmail_id ?? p.role}`
  const working = busy === key
  const mailLink = p.gmail_id ? `https://mail.google.com/mail/u/0/#all/${p.gmail_id.split(':').pop()}` : null
  const link = p.url && p.url.startsWith('http') ? p.url : mailLink

  function change(status: string) {
    if (p.source === 'logged' && p.job_id != null) {
      act(key, () => api.setPositionStatus(p.job_id as number, status))
    } else {
      // A Gmail receipt becomes a logged position the first time you edit it.
      act(key, () =>
        api.track({
          company,
          title: p.role ?? undefined,
          status,
          applied_on: p.applied_on ?? undefined,
          gmail_id: p.gmail_id ?? undefined,
        }),
      )
    }
  }

  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
      <span className="min-w-0 flex-1">
        {link ? (
          <a
            href={link}
            target="_blank"
            rel="noreferrer"
            className="text-foreground underline-offset-4 hover:underline"
            onClick={(e) => e.stopPropagation()}
          >
            {p.role ?? <span className="italic text-muted-foreground">Role not named in the email</span>}
          </a>
        ) : (
          <span className="text-foreground">{p.role ?? 'Role not recorded'}</span>
        )}
        <span className="ml-2 inline-flex items-center gap-1 text-xs text-muted-foreground">
          {p.source === 'gmail' && <Mail size={12} aria-hidden="true" />}
          {SOURCE_TEXT[p.source]}
          {p.applied_on && <> · applied {fmtDate(p.applied_on, true)}</>}
        </span>
      </span>
      {working && <Loader2 size={14} className="animate-spin text-muted-foreground" aria-hidden="true" />}
      {p.source === 'imported' ? (
        <Badge variant={POSITION_VARIANT[p.status]}>{POSITION_TEXT[p.status]}</Badge>
      ) : (
        <select
          value={p.status === 'assessment' ? 'applied' : p.status}
          disabled={working}
          aria-label={`Status for ${p.role ?? 'this position'}`}
          onClick={(e) => e.stopPropagation()}
          onChange={(e) => change(e.target.value)}
          className="h-8 rounded-md border border-input bg-card px-2 text-xs"
        >
          {EDITABLE.map((s) => (
            <option key={s} value={s}>
              {p.status === 'assessment' && s === 'applied' ? 'Assessment' : POSITION_TEXT[s]}
            </option>
          ))}
        </select>
      )}
    </li>
  )
}
