import { ExternalLink } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import type { Job } from '@/lib/api'

function scoreVariant(score: number | null): 'green' | 'amber' | 'slate' {
  if (score == null) return 'slate'
  if (score >= 70) return 'green'
  if (score >= 50) return 'amber'
  return 'slate'
}

export function JobsTable({ jobs }: { jobs: Job[] }) {
  if (!jobs.length) {
    return (
      <Card className="p-10 text-center text-sm text-muted-foreground">
        No scored postings in the pipeline yet. Run a job search to populate this.
      </Card>
    )
  }
  return (
    <Card className="overflow-hidden p-0">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Role</TableHead>
            <TableHead>Company</TableHead>
            <TableHead>Location</TableHead>
            <TableHead className="text-right">ATS</TableHead>
            <TableHead className="text-right">Priority</TableHead>
            <TableHead>Legitimacy</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {jobs.map((j) => (
            <TableRow key={j.id}>
              <TableCell className="max-w-[22rem] font-medium text-foreground">
                <span className="line-clamp-1">{j.title || 'Untitled role'}</span>
                {j.recommendation && (
                  <span className="mt-0.5 block text-xs font-normal text-muted-foreground">{j.recommendation}</span>
                )}
              </TableCell>
              <TableCell className="text-muted-foreground">{j.company || '—'}</TableCell>
              <TableCell className="text-muted-foreground">{j.location || '—'}</TableCell>
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
  )
}
