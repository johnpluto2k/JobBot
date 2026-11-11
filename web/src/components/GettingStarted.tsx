import { CheckCircle2, Circle } from 'lucide-react'
import type { ReactNode } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

function Code({ children }: { children: ReactNode }) {
  return <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs text-foreground">{children}</code>
}

function Step({ done, title, children }: { done: boolean; title: string; children: ReactNode }) {
  return (
    <li className="flex gap-3">
      {done ? (
        <CheckCircle2 size={18} className="mt-0.5 shrink-0" style={{ color: 'var(--status-green, #059669)' }} />
      ) : (
        <Circle size={18} className="mt-0.5 shrink-0 text-muted-foreground" />
      )}
      <div className="min-w-0">
        <p className={done ? 'font-medium text-muted-foreground line-through' : 'font-medium text-foreground'}>
          {title}
        </p>
        {!done && <div className="mt-1 text-sm leading-relaxed text-muted-foreground">{children}</div>}
      </div>
    </li>
  )
}

/** First-run checklist on the Overview page. Shown until there is a profile
 *  and at least one application, so a new install is never just a row of zeros. */
export function GettingStarted({
  hasProfile,
  hasApplications,
  gmailOff,
  onLogApplication,
}: {
  hasProfile: boolean
  hasApplications: boolean
  gmailOff: boolean
  onLogApplication: () => void
}) {
  if (hasProfile && hasApplications) return null
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Getting started</CardTitle>
      </CardHeader>
      <CardContent>
        <ol className="space-y-4">
          <Step done={hasProfile} title="Build your profile">
            Put your résumé (PDF, DOCX or text) in a <Code>documents/</Code> folder at the project root, then run{' '}
            <Code>python -m job_bot.build_profile</Code> and reload this page. Scoring, tailoring and cover letters
            all read the profile it writes.
          </Step>
          <Step done={hasApplications} title="Log an application">
            When you apply somewhere, record it so the funnel is real.{' '}
            <button onClick={onLogApplication} className="font-medium text-primary underline underline-offset-4">
              Open Applications
            </button>{' '}
            and choose <span className="font-medium text-foreground">Log an application</span>.
          </Step>
          <Step done={!gmailOff} title="Optional: let Gmail fill the tracker">
            With a Google OAuth client in <Code>.env</Code>, receipts, interview invites and rejections are read from
            your inbox (read-only) every 15 minutes. Steps are in <Code>docs/SETUP.md</Code>, section 3.
          </Step>
        </ol>
        <p className="mt-5 border-t border-border pt-4 text-sm text-muted-foreground">
          Want to see it full first? Stop the server and run <Code>python -m job_bot demo</Code> for a fictional
          search. <Code>python -m job_bot doctor</Code> lists what is set up.
        </p>
      </CardContent>
    </Card>
  )
}
