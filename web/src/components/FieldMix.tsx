import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { Summary } from '@/lib/api'

export function FieldMix({ summary }: { summary: Summary }) {
  const entries = Object.entries(summary.by_field)
  const max = Math.max(...entries.map(([, f]) => f.companies), 1)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Where you're applying</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3.5">
        {entries.map(([field, stat]) => {
          const pct = Math.round((stat.companies / max) * 100)
          return (
            <div key={field}>
              <div className="mb-1 flex items-baseline justify-between text-sm">
                <span className="truncate pr-3 text-foreground">{field}</span>
                <span className="shrink-0 tabular-nums text-muted-foreground">
                  {stat.companies}
                  {stat.interviewed > 0 && (
                    <span className="ml-1.5 text-xs" style={{ color: 'var(--status-violet)' }}>
                      ★ {stat.interviewed}
                    </span>
                  )}
                </span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full"
                  style={{ width: `${Math.max(pct, 3)}%`, background: 'var(--primary)' }}
                />
              </div>
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}
