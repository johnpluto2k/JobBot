# Privacy policy

Job Bot is a personal, self-hosted tool. Each copy runs on its owner's own
computer at `http://localhost:8000` and is used only by that person.

## What it accesses

When you sign in with Google, Job Bot asks for:

- your basic profile and email address, to sign you in to your own dashboard;
- **read-only** access to Gmail (`gmail.readonly`), to find job-application
  email such as receipts, assessments, interview invitations and rejections.

It cannot send, delete, label or modify email.

## What it stores, and where

Classified email details (date, sender, subject, company, category, and the
role named) and your Google refresh token are stored in files under the
`data/` folder on your own computer. Nothing is uploaded to a server run by the
author, and nothing is sold or shared.

The only outside services contacted are Google (to read your mail) and, if you
configure an API key, the Anthropic API for writing and coaching features, which
receives the text you ask it to work on.

## Removing access

Delete the `data/` folder to erase everything Job Bot stored, and revoke its
access at any time at <https://myaccount.google.com/permissions>.

## Contact

Questions: open an issue at <https://github.com/johnpluto2k/JobBot/issues>.
