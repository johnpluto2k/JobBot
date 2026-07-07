import type { LucideIcon } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'

type Accent = 'indigo' | 'green' | 'violet' | 'amber' | 'red' | 'slate'

const ACCENT: Record<Accent, { text: string; tint: string }> = {
  indigo: { text: 'var(--primary)', tint: 'var(--accent)' },
  green: { text: 'var(--status-green)', tint: 'var(--status-green-bg)' },
  violet: { text: 'var(--status-violet)', tint: 'var(--status-violet-bg)' },
  amber: { text: 'var(--status-amber)', tint: 'var(--status-amber-bg)' },
  red: { text: 'var(--status-red)', tint: 'var(--status-red-bg)' },
  slate: { text: 'var(--status-slate)', tint: 'var(--status-slate-bg)' },
}

interface KpiCardProps {
  label: string
  value: string | number
  sub?: string
  icon?: LucideIcon
  accent?: Accent
}

export function KpiCard({ label, value, sub, icon: Icon, accent = 'indigo' }: KpiCardProps) {
  const a = ACCENT[accent]
  return (
    <Card className="gap-0 p-5">
      <div className="flex items-start justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</span>
        {Icon && (
          <span
            className="flex h-9 w-9 items-center justify-center rounded-lg"
            style={{ color: a.text, background: a.tint }}
          >
            <Icon size={18} strokeWidth={1.9} />
          </span>
        )}
      </div>
      <div className="mt-3 text-3xl font-semibold tracking-tight tabular-nums" style={{ color: 'var(--foreground)' }}>
        {value}
      </div>
      {sub && <div className={cn('mt-1 text-sm text-muted-foreground')}>{sub}</div>}
    </Card>
  )
}
