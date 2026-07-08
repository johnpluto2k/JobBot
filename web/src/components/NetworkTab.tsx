import { Users, AlertTriangle } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ErrorNote } from '@/components/ErrorNote'
import { KpiCard } from '@/components/KpiCard'
import { api, type Contact } from '@/lib/api'
import { useAsync } from '@/lib/useAsync'

const REL_LABEL: Record<string, string> = {
  recruiter: 'Recruiter',
  first_degree: '1st degree',
  second_degree: '2nd degree',
  umd: 'UMD',
  pse: 'PSE',
  alum: 'Alum',
  iefs: 'IEFS',
  terptax: 'TerpTax',
}

function warmthDot(w?: number | null) {
  const v = w ?? 0
  const color = v >= 0.7 ? 'var(--status-green)' : v >= 0.4 ? 'var(--status-amber)' : 'var(--status-slate)'
  return <span className="inline-block h-2 w-2 rounded-full" style={{ background: color }} />
}

function ContactRow({ c }: { c: Contact }) {
  return (
    <div className="flex items-center gap-2 py-1 text-sm">
      {warmthDot(c.warmth)}
      <span className="font-medium text-foreground">{c.name}</span>
      {c.relationship && (
        <Badge variant="secondary" className="text-[10px]">
          {REL_LABEL[c.relationship] ?? c.relationship}
        </Badge>
      )}
      {c.title && <span className="truncate text-muted-foreground">· {c.title}</span>}
    </div>
  )
}

export function NetworkTab() {
  const { data, loading, error } = useAsync(api.network, [])

  if (loading) return <div className="h-64 animate-pulse rounded-xl border border-border bg-card" />
  if (error || !data) return <ErrorNote error={error ?? 'No network data returned.'} />

  const topCovered = data.covered.slice(0, 12)

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
        <KpiCard label="Contacts" value={data.total_contacts} icon={Users} accent="indigo" />
        <KpiCard label="Companies covered" value={data.companies_with_contacts} icon={Users} accent="violet" />
        <KpiCard
          label="Target gaps"
          value={data.gaps.length}
          sub="targets w/ weak coverage"
          icon={AlertTriangle}
          accent="amber"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Strongest coverage</CardTitle>
          </CardHeader>
          <CardContent className="divide-y divide-border">
            {topCovered.map((co) => (
              <div key={co.company} className="py-3 first:pt-0 last:pb-0">
                <div className="mb-1 flex items-center justify-between">
                  <span className="font-semibold text-foreground">{co.company}</span>
                  <span className="text-xs text-muted-foreground">
                    {co.count} {co.count === 1 ? 'contact' : 'contacts'} · reach{' '}
                    <span className="font-medium text-foreground">{co.reach_first}</span>
                  </span>
                </div>
                {co.contacts.slice(0, 3).map((c, i) => (
                  <ContactRow key={`${c.name}-${i}`} c={c} />
                ))}
                {co.contacts.length > 3 && (
                  <div className="pt-1 text-xs text-muted-foreground">
                    +{co.contacts.length - 3} more
                  </div>
                )}
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Coverage gaps at your targets</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {data.gaps.length === 0 && <p className="text-sm text-muted-foreground">No gaps — every target has coverage.</p>}
            {data.gaps.map((g) => (
              <div
                key={g.company}
                className="flex items-center justify-between rounded-lg border border-border px-3 py-2 text-sm"
              >
                <span className="font-medium text-foreground">{g.company}</span>
                <Badge variant={g.status === 'no coverage' ? 'red' : 'amber'}>{g.status}</Badge>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
