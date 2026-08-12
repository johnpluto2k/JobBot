import { useEffect, useState, type ChangeEvent } from 'react'
import { Download, ExternalLink, Link2, Loader2, Printer, Sparkles } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ErrorNote } from '@/components/ErrorNote'
import {
  api,
  studioFileUrl,
  type StudioGenerateResult,
  type StudioHistoryRow,
  type StudioRender,
  type StudioSource,
} from '@/lib/api'
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

function fmtDate(iso: string | null | undefined) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

// --- "Link to application" mini action ------------------------------------------
type IntakeState = { status: 'idle' | 'loading' | 'done' | 'error'; message?: string }

function LinkToApplicationButton({
  company,
  title,
  state,
  onStateChange,
}: {
  company: string | null | undefined
  title: string | null | undefined
  state: IntakeState
  onStateChange: (s: IntakeState) => void
}) {
  async function link() {
    onStateChange({ status: 'loading' })
    try {
      const r = await api.intake({ url: '', company: company ?? '', title: title ?? '', portal: 'other', status: 'applied' })
      if (r.error) onStateChange({ status: 'error', message: r.error })
      else onStateChange({ status: 'done' })
    } catch (e) {
      onStateChange({ status: 'error', message: String((e as Error).message ?? e) })
    }
  }

  if (state.status === 'done') {
    return <span className="text-xs font-medium" style={{ color: 'var(--status-green)' }}>Linked</span>
  }
  return (
    <div className="flex items-center gap-2">
      <Button variant="outline" size="sm" onClick={link} disabled={state.status === 'loading'}>
        {state.status === 'loading' ? <Loader2 className="animate-spin" /> : <Link2 />} Link to application
      </Button>
      {state.status === 'error' && <span className="text-xs text-destructive">{state.message}</span>}
    </div>
  )
}

export function ResumeTab() {
  const [activeTab, setActiveTab] = useState<'generate' | 'code'>('generate')

  return (
    <div className="space-y-6">
      <div className="flex gap-2">
        <Button variant={activeTab === 'generate' ? 'default' : 'outline'} onClick={() => setActiveTab('generate')}>
          Generate from JD
        </Button>
        <Button variant={activeTab === 'code' ? 'default' : 'outline'} onClick={() => setActiveTab('code')}>
          Edit as code
        </Button>
      </div>

      {activeTab === 'generate' ? <GenerateFromJdTab /> : <EditAsCodeTab />}
    </div>
  )
}

// =================================================================================
// Tab 1 — Generate from JD
// =================================================================================

function GenerateFromJdTab() {
  const [jd, setJd] = useState('')
  const [company, setCompany] = useState('')
  const [role, setRole] = useState('')

  const [generating, setGenerating] = useState(false)
  const [genError, setGenError] = useState<string | null>(null)
  const [result, setResult] = useState<StudioGenerateResult | null>(null)
  const [intakeMain, setIntakeMain] = useState<IntakeState>({ status: 'idle' })

  // Bumped on every successful generate so the history table below refetches.
  const [refreshKey, setRefreshKey] = useState(0)
  const history = useAsync(api.studioHistory, [refreshKey])

  const [rowIntake, setRowIntake] = useState<Record<number, IntakeState>>({})

  async function generate() {
    if (!jd.trim()) return
    setGenerating(true)
    setGenError(null)
    setResult(null)
    setIntakeMain({ status: 'idle' })
    try {
      const r = await api.studioGenerate({ jd_text: jd, company: company || undefined, role: role || undefined })
      if (r.error || !r.summary || !r.resume_files || !r.history_row) {
        setGenError(r.error ?? 'no resume returned')
        return
      }
      setResult(r)
      setRefreshKey((k) => k + 1)
    } catch (e) {
      setGenError(String((e as Error).message ?? e))
    } finally {
      setGenerating(false)
    }
  }

  const summary = result?.summary
  const resumeFiles = result?.resume_files

  return (
    <div className="space-y-6">
      {/* Input card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Sparkles size={17} style={{ color: 'var(--primary)' }} /> Generate a tailored resume
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Paste a job description — get an honest ATS match, the real gaps, and a tailored, persisted
            application package (PDF/DOCX/YAML), all in one click.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Input
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              placeholder="Company (optional — auto-detected from JD)"
            />
            <Input value={role} onChange={(e) => setRole(e.target.value)} placeholder="Role (optional — auto-detected from JD)" />
          </div>
          <Textarea
            value={jd}
            onChange={(e) => setJd(e.target.value)}
            placeholder="Paste the job description here…"
            className="min-h-[200px]"
          />
          <div className="flex justify-end border-t border-border pt-4">
            <Button onClick={generate} disabled={generating || !jd.trim()}>
              {generating ? (
                <>
                  <Loader2 className="animate-spin" /> Generating…
                </>
              ) : (
                <>
                  <Sparkles /> Generate Tailored Resume
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="min-h-[1.25rem]">
        {genError && <ErrorNote error={genError} title="Generation failed." showStartHint={false} />}
      </div>

      {/* Summary card */}
      {summary && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Job summary</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
              <span className="text-lg font-semibold text-foreground">
                {summary.title || 'Role'} @ {summary.company || '—'}
                {summary.location && (
                  <span className="ml-2 text-sm font-normal text-muted-foreground">{summary.location}</span>
                )}
              </span>
              <Badge variant="blue">{summary.track}</Badge>
            </div>

            <div>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Must-haves
              </p>
              <div className="flex flex-wrap gap-1.5">
                {summary.must_haves.length ? (
                  summary.must_haves.map((k) => (
                    <Badge key={k} variant="slate">
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
                You already cover
              </p>
              <div className="flex flex-wrap gap-1.5">
                {summary.matched_keywords.length ? (
                  summary.matched_keywords.map((k) => (
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
                Honest gaps
              </p>
              <div className="flex flex-wrap gap-1.5">
                {summary.gaps.length ? (
                  summary.gaps.map((k) => (
                    <Badge key={k} variant="red">
                      {k}
                    </Badge>
                  ))
                ) : (
                  <span className="text-sm text-muted-foreground">none — you cover them all</span>
                )}
              </div>
            </div>

            <div className="flex items-center gap-3 border-t border-border pt-3">
              <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                ATS match
              </span>
              <span className="tabular-nums text-sm font-medium" style={{ color: scoreColor(summary.ats_before) }}>
                {summary.ats_before}
              </span>
              <span className="text-muted-foreground">→</span>
              <span className="tabular-nums text-base font-semibold" style={{ color: scoreColor(summary.ats_after) }}>
                {summary.ats_after}
              </span>
            </div>

            <div className="border-t border-border pt-3">
              <LinkToApplicationButton
                company={summary.company}
                title={summary.title}
                state={intakeMain}
                onStateChange={setIntakeMain}
              />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Tailored resume card */}
      {resumeFiles && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Tailored resume</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {resumeFiles.kinds.map((k) => (
                <Button key={k} variant="outline" asChild>
                  <a href={studioFileUrl(resumeFiles.id, k)} download>
                    <Download /> resume.{k}
                  </a>
                </Button>
              ))}
            </div>
            {resumeFiles.kinds.includes('pdf') && (
              <iframe
                title="Tailored resume PDF"
                src={studioFileUrl(resumeFiles.id, 'pdf')}
                className="h-[48rem] w-full rounded-lg border border-border"
              />
            )}
          </CardContent>
        </Card>
      )}

      {/* History table — always visible */}
      <div className="space-y-3">
        <h2 className="text-base font-semibold tracking-tight text-foreground">Generation history</h2>
        {history.error ? (
          <ErrorNote error={history.error} showStartHint={false} />
        ) : history.loading ? (
          <div className="h-48 animate-pulse rounded-xl border border-border bg-card" />
        ) : (
          <Card className="overflow-hidden p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Company</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Track</TableHead>
                  <TableHead>ATS</TableHead>
                  <TableHead>Downloads</TableHead>
                  <TableHead className="text-right">Application</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(history.data?.rows ?? []).map((row: StudioHistoryRow) => (
                  <TableRow key={row.id}>
                    <TableCell className="tabular-nums text-muted-foreground">{fmtDate(row.created_at)}</TableCell>
                    <TableCell className="font-medium text-foreground">{row.company || '—'}</TableCell>
                    <TableCell className="text-muted-foreground">{row.role || '—'}</TableCell>
                    <TableCell>
                      <Badge variant="slate">{row.track}</Badge>
                    </TableCell>
                    <TableCell className="text-xs">
                      <span className="tabular-nums" style={{ color: scoreColor(row.ats_before) }}>
                        {row.ats_before}
                      </span>
                      <span className="mx-1 text-muted-foreground">→</span>
                      <span className="tabular-nums" style={{ color: scoreColor(row.ats_after) }}>
                        {row.ats_after}
                      </span>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap items-center gap-2">
                        {row.kinds.map((k) => (
                          <a
                            key={k}
                            href={studioFileUrl(row.id, k)}
                            download
                            title={`Download resume.${k}`}
                            className="text-muted-foreground transition-colors hover:text-foreground"
                          >
                            <Download size={14} />
                          </a>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <LinkToApplicationButton
                        company={row.company}
                        title={row.role}
                        state={rowIntake[row.id] ?? { status: 'idle' }}
                        onStateChange={(s) => setRowIntake((prev) => ({ ...prev, [row.id]: s }))}
                      />
                    </TableCell>
                  </TableRow>
                ))}
                {(history.data?.rows.length ?? 0) === 0 && (
                  <TableRow>
                    <TableCell colSpan={7} className="py-8 text-center text-sm text-muted-foreground">
                      No resumes generated yet — use the form above to generate your first one.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </Card>
        )}
      </div>
    </div>
  )
}

// =================================================================================
// Tab 2 — Edit as code (ported from the old "Advanced: Edit YAML" section, verbatim
// behavior — calls /api/resume-studio/yaml + /api/resume-studio/render, unchanged)
// =================================================================================

function EditAsCodeTab() {
  const [yamlText, setYamlText] = useState('')
  const sources = useAsync(api.studioSources, [])
  const [source, setSource] = useState('profile')
  const [sourceYamlLoading, setSourceYamlLoading] = useState(false)
  const [reRendering, setReRendering] = useState(false)
  const [renderError, setRenderError] = useState<string | null>(null)
  const [render, setRender] = useState<StudioRender | null>(null)

  async function loadSourceYaml(src: string) {
    setSourceYamlLoading(true)
    setRenderError(null)
    try {
      const r = await api.studioYaml(src)
      if (r.error) setRenderError(r.error)
      else setYamlText(r.yaml ?? '')
    } catch (e) {
      setRenderError(String((e as Error).message ?? e))
    } finally {
      setSourceYamlLoading(false)
    }
  }

  // Load the default source's YAML on mount — this tab is now fully
  // independent of "Generate from JD" (each has its own state), so there's
  // no cross-tab prefill race to avoid; without this the editor opens empty
  // with no way to populate it until the user picks a different source.
  useEffect(() => {
    loadSourceYaml(source)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

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

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Edit as code</CardTitle>
        <p className="text-sm text-muted-foreground">
          resume-as-code, RenderCV YAML — start from a source, edit freely, and render a scratch PDF preview
          (not saved to the generation history).
        </p>
      </CardHeader>
      <CardContent className="space-y-5">
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
            onChange={(e) => setYamlText(e.target.value)}
            disabled={sourceYamlLoading}
            spellCheck={false}
            placeholder={sourceYamlLoading ? 'Loading résumé YAML…' : 'RenderCV YAML…'}
            aria-busy={sourceYamlLoading}
            className="min-h-[26rem] w-full resize-y overflow-auto whitespace-pre font-mono text-xs leading-relaxed"
          />
        </div>

        <div className="min-h-[1.25rem] space-y-2" aria-live="polite">
          {reRendering && (
            <p className="flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 size={13} className="animate-spin" /> Typesetting via Typst — usually 10–30s.
            </p>
          )}
          {renderError && <ErrorNote error={renderError} title="Render failed." showStartHint={false} />}
        </div>

        {render?.pdf_b64 && (
          <>
            <div className="min-h-[1.25rem]">
              {render.page_count === 1 && <Badge variant="green">Fits on one page</Badge>}
              {render.page_count != null && render.page_count > 1 && (
                <Badge variant="amber">Resume is {render.page_count} pages — consider trimming</Badge>
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
              <Button variant="outline" onClick={() => downloadBlob(yamlText, 'resume.yaml', 'text/plain')}>
                <Download /> resume.yaml
              </Button>
              {render.typ && (
                <Button variant="outline" onClick={() => downloadBlob(render.typ!, 'resume.typ', 'text/plain')}>
                  <Download /> resume.typ
                </Button>
              )}
              <Button variant="outline" asChild>
                <a href="https://typst.app" target="_blank" rel="noreferrer">
                  <ExternalLink /> Open typst.app
                </a>
              </Button>
            </div>
            <iframe
              title="Résumé PDF preview"
              src={`data:application/pdf;base64,${render.pdf_b64}`}
              className="h-[48rem] w-full rounded-lg border border-border"
            />
          </>
        )}
      </CardContent>
    </Card>
  )
}
