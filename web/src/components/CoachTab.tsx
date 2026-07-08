import { useEffect, useRef, useState } from 'react'
import { AlertCircle, CalendarClock, Clock, Loader2, Mail, MessageCircle, Send } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { ErrorNote } from '@/components/ErrorNote'
import { api, type ChatMessage, type CoachSnapshot } from '@/lib/api'
import { useAsync } from '@/lib/useAsync'

const STARTERS = [
  'How am I doing?',
  'What should I focus on today?',
  'Am I on track?',
  "What's most time-sensitive right now?",
]

/** Time-sensitive items pulled from the live snapshot, shown above the chat so
 *  the coach's grounding is visible — not just implied. */
function ContextStrip({ snap }: { snap: CoachSnapshot }) {
  const interviews = snap.upcoming_interviews ?? []
  const followups = snap.followups_due ?? []
  const email = snap.unhandled_recruiter_email ?? []
  const items: { icon: typeof CalendarClock; tint: string; text: string }[] = []

  for (const iv of interviews.slice(0, 3)) {
    items.push({
      icon: CalendarClock,
      tint: 'var(--status-violet)',
      text: `${iv.round_name ? `${iv.round_name} · ` : ''}${iv.company}${iv.scheduled_at ? ` — ${iv.scheduled_at}` : ''}`,
    })
  }
  for (const f of followups.slice(0, 3)) {
    items.push({
      icon: Clock,
      tint: 'var(--status-amber)',
      text: `Follow up: ${f.contact_name} @ ${f.company} (due ${f.followup_date})`,
    })
  }
  for (const e of email.slice(0, 3)) {
    items.push({
      icon: Mail,
      tint: 'var(--status-blue)',
      text: `Unhandled ${e.category.replace(/_/g, ' ')}${e.company ? ` — ${e.company}` : ''}`,
    })
  }

  if (!items.length) return null
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((it, i) => (
        <span
          key={i}
          className="inline-flex max-w-full items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1 text-xs text-foreground"
        >
          <it.icon size={13} className="shrink-0" style={{ color: it.tint }} />
          <span className="min-w-0 break-words">{it.text}</span>
        </span>
      ))}
    </div>
  )
}

function Bubble({ m }: { m: ChatMessage }) {
  const isUser = m.role === 'user'
  return (
    <div className={isUser ? 'flex justify-end' : 'flex justify-start'}>
      <div
        className={
          isUser
            ? 'max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-primary px-4 py-2.5 text-sm text-primary-foreground'
            : 'max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-bl-sm border border-border bg-card px-4 py-2.5 text-sm text-foreground'
        }
      >
        {m.content}
      </div>
    </div>
  )
}

export function CoachTab() {
  const snapshot = useAsync(api.coachSnapshot, [])
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [thinking, setThinking] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Set when the coach is configured *off* (no API key). Unlike `error` (a
  // transient failure the user can retry), this permanently disables the
  // composer for the session — retrying can't fix a missing key.
  const [disabledReason, setDisabledReason] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, thinking])

  async function send(text: string) {
    const trimmed = text.trim()
    if (!trimmed || thinking || disabledReason) return
    // Optimistically show the user's turn, but remember the prior history so we
    // can roll back on failure — a dangling user turn would make the *next*
    // send two user messages in a row, which the Anthropic API rejects.
    const history = messages
    const next: ChatMessage[] = [...history, { role: 'user', content: trimmed }]
    setMessages(next)
    setInput('')
    setError(null)
    setThinking(true)
    try {
      const res = await api.coach(next)
      if (res.reply == null) {
        const msg = res.error ?? 'The coach could not respond.'
        setMessages(history)
        if (/ANTHROPIC_API_KEY/i.test(msg)) {
          setDisabledReason(msg) // no key configured — nothing to retry
        } else {
          setInput(trimmed) // transient server-side failure — let him resend
          setError(msg)
        }
      } else {
        setMessages([...next, { role: 'assistant', content: res.reply }])
      }
    } catch (e) {
      setMessages(history)
      setInput(trimmed)
      setError(String((e as Error).message ?? e))
    } finally {
      setThinking(false)
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="flex items-center gap-2 text-base font-semibold text-foreground">
          <MessageCircle size={17} style={{ color: 'var(--primary)' }} /> Career coach
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Grounded in your real pipeline — funnel, upcoming interviews, overdue follow-ups, and unhandled
          recruiter email. Ask how you're doing or what to focus on.
        </p>
      </div>

      {snapshot.data && <ContextStrip snap={snapshot.data} />}

      <Card>
        <CardContent className="flex h-[min(60vh,560px)] flex-col gap-4 p-4">
          <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto pr-1">
            {messages.length === 0 && !thinking && !disabledReason && (
              <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
                <p className="text-sm text-muted-foreground">Start with one of these, or ask your own:</p>
                <div className="flex flex-wrap justify-center gap-2">
                  {STARTERS.map((s) => (
                    <Button key={s} variant="outline" size="sm" onClick={() => send(s)}>
                      {s}
                    </Button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((m, i) => (
              <Bubble key={i} m={m} />
            ))}
            {thinking && (
              <div className="flex justify-start">
                <div className="inline-flex items-center gap-2 rounded-2xl rounded-bl-sm border border-border bg-card px-4 py-2.5 text-sm text-muted-foreground">
                  <Loader2 size={14} className="animate-spin" /> Thinking…
                </div>
              </div>
            )}
            {error && <ErrorNote error={error} title="Coach reply failed." showStartHint={false} />}
          </div>

          {disabledReason && (
            <div className="flex items-center gap-2 rounded-lg border border-border bg-muted px-3 py-2 text-sm text-muted-foreground">
              <AlertCircle size={15} style={{ color: 'var(--status-amber)' }} />
              <span>{disabledReason}</span>
            </div>
          )}

          <div className="flex items-end gap-2">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                // Ignore Enter mid-IME-composition so it doesn't send a half-typed line.
                if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault()
                  void send(input)
                }
              }}
              disabled={thinking || !!disabledReason}
              placeholder={
                disabledReason
                  ? 'Coach unavailable'
                  : 'Ask your coach…  (Enter to send, Shift+Enter for a new line)'
              }
              className="min-h-[44px] flex-1 resize-none"
            />
            <Button
              size="icon"
              onClick={() => void send(input)}
              disabled={thinking || !input.trim() || !!disabledReason}
              aria-label={disabledReason ? 'Coach unavailable' : 'Send'}
            >
              <Send />
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
