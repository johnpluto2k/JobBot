import { useMemo, useState } from 'react'
import { ExternalLink, ArrowDown, ArrowUp } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { TableToolbar } from '@/components/TableToolbar'
import { matches } from '@/lib/search'
import type { Job } from '@/lib/api'

type SortKey = 'priority' | 'ats_score' | 'company' | 'title'

function scoreVariant(score: number | null): 'green' | 'amber' | 'slate' {
  if (score == null) return 'slate'
  if (score >= 70) return 'green'
  if (score >= 50) return 'amber'
  return 'slate'
}

export function JobsTable({ jobs }: { jobs: Job[] }) {
  const [query, setQuery] = useState('')
  const [sortKey, setSortKey] = useState<SortKey>('priority')
  const [asc, setAsc] = useState(false)

  const visible = useMemo(() => {
    const filtered = jobs.filter((j) =>
      matches([j.title, j.company, j.location, j.legit_grade, j.recommendation], query))
    const dir = asc ? 1 : -1
    return [...filtered].sort((a, b) => {
      if (sortKey === 'company' || sortKey === 'title') {
        return dir * (a[sortKey] || '').localeCompare(b[sortKey] || '')
      }
      return dir * ((a[sortKey] ?? -1) - (b[sortKey] ?? -1))
    })
  }, [jobs, query, sortKey, asc])

  function header(label: string, key: SortKey, className = '') {
    const active = sortKey === key
    return (
      <TableHead className={className}>
        <button
          type="button"
          onClick={() => (active ? setAsc(!asc) : (setSortKey(key), setAsc(false)))}
          aria-sort={active ? (asc ? 'ascending' : 'descending') : 'none'}
          className="inline-flex items-center gap-1 transition-colors hover:text-foreground"
        >
          {label}
          {active && (asc ? <ArrowUp size={12} aria-hidden="true" /> : <ArrowDown size={12} aria-hidden="true" />)}
        </button>
      </TableHead>
    )
  }

  if (!jobs.length) {
    return (
      <Card className="p-10 text-center text-sm text-muted-foreground">
        No scored postings in the pipeline yet. The company watcher fills this in
        automatically, or run a job search.
      </Card>
    )
  }
  return (
    <div className="space-y-3">
      <TableToolbar
        value={query}
        onChange={setQuery}
        placeholder="Search roles, companies, locations…"
        shown={visible.length}
        total={jobs.length}
      />
      {!visible.length ? (
        <Card className="p-10 text-center text-sm text-muted-foreground">
          No postings match “{query}”.
        </Card>
      ) : (
    <Card className="overflow-hidden p-0">
      <Table>
        <TableHeader>
          <TableRow>
            {header('Role', 'title')}
            {header('Company', 'company')}
            {header('ATS', 'ats_score', 'text-right')}
            {header('Priority', 'priority', 'text-right')}
            <TableHead>Legitimacy</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {visible.map((j) => (
            <TableRow key={j.id}>
              <TableCell className="max-w-[22rem] font-medium text-foreground">
                <span className="line-clamp-1">{j.title || 'Untitled role'}</span>
                {j.recommendation && (
                  <span className="mt-0.5 block text-xs font-normal text-muted-foreground">{j.recommendation}</span>
                )}
              </TableCell>
              <TableCell className="text-muted-foreground">
                {j.company || '—'}
                {j.location && <span className="block text-xs text-muted-foreground">{j.location}</span>}
              </TableCell>
              <TableCell className="text-right">
                <Badge variant={scoreVariant(j.ats_score)} className="tabular-nums">
                  {j.ats_score != null ? Math.round(j.ats_score) : '—'}
                </Badge>
              </TableCell>
              <TableCell className="text-right tabular-nums text-muted-foreground">
                {j.priority != null ? Math.round(j.priority) : '—'}
              </TableCell>
              <TableCell className="whitespace-nowrap text-muted-foreground">{j.legit_grade || '—'}</TableCell>
              <TableCell className="text-right">
                {j.url && (
                  <a
                    href={j.url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center text-muted-foreground transition-colors hover:text-primary"
                    aria-label="Open posting"
                  >
                    <ExternalLink size={16} />
                  </a>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
      )}
    </div>
  )
}
