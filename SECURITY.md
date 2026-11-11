# Security

Job Bot runs on your own machine and holds private things: your résumé, your
application history, a read-only Gmail token, and API keys. This page says how
it protects them and how to report a problem.

## How it is meant to be run

- **On localhost, for one person.** `python -m job_bot serve` binds to
  `127.0.0.1`. Don't expose the port to a network or put it behind a public
  reverse proxy; there are no user accounts.
- **Sign-in.** With a Google OAuth client in `.env`, every `/api/*` route needs
  the session cookie set by Google sign-in. Without one the app runs in *local
  mode*: no sign-in, and requests are accepted only from a loopback address
  with a loopback `Host` header.
- **Gmail is read-only.** The only Gmail scope requested is `gmail.readonly`.
  There is no code path that sends, labels or deletes mail.
- **Secrets stay local.** `.env`, `data/` (database, profile, Google token,
  session), `documents/` and the coaching files are gitignored.
- **Outbound calls** go only to services you configure: the Anthropic API,
  Google, the public job boards the watcher polls, and an optional webhook.
  See [`PRIVACY.md`](PRIVACY.md).

Email and job-posting text are treated as data. They are shown to the model as
evidence and never followed as instructions.

## Reporting a vulnerability

Please report it privately through GitHub: **Security → Report a
vulnerability** on this repository. Include steps to reproduce and what an
attacker could reach. Please don't open a public issue for something that
exposes user data.

This is a personal project maintained in spare time. Expect an acknowledgement
within a week.
