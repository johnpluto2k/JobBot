import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { STATUS_VARIANT, type Application } from '@/lib/api'

function fmtDate(iso: string | null) {
  if (!iso) return '—'
  const d = new Date(iso + 'T00:00:00')
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

export function ApplicationsTable({ apps }: { apps: Application[] }) {
  // Zero applications used to render a bare header row under the text
  // "0 companies". JobsTable already handles this case; match it.
  if (!apps.length) {
    return (
      <Card className="p-10 text-center text-sm text-muted-foreground">
        No applications logged yet. Use <span className="font-medium">Log a job</span> on
        the Companies page each time you apply — this funnel is what the coach reads.
      </Card>
    )
  }
  return (
    <Card className="overflow-hidden p-0">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Company</TableHead>
            <TableHead>Field</TableHead>
            <TableHead>Roles</TableHead>
            <TableHead className="text-center">Interviewed</TableHead>
            <TableHead>Last activity</TableHead>
            <TableHead className="text-right">Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {apps.map((a) => (
            <TableRow key={a.company}>
              <TableCell className="font-medium text-foreground">{a.company}</TableCell>
              <TableCell className="text-muted-foreground">{a.field}</TableCell>
              <TableCell className="max-w-[22rem] text-muted-foreground">
                <span className="line-clamp-1">{a.roles.length ? a.roles.join(', ') : '—'}</span>
              </TableCell>
              <TableCell className="text-center">
                {a.reached_interview ? (
                  <span style={{ color: 'var(--status-violet)' }} aria-label="Reached interview">
                    ★
                  </span>
                ) : (
                  <span className="text-muted-foreground/40">·</span>
                )}
              </TableCell>
              <TableCell className="tabular-nums text-muted-foreground">{fmtDate(a.last_seen)}</TableCell>
              <TableCell className="text-right">
                <Badge variant={STATUS_VARIANT[a.status]}>{a.status_label}</Badge>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  )
}
