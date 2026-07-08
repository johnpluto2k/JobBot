import { useState } from 'react'
import { Sparkles, Loader2, Users } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { ErrorNote } from '@/components/ErrorNote'
import { api, type ScoreResult } from '@/lib/api'

function scoreColor(v: number) {
  return v >= 70 ? 'var(--status-green)' : v >= 50 ? 'var(--status-amber)' : 'var(--status-red)'
}

export function ScoreTab() {
  const [jd, setJd] = useState('')
  const [url, setUrl] = useState('')
  const [company, setCompany] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<ScoreResult | null>(null)

  async function analyze() {
    if (!jd.trim()) return
    setLoading(true)
    setError(null)
    try {
      const r = await api.score({ jd, url: url || undefined, company: company || undefined })
      setResult(r)
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
            <Sparkles size={17} style={{ color: 'var(--primary)' }} /> Score a job description
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Runs the live ATS match + connection lookup to tell you whether to apply cold or get a referral first.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <Textarea
            value={jd}
            onChange={(e) => setJd(e.target.value)}
            placeholder="Paste the full job description here…"
            className="min-h-[200px]"
          />
          <div className="grid gap-3 sm:grid-cols-2">
            <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="Posting URL (optional)" />
            <Input
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              placeholder="Company override (optional)"
            />
          </div>
          {error && <ErrorNote error={error} title="Analysis failed." showStartHint={false} />}
          <div className="flex justify-end border-t border-border pt-4">
            <Button onClick={analyze} disabled={loading || !jd.trim()}>
              {loading ? (
                <>
                  <Loader2 className="animate-spin" /> Analyzing…
                </>
              ) : (
                <>
                  <Sparkles /> Analyze
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {result && (
        <div className="space-y-6">
          {/* Verdict banner */}
          <Card>
            <CardContent className="py-5">
              <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
                <span className="text-lg font-semibold text-foreground">
                  {result.job.title || 'Role'} @ {result.job.company || '—'}
                </span>
                {result.job.market_tier && <Badge variant="slate">{result.job.market_tier}</Badge>}
                <Badge variant="blue">{result.ats.platform}</Badge>
              </div>
              <div className="flex items-center gap-4">
                <div className="text-3xl font-semibold tabular-nums" style={{ color: scoreColor(result.ats.overall_score) }}>
                  {result.ats.overall_score}
                  <span className="text-lg text-muted-foreground">/100</span>
                </div>
                <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${Math.min(100, result.ats.overall_score)}%`,
                      background: scoreColor(result.ats.overall_score),
                    }}
                  />
                </div>
              </div>
              <p className="mt-4 text-base font-medium text-foreground">{result.decision.verdict}</p>
              <p className="mt-1 text-sm text-muted-foreground">{result.decision.rationale}</p>
            </CardContent>
          </Card>

          <div className="grid gap-6 lg:grid-cols-2">
            {/* Keywords */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Keyword match</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Matched</p>
                  <div className="flex flex-wrap gap-1.5">
                    {result.ats.matched.length ? (
                      result.ats.matched.map((k) => (
                        <Badge key={k} variant="green">
                          {k}
                        </Badge>
                      ))
                    ) : (
                      <span className="text-sm text-muted-foreground">—</span>
                    )}
                  </div>
                </div>
                <div>
                  <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Missing (required)
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {result.ats.missing_required.length ? (
                      result.ats.missing_required.map((k) => (
                        <Badge key={k} variant="red">
                          {k}
                        </Badge>
                      ))
                    ) : (
                      <span className="text-sm text-muted-foreground">none — you cover them all</span>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Gap analysis */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Ranked gap analysis</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2.5">
                {result.ats.gap_analysis.map((g) => (
                  <div key={g.keyword} className="text-sm">
                    <div className="flex items-baseline justify-between">
                      <span className="font-medium text-foreground">
                        {g.keyword}{' '}
                        <Badge variant={g.importance === 'required' ? 'red' : 'slate'} className="ml-1 align-middle">
                          {g.importance}
                        </Badge>
                      </span>
                      <span className="tabular-nums text-muted-foreground">+{g.impact}</span>
                    </div>
                    <p className="text-xs text-muted-foreground">{g.action}</p>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>

          {/* Recommended actions + who to reach */}
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Recommended actions</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="list-inside list-disc space-y-1.5 text-sm text-foreground marker:text-primary">
                  {result.decision.actions.map((a, i) => (
                    <li key={i}>{a.replace(/\*\*(.+?)\*\*/g, '$1')}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
            {result.decision.matches.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Users size={16} /> Warm contacts here
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-1.5">
                  {result.decision.matches.map((m, i) => (
                    <div key={i} className="flex items-center justify-between text-sm">
                      <span className="font-medium text-foreground">{m.name}</span>
                      <span className="text-xs text-muted-foreground">
                        {m.relationship} {m.warmth != null && `· warmth ${m.warmth}`}
                      </span>
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
