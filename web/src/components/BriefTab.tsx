import { useState } from 'react'
import { Building2, Loader2, HelpCircle, Users } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { ErrorNote } from '@/components/ErrorNote'
import { api, type Brief } from '@/lib/api'

function ListCard({ title, items }: { title: string; items: string[] }) {
  if (!items?.length) return null
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="list-inside list-disc space-y-1.5 text-sm text-foreground marker:text-muted-foreground">
          {items.map((it, i) => (
            <li key={i}>{it}</li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}

export function BriefTab() {
  const [company, setCompany] = useState('')
  const [role, setRole] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [brief, setBrief] = useState<Brief | null>(null)

  async function run() {
    if (!company.trim()) return
    setLoading(true)
    setError(null)
    try {
      setBrief(await api.brief({ company, role: role || undefined }))
    } catch (e) {
      setError(String((e as Error).message ?? e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Building2 size={17} style={{ color: 'var(--primary)' }} /> Company research brief
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Hiring process, values, likely interview topics, smart questions to ask, and your warm contacts there.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Input value={company} onChange={(e) => setCompany(e.target.value)} placeholder="Company (e.g. KPMG)" />
            <Input value={role} onChange={(e) => setRole(e.target.value)} placeholder="Role (optional)" />
          </div>
          {error && <ErrorNote error={error} title="Brief failed." showStartHint={false} />}
          <div className="flex justify-end border-t border-border pt-4">
            <Button onClick={run} disabled={loading || !company.trim()}>
              {loading ? (
                <>
                  <Loader2 className="animate-spin" /> Building…
                </>
              ) : (
                <>
                  <Building2 /> Build brief
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {brief && (
        <div className="space-y-6">
          <Card>
            <CardContent className="py-5">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-lg font-semibold text-foreground">{brief.company}</span>
                <Badge variant="slate">{brief.type}</Badge>
                {brief.ats_platform && <Badge variant="blue">ATS: {brief.ats_platform}</Badge>}
              </div>
              {brief.narrative && (
                <p className="mt-3 whitespace-pre-line text-sm leading-relaxed text-foreground">{brief.narrative}</p>
              )}
            </CardContent>
          </Card>

          <div className="grid gap-6 lg:grid-cols-2">
            <ListCard title="Hiring process" items={brief.hiring_process} />
            <ListCard title="Values" items={brief.values} />
            <ListCard title="Likely interview topics" items={brief.likely_topics} />
            <ListCard title="Why this firm (your angles)" items={brief.why_this_firm} />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <HelpCircle size={16} /> Smart questions to ask
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="list-inside list-decimal space-y-1.5 text-sm text-foreground marker:text-muted-foreground">
                  {brief.smart_questions.map((q, i) => (
                    <li key={i}>{q}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Users size={16} /> Warm contacts here ({brief.warm_contacts.length})
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-1.5">
                {brief.warm_contacts.length === 0 && (
                  <p className="text-sm text-muted-foreground">No contacts on file — a coverage gap.</p>
                )}
                {brief.warm_contacts.slice(0, 8).map((c, i) => (
                  <div key={i} className="flex items-center justify-between text-sm">
                    <span className="font-medium text-foreground">{c.name}</span>
                    <span className="text-xs text-muted-foreground">
                      {c.relationship} {c.title && `· ${c.title}`}
                    </span>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  )
}
