/** Full-page gate shown while logged out: one "Sign in with Google" action. */

function GoogleMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden>
      <path
        fill="#EA4335"
        d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
      />
      <path
        fill="#4285F4"
        d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
      />
      <path
        fill="#FBBC05"
        d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
      />
      <path
        fill="#34A853"
        d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
      />
    </svg>
  )
}

export function SignInScreen({ configured }: { configured: boolean }) {
  const next = `${window.location.origin}/`
  return (
    <div className="flex min-h-dvh items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm rounded-2xl border border-border bg-card p-8 text-center shadow-sm">
        <div
          className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl text-lg font-bold text-white"
          style={{ background: 'linear-gradient(135deg, var(--primary), #7c3aed)' }}
        >
          JB
        </div>
        <h1 className="text-lg font-semibold tracking-tight">Job Bot · Career OS</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Sign in with Google to open your dashboard and keep the Gmail tracker syncing recruiter email
          automatically.
        </p>
        {configured ? (
          <a
            href={`/auth/login?next=${encodeURIComponent(next)}`}
            className="mt-6 inline-flex w-full items-center justify-center gap-3 rounded-lg border border-border bg-background px-4 py-2.5 text-sm font-medium shadow-sm transition-colors hover:bg-muted"
          >
            <GoogleMark />
            Sign in with Google
          </a>
        ) : (
          <p className="mt-6 rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
            GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET are missing from <code>.env</code> — add them and restart
            the API.
          </p>
        )}
        <p className="mt-4 text-xs text-muted-foreground">
          Read-only Gmail scope · tokens stay on this machine
        </p>
      </div>
    </div>
  )
}
