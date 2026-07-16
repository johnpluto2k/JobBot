import { Card } from '@/components/ui/card'

/** Shared error panel — the one pattern for API/action failures across tabs.
 *  Default copy is the "API unreachable" case; pass a title (and
 *  showStartHint={false}) for action-specific failures like a search error. */
export function ErrorNote({
  error,
  title = "Couldn't reach the API.",
  showStartHint = true,
}: {
  error: string
  title?: string
  showStartHint?: boolean
}) {
  return (
    <Card className="border-destructive/30 bg-destructive/5 p-6 text-sm text-destructive">
      <p className="font-medium">{title}</p>
      <p className="mt-1 whitespace-pre-wrap break-words text-destructive/80">{error}</p>
      {showStartHint && (
        <p className="mt-3 text-muted-foreground">
          Start the server from the project root:{' '}
          <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs text-foreground">
            uvicorn job_bot.api:app --port 8000
          </code>
        </p>
      )}
    </Card>
  )
}
