import { useState } from 'react'
import { Gift, Trophy } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { api } from '@/lib/api'
import { useAsync } from '@/lib/useAsync'

function usd(n: number) {
  return `$${Math.round(n).toLocaleString()}`
}

function WeightSlider({
  label,
  value,
  onChange,
}: {
  label: string
  value: number
  onChange: (v: number) => void
}) {
  return (
    <label className="flex-1">
      <div className="mb-1 flex justify-between text-xs">
        <span className="font-medium text-foreground">{label}</span>
        <span className="tabular-nums text-muted-foreground">{value.toFixed(2)}</span>
      </div>
      <input
        type="range"
        min={0}
        max={1}
        step={0.05}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-[var(--primary)]"
      />
    </label>
  )
}

export function OffersTab() {
  const [w, setW] = useState({ money: 0.5, growth: 0.25, fit: 0.25 })
  const { data, loading, error } = useAsync(() => api.offers(w), [w.money, w.growth, w.fit])

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">Your priorities</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4 sm:flex-row">
          <WeightSlider label="Money" value={w.money} onChange={(v) => setW((s) => ({ ...s, money: v }))} />
          <WeightSlider label="Growth" value={w.growth} onChange={(v) => setW((s) => ({ ...s, growth: v }))} />
          <WeightSlider label="Fit" value={w.fit} onChange={(v) => setW((s) => ({ ...s, fit: v }))} />
        </CardContent>
      </Card>

      {loading ? (
        <div className="h-40 animate-pulse rounded-xl border border-border bg-card" />
      ) : error ? (
        <Card className="p-6 text-sm text-destructive">{error}</Card>
      ) : !data || data.offers.length === 0 ? (
        <Card className="flex flex-col items-center gap-2 p-10 text-center">
          <Gift size={28} className="text-muted-foreground/50" />
          <p className="font-medium text-foreground">No open offers yet</p>
          <p className="text-sm text-muted-foreground">
            When an offer lands, log it via the CLI or Streamlit tool and it'll rank here, COL-adjusted.
          </p>
        </Card>
      ) : (
        <>
          {data.winner && (
            <Card className="border-[color:var(--status-green)]/30" style={{ background: 'var(--status-green-bg)' }}>
              <CardContent className="flex items-center gap-3 py-4">
                <Trophy size={20} style={{ color: 'var(--status-green)' }} />
                <div className="text-sm">
                  <span className="font-semibold text-foreground">Top pick: {data.winner.company}</span>{' '}
                  <span className="text-muted-foreground">
                    — score {data.winner.score}, COL-adjusted {usd(data.winner.adjusted_comp)}
                  </span>
                </div>
              </CardContent>
            </Card>
          )}
          <Card className="overflow-hidden p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>#</TableHead>
                  <TableHead>Company</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead className="text-right">Total comp</TableHead>
                  <TableHead className="text-right">COL-adjusted</TableHead>
                  <TableHead className="text-right">Score</TableHead>
                  <TableHead>Deadline</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.offers.map((o, i) => (
                  <TableRow key={o.company + i}>
                    <TableCell className="text-muted-foreground">{i + 1}</TableCell>
                    <TableCell className="font-medium text-foreground">{o.company}</TableCell>
                    <TableCell className="text-muted-foreground">{o.role_title ?? '—'}</TableCell>
                    <TableCell className="text-right tabular-nums">{usd(o.total_comp)}</TableCell>
                    <TableCell className="text-right tabular-nums">{usd(o.adjusted_comp)}</TableCell>
                    <TableCell className="text-right">
                      <Badge variant={i === 0 ? 'green' : 'slate'} className="tabular-nums">
                        {o.score}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{o.deadline ?? '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
          {data.insights.length > 0 && (
            <Card>
              <CardContent className="space-y-1.5 py-4 text-sm text-foreground">
                {data.insights.map((ins, i) => (
                  <p key={i}>• {ins.replace(/\*\*(.+?)\*\*/g, '$1')}</p>
                ))}
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  )
}
