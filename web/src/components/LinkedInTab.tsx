import { useState } from 'react'
import { AtSign, Loader2, Copy, Check } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { ErrorNote } from '@/components/ErrorNote'
import { api, type LinkedInAudit } from '@/lib/api'

function CopyBlock({ label, text }: { label: string; text: string }) {
  const [copied, setCopied] = useState(false)
  async function copy() {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</span>
        <Button variant="ghost" size="sm" onClick={copy} className="h-7 gap-1.5 px-2 text-xs">
          {copied ? <Check size={13} /> : <Copy size={13} />}
          {copied ? 'Copied' : 'Copy'}
        </Button>
      </div>
      <div className="whitespace-pre-line rounded-lg border border-border bg-muted/40 p-3 text-sm text-foreground">
        {text}
      </div>
    </div>
  )
}

export function LinkedInTab() {
  const [role, setRole] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [audit, setAudit] = useState<LinkedInAudit | null>(null)

  async function run() {
    setLoading(true)
    setError(null)
    try {
      setAudit(await api.linkedin({ target_role: role || undefined }))
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
            <AtSign size={17} style={{ color: 'var(--primary)' }} /> LinkedIn profile optimizer
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Generates a search-optimized headline and About section, ranks your skills, and flags keyword gaps.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <label className="block">
            <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Target role (optional)
            </span>
            <Input value={role} onChange={(e) => setRole(e.target.value)} placeholder="e.g. IT Audit / Technology Risk" />
          </label>
          {error && <ErrorNote error={error} title="Audit failed." showStartHint={false} />}
          <div className="flex justify-end border-t border-border pt-4">
            <Button onClick={run} disabled={loading}>
              {loading ? (
                <>
                  <Loader2 className="animate-spin" /> Auditing…
                </>
              ) : (
                <>
                  <AtSign /> Run audit
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {audit && (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                Optimized for <span className="text-primary">{audit.target_role}</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <CopyBlock label="Headline" text={audit.headline} />
              <CopyBlock label="About" text={audit.about} />
            </CardContent>
          </Card>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Ranked skills</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-1.5">
                {audit.skills.map((s) => (
                  <Badge key={s} variant="secondary">
                    {s}
                  </Badge>
                ))}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Keyword gaps</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-1.5">
                {audit.keyword_gaps.length ? (
                  audit.keyword_gaps.map((k) => (
                    <Badge key={k} variant="amber">
                      {k}
                    </Badge>
                  ))
                ) : (
                  <p className="text-sm text-muted-foreground">No gaps for this target — your skills cover it.</p>
                )}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Recommendations</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="list-inside list-disc space-y-1.5 text-sm text-foreground marker:text-primary">
                {audit.recommendations.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
