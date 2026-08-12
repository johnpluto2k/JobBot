import { useRef, useState, type ChangeEvent, type ReactNode } from 'react'
import {
  ChevronDown,
  ChevronRight,
  Download,
  ExternalLink,
  FileText,
  Loader2,
  Printer,
  Sparkles,
  Users,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { ErrorNote } from '@/components/ErrorNote'
import { api, type ScoreResult, type StudioRender, type StudioSource, type TailorResult } from '@/lib/api'

// The `error` case aside, a resolved /api/tailor call always carries all four
// fields together — narrow to that once here so downstream JSX can read
// `tailor.summary`/`tailor.yaml` without re-checking optionality everywhere.
type TailorSuccess = Required<Pick<TailorResult, 'summary' | 'yaml' | 'field' | 'suggested_renderer'>>
import { useAsync } from '@/lib/useAsync'

function scoreColor(v: number) {
  return v >= 70 ? 'var(--status-green)' : v >= 50 ? 'var(--status-amber)' : 'var(--status-red)'
}

function downloadBlob(bytes: BlobPart, name: string, mime: string) {
  const url = URL.createObjectURL(new Blob([bytes], { type: mime }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

function b64ToBytes(b64: string): Uint8Array {
  const bin = atob(b64)
  const out = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i)
  return out
}

/** Labeled fact row for the job-summary card. */
function SummaryRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-right font-medium text-foreground">{value ?? '—'}</span>
    </div>
  )
}

export function ResumeTab() {
  // --- Input card state -------------------------------------------------------
  const [jd, setJd] = useState('')
  const [url, setUrl] = useState('')
  const [company, setCompany] = useState('')

  // --- Score box state ---------------------------------------------------------
  const [scoreLoading, setScoreLoading] = useState(false)
  const [scoreError, setScoreError] = useState<string | null>(null)
  const [score, setScore] = useState<ScoreResult | null>(null)

  // --- Job summary + tailored YAML state ---------------------------------------
  const [tailorLoading, setTailorLoading] = useState(false)
  const [tailorError, setTailorError] = useState<string | null>(null)
  const [tailor, setTailor] = useState<TailorSuccess | null>(null)

  // --- Tailored resume (PDF) state ----------------------------------------------
  const [renderLoading, setRenderLoading] = useState(false)
  const [renderError, setRenderError] = useState<string | null>(null)
  const [render, setRender] = useState<StudioRender | null>(null)
  // Bumped on every Analyze click; the background studioRender callback checks
  // it before writing state so a stale render from a superseded Analyze can
  // never clobber a newer one (the Analyze button re-enables — and can be
  // clicked again — before the background PDF render finishes).
  const analyzeGenRef = useRef(0)
  // Snapshot of {jd, url, company} at the moment Analyze was clicked, so
  // "resume.docx" always matches what's on screen even if the JD textarea is
  // edited afterward — not whatever's currently typed.
  const [analyzedInput, setAnalyzedInput] = useState<{ jd: string; url?: string; company?: string } | null>(null)

  // --- Advanced: Edit YAML section ----------------------------------------------
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [yamlText, setYamlText] = useState('')
  // True once the user has deliberately set YAML content themselves (typed in
  // the editor, or picked a "Start from" source) — after that, Analyze must
  // never silently overwrite it.
  const [yamlDirty, setYamlDirty] = useState(false)
  const sources = useAsync(api.studioSources, [])
  const [source, setSource] = useState('profile')
  const [sourceYamlLoading, setSourceYamlLoading] = useState(false)
  const [reRendering, setReRendering] = useState(false)

  // --- Download resume.docx (lazy, fetched on click) ----------------------------
  const [docxLoading, setDocxLoading] = useState(false)
  const [docxError, setDocxError] = useState<string | null>(null)

  const analyzing = scoreLoading || tailorLoading

  async function analyze() {
    if (!jd.trim()) return
    const gen = ++analyzeGenRef.current
    const body = { jd, url: url || undefined, company: company || undefined }
    setAnalyzedInput(body)

    // Score and tailor run concurrently — independent loading/error state each.
    setScoreLoading(true)
    setScoreError(null)
    setScore(null)
    setTailorLoading(true)
    setTailorError(null)
    setTailor(null)
    setRenderLoading(false)
    setRenderError(null)
    setRender(null)

    const scorePromise = api
      .score(body)
      .then((r) => setScore(r))
      .catch((e) => setScoreError(String((e as Error).message ?? e)))
      .finally(() => setScoreLoading(false))

    const tailorPromise = api
      .tailor(body)
      .then((r) => {
        if (r.error || !r.summary || !r.yaml || !r.field || !r.suggested_renderer) {
          setTailorError(r.error ?? 'no resume returned')
          return
        }
        const yaml = r.yaml
        setTailor({ summary: r.summary, yaml: r.yaml, field: r.field, suggested_renderer: r.suggested_renderer })
        // Pre-fill the YAML editor, but never clobber a deliberate user choice.
        if (!yamlDirty) setYamlText(yaml)
        // As soon as we have YAML, kick off typesetting in the background.
        // The Analyze button re-enables once tailor resolves — well before
        // this finishes — so a newer Analyze click can supersede this one;
        // `gen` guards every state write below against that race.
        setRenderLoading(true)
        api
          .studioRender(yaml)
          .then((rr) => {
            if (gen !== analyzeGenRef.current) return
            if (rr.error) setRenderError(rr.error)
            else setRender(rr)
          })
          .catch((e) => {
            if (gen !== analyzeGenRef.current) return
            setRenderError(String((e as Error).message ?? e))
          })
          .finally(() => {
            if (gen !== analyzeGenRef.current) return
            setRenderLoading(false)
          })
      })
      .catch((e) => setTailorError(String((e as Error).message ?? e)))
      .finally(() => setTailorLoading(false))

    await Promise.allSettled([scorePromise, tailorPromise])
  }

  async function loadSourceYaml(src: string) {
    setSourceYamlLoading(true)
    setRenderError(null)
    try {
      const r = await api.studioYaml(src)
      if (r.error) setRenderError(r.error)
      else {
        setYamlText(r.yaml ?? '')
        setYamlDirty(true) // deliberate override — Analyze must not replace it later
      }
    } catch (e) {
      setRenderError(String((e as Error).message ?? e))
    } finally {
      setSourceYamlLoading(false)
    }
  }

  function onSourceChange(e: ChangeEvent<HTMLSelectElement>) {
    const src = e.target.value
    setSource(src)
    loadSourceYaml(src)
  }

  async function reRender() {
    setReRendering(true)
    setRenderError(null)
    try {
      const r = await api.studioRender(yamlText)
      if (r.error) setRenderError(r.error)
      else setRender(r)
    } catch (e) {
      setRenderError(String((e as Error).message ?? e))
    } finally {
      setReRendering(false)
    }
  }

  async function downloadDocx() {
    if (!analyzedInput) return
    setDocxLoading(true)
    setDocxError(null)
    try {
      // Use the snapshot from the last Analyze, not live jd/url/company —
      // the JD textarea may have been edited since, and the docx must match
      // what's actually on screen (score/summary/PDF), not whatever's typed now.
      const r = await api.tailorDocx(analyzedInput)
      if (r.error || !r.docx_b64) {
        setDocxError(r.error ?? 'no docx returned')
        return
      }
      downloadBlob(
        b64ToBytes(r.docx_b64).buffer as ArrayBuffer,
        r.name ?? 'resume.docx',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      )
    } catch (e) {
      setDocxError(String((e as Error).message ?? e))
    } finally {
      setDocxLoading(false)
    }
  }

  const showResultsRow = scoreLoading || scoreError || score || tailorLoading || tailorError || tailor
  const showResumeCard = tailorLoading || tailor || renderLoading || render || renderError

  return (
    <div className="space-y-6">
      {/* Input card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Sparkles size={17} style={{ color: 'var(--primary)' }} /> Analyze a job description
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Paste a JD once — get the live ATS match + network verdict, a job summary, and a tailored,
            one-page resume, all from one click.
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
          <div className="flex justify-end border-t border-border pt-4">
            <Button onClick={analyze} disabled={analyzing || !jd.trim()}>
              {analyzing ? (
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

      {showResultsRow && (
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Score box */}
          <div className="space-y-6">
            {scoreError && <ErrorNote error={scoreError} title="Scoring failed." showStartHint={false} />}
            {scoreLoading && !score && (
              <Card>
                <CardContent className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
                  <Loader2 size={15} className="animate-spin" /> Scoring…
                </CardContent>
              </Card>
            )}
            {score && (
              <div className="space-y-6">
                {/* Verdict banner */}
                <Card>
                  <CardContent className="py-5">
                    <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
                      <span className="text-lg font-semibold text-foreground">
                        {score.job.title || 'Role'} @ {score.job.company || '—'}
                      </span>
                      {score.job.market_tier && <Badge variant="slate">{score.job.market_tier}</Badge>}
                      <Badge variant="blue">{score.ats.platform}</Badge>
                    </div>
                    <div className="flex items-center gap-4">
                      <div
                        className="text-3xl font-semibold tabular-nums"
                        style={{ color: scoreColor(score.ats.overall_score) }}
                      >
                        {score.ats.overall_score}
                        <span className="text-lg text-muted-foreground">/100</span>
                      </div>
                      <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-muted">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${Math.min(100, score.ats.overall_score)}%`,
                            background: scoreColor(score.ats.overall_score),
                          }}
                        />
                      </div>
                    </div>
                    <p className="mt-4 text-base font-medium text-foreground">{score.decision.verdict}</p>
                    <p className="mt-1 text-sm text-muted-foreground">{score.decision.rationale}</p>
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
                        <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                          Matched
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                          {score.ats.matched.length ? (
                            score.ats.matched.map((k) => (
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
                          {score.ats.missing_required.length ? (
                            score.ats.missing_required.map((k) => (
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
                      {score.ats.gap_analysis.map((g) => (
                        <div key={g.keyword} className="text-sm">
                          <div className="flex items-baseline justify-between">
                            <span className="font-medium text-foreground">
                              {g.keyword}{' '}
                              <Badge
                                variant={g.importance === 'required' ? 'red' : 'slate'}
                                className="ml-1 align-middle"
                              >
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
                        {score.decision.actions.map((a, i) => (
                          <li key={i}>{a.replace(/\*\*(.+?)\*\*/g, '$1')}</li>
                        ))}
                      </ul>
                    </CardContent>
                  </Card>
                  {score.decision.matches.length > 0 && (
                    <Card>
                      <CardHeader>
                        <CardTitle className="flex items-center gap-2 text-base">
                          <Users size={16} /> Warm contacts here
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-1.5">
                        {score.decision.matches.map((m, i) => (
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

          {/* Job summary box */}
          <div className="space-y-6">
            {tailorError && <ErrorNote error={tailorError} title="Analysis failed." showStartHint={false} />}
            {tailorLoading && !tailor && (
              <Card>
                <CardContent className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
                  <Loader2 size={15} className="animate-spin" /> Summarizing the role…
                </CardContent>
              </Card>
            )}
            {tailor && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Job summary</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-1.5">
                    <SummaryRow label="Title" value={tailor.summary.title} />
                    <SummaryRow label="Company" value={tailor.summary.company} />
                    <SummaryRow label="Location" value={tailor.summary.location} />
                    <SummaryRow label="Role type" value={tailor.summary.role_type} />
                    <SummaryRow label="Seniority" value={tailor.summary.seniority} />
                    <SummaryRow label="Market tier" value={tailor.summary.market_tier} />
                    <SummaryRow
                      label="Remote"
                      value={<Badge variant={tailor.summary.remote ? 'blue' : 'slate'}>{tailor.summary.remote ? 'Remote' : 'On-site'}</Badge>}
                    />
                    <SummaryRow label="ATS platform" value={tailor.summary.ats_platform} />
                    <SummaryRow
                      label="GPA cutoff"
                      value={tailor.summary.gpa_cutoff != null ? tailor.summary.gpa_cutoff : null}
                    />
                    <SummaryRow
                      label="Years experience"
                      value={tailor.summary.years_experience != null ? tailor.summary.years_experience : null}
                    />
                  </div>

                  <div>
                    <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      Required keywords
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {tailor.summary.required_keywords.length ? (
                        tailor.summary.required_keywords.map((k) => (
                          <Badge key={k} variant="blue">
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
                      Preferred keywords
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {tailor.summary.preferred_keywords.length ? (
                        tailor.summary.preferred_keywords.map((k) => (
                          <Badge key={k} variant="slate">
                            {k}
                          </Badge>
                        ))
                      ) : (
                        <span className="text-sm text-muted-foreground">—</span>
                      )}
                    </div>
                  </div>

                  {tailor.summary.prose && (
                    <p className="border-t border-border pt-3 text-sm leading-relaxed text-foreground">
                      {tailor.summary.prose}
                    </p>
                  )}
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}

      {/* Tailored resume card */}
      {showResumeCard && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Tailored resume</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="min-h-[1.25rem] space-y-2" aria-live="polite">
              {renderLoading && (
                <p className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Loader2 size={13} className="animate-spin" /> Typesetting via Typst — usually 10–30s.
                </p>
              )}
              {renderError && <ErrorNote error={renderError} title="Render failed." showStartHint={false} />}
            </div>

            {render?.pdf_b64 && tailor && (
              <>
                <div className="min-h-[1.25rem]">
                  {render.page_count === 1 && (
                    <Badge variant="green">Fits on one page</Badge>
                  )}
                  {render.page_count != null && render.page_count > 1 && (
                    <Badge variant="amber">
                      Resume is {render.page_count} pages — consider trimming in Edit YAML below
                    </Badge>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="outline"
                    onClick={() =>
                      downloadBlob(
                        b64ToBytes(render.pdf_b64!).buffer as ArrayBuffer,
                        render.pdf_name ?? 'resume.pdf',
                        'application/pdf',
                      )
                    }
                  >
                    <Download /> resume.pdf
                  </Button>
                  <Button variant="outline" onClick={() => downloadBlob(tailor.yaml, 'resume.yaml', 'text/plain')}>
                    <Download /> resume.yaml
                  </Button>
                  {render.typ && (
                    <Button variant="outline" onClick={() => downloadBlob(render.typ!, 'resume.typ', 'text/plain')}>
                      <Download /> resume.typ
                    </Button>
                  )}
                  <Button variant="outline" onClick={downloadDocx} disabled={docxLoading}>
                    {docxLoading ? <Loader2 className="animate-spin" /> : <FileText />} resume.docx
                  </Button>
                  <Button variant="outline" asChild>
                    <a href="https://typst.app" target="_blank" rel="noreferrer">
                      <ExternalLink /> Open typst.app
                    </a>
                  </Button>
                </div>
                <div className="min-h-[1.25rem]">
                  {docxError && <ErrorNote error={docxError} title="Download failed." showStartHint={false} />}
                </div>
                <iframe
                  title="Tailored resume PDF"
                  src={`data:application/pdf;base64,${render.pdf_b64}`}
                  className="h-[48rem] w-full rounded-lg border border-border"
                />
              </>
            )}
          </CardContent>
        </Card>
      )}

      {/* Advanced: Edit YAML */}
      <Card>
        <button
          type="button"
          onClick={() => setAdvancedOpen((v) => !v)}
          className="flex w-full items-center justify-between gap-2 px-6 py-4 text-left"
          aria-expanded={advancedOpen}
        >
          <span className="flex items-center gap-2 text-base font-semibold tracking-tight">
            {advancedOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />} Advanced: Edit YAML
          </span>
          <span className="text-xs text-muted-foreground">resume-as-code, RenderCV YAML</span>
        </button>
        {advancedOpen && (
          <CardContent className="space-y-5 border-t border-border pt-5">
            <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end sm:justify-between">
              <label className="min-w-0 flex-1 sm:max-w-sm">
                <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Start from
                </span>
                <select
                  value={source}
                  onChange={onSourceChange}
                  disabled={sourceYamlLoading}
                  className="h-10 w-full rounded-lg border border-input bg-card px-3 text-sm shadow-sm outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {(sources.data?.sources ?? [{ key: 'profile', label: 'Master profile (no target JD)' }]).map(
                    (s: StudioSource) => (
                      <option key={s.key} value={s.key}>
                        {s.label}
                      </option>
                    ),
                  )}
                </select>
              </label>
              <Button onClick={reRender} disabled={reRendering || sourceYamlLoading || !yamlText.trim()}>
                {reRendering ? (
                  <>
                    <Loader2 className="animate-spin" /> Typesetting…
                  </>
                ) : (
                  <>
                    <Printer /> Re-render PDF
                  </>
                )}
              </Button>
            </div>

            <div className="min-w-0 space-y-1.5">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                <label
                  htmlFor="resume-yaml"
                  className="text-xs font-semibold uppercase tracking-wide text-muted-foreground"
                >
                  RenderCV YAML
                </label>
                <span className="min-w-0 text-xs text-muted-foreground">
                  the résumé — reorder bullets, rewrite wording, add/remove sections (JSON is valid YAML)
                </span>
              </div>
              <Textarea
                id="resume-yaml"
                value={yamlText}
                onChange={(e) => {
                  setYamlText(e.target.value)
                  setYamlDirty(true)
                }}
                disabled={sourceYamlLoading}
                spellCheck={false}
                placeholder={sourceYamlLoading ? 'Loading résumé YAML…' : 'RenderCV YAML…'}
                aria-busy={sourceYamlLoading}
                className="min-h-[26rem] w-full resize-y overflow-auto whitespace-pre font-mono text-xs leading-relaxed"
              />
            </div>
          </CardContent>
        )}
      </Card>
    </div>
  )
}
