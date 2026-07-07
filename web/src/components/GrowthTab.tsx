import { Lightbulb, Target, Award, FolderGit2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { api } from '@/lib/api'
import { useAsync } from '@/lib/useAsync'

/** Strip **bold** markers from the Python-generated strings into plain text. */
function stripMd(s: string) {
  return s.replace(/\*\*(.+?)\*\*/g, '$1')
}

export function GrowthTab() {
  const { data, loading, error } = useAsync(api.growth, [])

  if (loading) return <div className="h-64 animate-pulse rounded-xl border border-border bg-card" />
  if (error || !data) return <Card className="p-6 text-sm text-destructive">{error}</Card>

  return (
    <div className="space-y-6">
      {/* Insights + prioritized actions */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Lightbulb size={17} style={{ color: 'var(--status-amber)' }} /> Insights
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {data.insights.map((ins, i) => (
              <p key={i} className="text-sm leading-relaxed text-foreground">
                {stripMd(ins)}
              </p>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Target size={17} style={{ color: 'var(--primary)' }} /> Do these first
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="space-y-2.5">
              {data.top_actions.map((a, i) => (
                <li key={i} className="flex gap-3 text-sm text-foreground">
                  <span
                    className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs font-semibold"
                    style={{ color: 'var(--primary)', background: 'var(--accent)' }}
                  >
                    {i + 1}
                  </span>
                  <span className="leading-relaxed">{stripMd(a)}</span>
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      </div>

      {/* Per-field plans */}
      <div className="grid gap-6 md:grid-cols-2">
        {data.per_field.map((pf) => (
          <Card key={pf.field}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">{pf.field}</CardTitle>
                {pf.is_stated_target && <Badge variant="violet">Stated target</Badge>}
              </div>
              <p className="text-xs text-muted-foreground">
                {pf.applied_count} application{pf.applied_count === 1 ? '' : 's'} in this field
              </p>
            </CardHeader>
            <CardContent className="space-y-4">
              {pf.strengths.length > 0 && (
                <div>
                  <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Strengths
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {pf.strengths.map((s) => (
                      <Badge key={s} variant="green">
                        {s}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
              {pf.gaps.length > 0 && (
                <div>
                  <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Gaps to close
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {pf.gaps.map((g) => (
                      <Badge key={g} variant="amber">
                        {g}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
              {pf.certifications.length > 0 && (
                <div>
                  <p className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    <Award size={13} /> Certifications
                  </p>
                  <ul className="space-y-1">
                    {pf.certifications.map(([name, why, effort]) => (
                      <li key={name} className="text-sm text-foreground">
                        <span className="font-medium">{name}</span>{' '}
                        <span className="text-xs text-muted-foreground">· {effort}</span>
                        <span className="block text-xs text-muted-foreground">{why}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {pf.projects.length > 0 && (
                <div>
                  <p className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    <FolderGit2 size={13} /> Portfolio projects
                  </p>
                  <ul className="list-inside list-disc space-y-1 text-sm text-foreground marker:text-muted-foreground">
                    {pf.projects.map((p) => (
                      <li key={p}>{p}</li>
                    ))}
                  </ul>
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
