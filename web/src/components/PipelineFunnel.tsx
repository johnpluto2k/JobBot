import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { Summary } from '@/lib/api'

interface Stage {
  label: string
  value: number
  color: string
}

export function PipelineFunnel({ summary }: { summary: Summary }) {
  // Applied → Responded → Interviewed → Offers. Each stage is a subset of the
  // one before it, so the bars taper — the classic recruiting funnel.
  const responded = summary.total - summary.ghosted
  const stages: Stage[] = [
    { label: 'Applied', value: summary.total, color: 'var(--primary)' },
    { label: 'Responded', value: responded, color: 'var(--status-blue)' },
    { label: 'Interviewed', value: summary.reached_interview, color: 'var(--status-violet)' },
    { label: 'Offers', value: summary.offers, color: 'var(--status-green)' },
  ]
  const max = Math.max(summary.total, 1)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Pipeline funnel</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {stages.map((s, i) => {
          const pct = Math.round((s.value / max) * 100)
          const conv = i === 0 ? 100 : Math.round((s.value / (stages[0].value || 1)) * 100)
          return (
            <div key={s.label}>
              <div className="mb-1.5 flex items-baseline justify-between text-sm">
                <span className="font-medium text-foreground">{s.label}</span>
                <span className="tabular-nums text-muted-foreground">
                  {s.value} <span className="text-xs">· {conv}%</span>
                </span>
              </div>
              <div className="h-2.5 w-full overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full transition-[width] duration-700 ease-out"
                  style={{ width: `${Math.max(pct, s.value > 0 ? 4 : 0)}%`, background: s.color }}
                />
              </div>
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}
