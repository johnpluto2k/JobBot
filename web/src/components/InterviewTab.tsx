import { useState } from 'react'
import { Mic, Loader2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { KpiCard } from '@/components/KpiCard'
import { api, type Recording } from '@/lib/api'

export function InterviewTab() {
  const [question, setQuestion] = useState('Tell me about a time you improved a process')
  const [transcript, setTranscript] = useState('')
  const [duration, setDuration] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [r, setR] = useState<Recording | null>(null)

  async function run() {
    if (!transcript.trim()) return
    setLoading(true)
    setError(null)
    try {
      setR(
        await api.recording({
          question,
          transcript,
          duration_seconds: duration ? Number(duration) : undefined,
        }),
      )
    } catch (e) {
      setError(String((e as Error).message ?? e))
    } finally {
      setLoading(false)
    }
  }

  const starOn = r ? Object.entries(r.star).filter(([, v]) => v).map(([k]) => k) : []

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Mic size={17} style={{ color: 'var(--primary)' }} /> Interview answer analysis
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Paste a transcript of a recorded practice answer — get STAR compliance, pacing, fillers, and phrases to cut.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <Input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Question" />
          <Textarea
            value={transcript}
            onChange={(e) => setTranscript(e.target.value)}
            placeholder="Paste the transcript of your recorded answer…"
            className="min-h-[160px]"
          />
          <div className="flex flex-wrap items-end gap-3">
            <label className="w-56">
              <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Spoken duration (sec, optional)
              </span>
              <Input
                type="number"
                value={duration}
                onChange={(e) => setDuration(e.target.value)}
                placeholder="e.g. 90 — enables pacing"
              />
            </label>
            <Button onClick={run} disabled={loading || !transcript.trim()}>
              {loading ? (
                <>
                  <Loader2 className="animate-spin" /> Analyzing…
                </>
              ) : (
                <>
                  <Mic /> Analyze answer
                </>
              )}
            </Button>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </CardContent>
      </Card>

      {r && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <KpiCard label="Score" value={`${r.score}`} sub={r.band} accent="violet" />
            <KpiCard label="Words" value={r.word_count} accent="slate" />
            <KpiCard label="Fillers" value={r.filler_count} accent="amber" />
            <KpiCard label="Pace" value={r.pacing ? `${r.pacing.wpm} wpm` : '—'} accent="indigo" />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">STAR &amp; delivery</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="font-medium text-foreground">STAR:</span>
                  {(['S', 'T', 'A', 'R'] as const).map((k) => (
                    <Badge key={k} variant={starOn.includes(k) ? 'green' : 'slate'}>
                      {k}
                    </Badge>
                  ))}
                  <span className="ml-2 text-muted-foreground">
                    Quantified: {r.quantified ? 'yes' : 'no'} · Ownership: {Math.round(r.ownership * 100)}%
                  </span>
                </div>
                {r.delivery_notes.length > 0 && (
                  <ul className="list-inside list-disc space-y-1 text-sm text-foreground marker:text-muted-foreground">
                    {r.delivery_notes.map((d, i) => (
                      <li key={i}>{d}</li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Fixes</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                {r.phrases_to_cut.length > 0 && (
                  <div>
                    <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      Phrases to cut
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {r.phrases_to_cut.map((c, i) => (
                        <Badge key={i} variant="red">
                          {c}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
                {r.improvements.length > 0 && (
                  <div>
                    <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Improve</p>
                    <ul className="list-inside list-disc space-y-1 text-foreground marker:text-primary">
                      {r.improvements.map((im, i) => (
                        <li key={i}>{im}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {r.strengths.length > 0 && (
                  <div>
                    <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Strengths</p>
                    <div className="flex flex-wrap gap-1.5">
                      {r.strengths.map((s, i) => (
                        <Badge key={i} variant="green">
                          {s}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  )
}
