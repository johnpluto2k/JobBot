import { useEffect, useState } from 'react'
import { Download, ExternalLink, FileCode2, FileText, Loader2, Printer } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { api, type StudioRender, type StudioSource } from '@/lib/api'
import { useAsync } from '@/lib/useAsync'

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

export function ResumeStudioTab() {
  const sources = useAsync(api.studioSources, [])
  const [source, setSource] = useState('profile')
  const [yaml, setYaml] = useState('')
  const [loadingYaml, setLoadingYaml] = useState(false)
  const [rendering, setRendering] = useState(false)
  const [out, setOut] = useState<StudioRender | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [field, setField] = useState<string | null>(null)
  const [suggested, setSuggested] = useState<'rendercv' | 'docx' | null>(null)

  // (Re)load the starting YAML whenever the source changes.
  useEffect(() => {
    let cancelled = false
    setLoadingYaml(true)
    setOut(null)
    setError(null)
    api
      .studioYaml(source)
      .then((r) => {
        if (cancelled) return
        if (r.error) setError(r.error)
        else setYaml(r.yaml ?? '')
        setField(r.field ?? null)
        setSuggested(r.suggested_renderer ?? null)
      })
      .catch((e) => !cancelled && setError(String((e as Error).message ?? e)))
      .finally(() => !cancelled && setLoadingYaml(false))
    return () => {
      cancelled = true
    }
  }, [source])

  async function render() {
    setRendering(true)
    setError(null)
    try {
      const r = await api.studioRender(yaml)
      if (r.error) setError(r.error)
      else setOut(r)
    } catch (e) {
      setError(String((e as Error).message ?? e))
    } finally {
      setRendering(false)
    }
  }

  async function downloadDocx() {
    setError(null)
    try {
      const r = await api.studioDocx(source)
      if (r.error || !r.docx_b64) {
        setError(r.error ?? 'no docx returned')
        return
      }
      downloadBlob(
        b64ToBytes(r.docx_b64).buffer as ArrayBuffer,
        r.name ?? 'resume.docx',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      )
    } catch (e) {
      setError(String((e as Error).message ?? e))
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <FileCode2 size={17} style={{ color: 'var(--primary)' }} /> Resume Studio — resume as code
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            The resume is a RenderCV YAML file you edit as text, then typeset to PDF. RenderCV 2.x
            compiles via <span className="font-medium text-foreground">Typst</span> (v2 dropped LaTeX), so
            the typeset source is a <code className="rounded bg-muted px-1 font-mono text-xs">.typ</code>{' '}
            file — Overleaf (LaTeX-only) can't open it. To edit online, download the .typ and paste it
            into typst.app; that round-trip is one-way — copy changes back here yourself.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-end gap-4">
            <label className="min-w-[16rem]">
              <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Start from
              </span>
              <select
                value={source}
                onChange={(e) => setSource(e.target.value)}
                className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm shadow-xs outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
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
            <Button
              variant={suggested === 'docx' ? 'outline' : 'default'}
              onClick={render}
              disabled={rendering || loadingYaml || !yaml.trim()}
            >
              {rendering ? (
                <>
                  <Loader2 className="animate-spin" /> Typesetting…
                </>
              ) : (
                <>
                  <Printer /> Render PDF
                </>
              )}
            </Button>
            <Button
              variant={suggested === 'docx' ? 'default' : 'outline'}
              onClick={downloadDocx}
              disabled={loadingYaml}
            >
              <FileText /> Download .docx
            </Button>
          </div>
          {suggested && (
            <p className="text-xs text-muted-foreground">
              Suggested template{field ? ` for ${field}` : ''}:{' '}
              <span className="font-medium text-foreground">
                {suggested === 'rendercv'
                  ? 'Typst PDF — CS/tech format'
                  : 'Word .docx — business/VMH format'}
              </span>
              . This is just a default — use either output.
            </p>
          )}
          <p className="text-xs text-muted-foreground">
            Application folders appear in the picker once generated with{' '}
            <code className="rounded bg-muted px-1 font-mono">python -m job_bot.generate --renderer rendercv</code>.
            The .docx uses the classic python-docx renderer — for application sources it downloads the
            already-generated file; YAML edits only affect the Typst PDF.
          </p>

          <label>
            <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              RenderCV YAML — this is the resume: reorder bullets, rewrite wording, add/remove sections (JSON
              is valid YAML)
            </span>
            <Textarea
              value={loadingYaml ? 'Loading…' : yaml}
              onChange={(e) => setYaml(e.target.value)}
              disabled={loadingYaml}
              spellCheck={false}
              className="min-h-[26rem] font-mono text-xs leading-relaxed"
            />
          </label>

          {rendering && (
            <p className="text-xs text-muted-foreground">
              The rendercv CLI typesets via Typst — usually 10–30s. Hang tight.
            </p>
          )}
          {error && <p className="whitespace-pre-wrap text-sm text-destructive">{error}</p>}
        </CardContent>
      </Card>

      {out?.pdf_b64 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Rendered PDF</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                onClick={() =>
                  downloadBlob(b64ToBytes(out.pdf_b64!).buffer as ArrayBuffer, out.pdf_name ?? 'resume.pdf', 'application/pdf')
                }
              >
                <Download /> resume.pdf
              </Button>
              <Button variant="outline" onClick={() => downloadBlob(yaml, 'resume.yaml', 'text/plain')}>
                <Download /> resume.yaml
              </Button>
              {out.typ && (
                <Button variant="outline" onClick={() => downloadBlob(out.typ!, 'resume.typ', 'text/plain')}>
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
              title="Rendered resume PDF"
              src={`data:application/pdf;base64,${out.pdf_b64}`}
              className="h-[48rem] w-full rounded-lg border border-border"
            />
          </CardContent>
        </Card>
      )}
    </div>
  )
}
