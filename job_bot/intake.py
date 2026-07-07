"""Personal data intake: import John's own spreadsheets into the system.

Two importers, both reusable (re-run after you update the sheets):

  • import_alumni()  — the PSE alumni workbook  → connections (tagged 'pse')
  • import_tracker() — the Internship & Job Tracker → jobs + rejections

SECURITY: the job tracker contains a reused password in free-text columns. This
module hard-excludes those columns (`Details`, `Applicant Portal`, and anything
whose header mentions password/login/credential) — they are never read into the
database, an output file, or logs. Only Company / Position / Date / Status are
imported.
"""

from __future__ import annotations

from pathlib import Path

from .connections import import_records
from .db import connect

# Columns from the tracker that may hold credentials — never imported.
SENSITIVE_COLS = {"details", "applicant portal", "portal", "password", "passwords",
                  "login", "username", "user name", "credentials", "pw"}

# Tracker status -> system job status.
STATUS_MAP = {
    "submitted": "applied", "applied": "applied", "in review": "applied",
    "interview": "interview", "interviewing": "interview", "phone screen": "interview",
    "assessment": "interview", "offer": "offer", "accepted": "offer",
    "rejected": "rejected", "declined": "rejected", "withdrawn": "rejected",
    "ghosted": "rejected",
}


def _find_header_row(path: Path, sheet: str, markers=("company", "position")) -> int:
    import pandas as pd
    raw = pd.read_excel(path, sheet_name=sheet, header=None)
    for i in range(min(40, len(raw))):
        low = " | ".join(str(c).strip().lower() for c in raw.iloc[i].tolist() if str(c) != "nan")
        if sum(m in low for m in markers) >= 2:
            return i
    return 0


def import_alumni(path: str | Path, sheet: str = "Alumni",
                  relationship: str = "pse", replace: bool = True) -> int:
    """Import the PSE alumni sheet as connections."""
    import pandas as pd

    path = Path(path)
    df = pd.read_excel(path, sheet_name=sheet)
    records = df.to_dict("records")
    if replace:
        con = connect()
        con.execute("DELETE FROM connections WHERE source=?", (path.name,))
        con.commit()
        con.close()
    return import_records(records, default_relationship=relationship, source=path.name)


def import_tracker(path: str | Path, sheet: str = "Internship & Job Tracker",
                   replace: bool = True) -> dict:
    """Import the job tracker into the jobs table (+ rejections), excluding any
    credential-bearing columns. Returns counts."""
    import pandas as pd

    from .rejections import log_rejection

    path = Path(path)
    hdr = _find_header_row(path, sheet)
    df = pd.read_excel(path, sheet_name=sheet, header=hdr)

    # Drop sensitive columns up front so they are never in memory beyond this read.
    safe_cols = [c for c in df.columns if str(c).strip().lower() not in SENSITIVE_COLS]
    df = df[safe_cols]

    def col(*names):
        for n in names:
            for c in df.columns:
                if str(c).strip().lower() == n:
                    return c
        return None

    c_company = col("company")
    c_pos = col("position", "role", "title")
    c_date = col("date applied", "date", "applied")
    c_status = col("application status", "status")
    c_cold = col("cold apply", "cold")
    if not c_company:
        raise SystemExit("Couldn't find a 'Company' column in the tracker.")

    con = connect()
    if replace:
        con.execute("DELETE FROM jobs WHERE site='tracker'")
        con.execute("DELETE FROM rejections WHERE source='tracker'")
        con.commit()

    imported = 0
    pending_rejections: list[tuple[str, str, str | None]] = []
    last_company = None
    for _, row in df.iterrows():
        company = str(row[c_company]).strip() if pd.notna(row[c_company]) else ""
        if company:
            last_company = company
        else:
            company = last_company  # carry company down merged/blank cells
        title = (str(row[c_pos]).strip() if c_pos and pd.notna(row[c_pos]) else "")
        if not company or not title:
            continue  # skip legend/blank/continuation rows with no role

        status_raw = (str(row[c_status]).strip().lower() if c_status and pd.notna(row[c_status])
                      else "applied")
        status = STATUS_MAP.get(status_raw, "applied")
        date_applied = (str(row[c_date]).split(" ")[0] if c_date and pd.notna(row[c_date]) else None)

        con.execute(
            "INSERT INTO jobs (title, company, site, status, date_posted, market_tier) "
            "VALUES (?,?,?,?,?,?)",
            (title, company, "tracker", status, date_applied, None))
        imported += 1
        if status == "rejected":
            pending_rejections.append((company, title, date_applied))

    con.commit()
    con.close()  # release the write lock before log_rejection opens its own connection

    for company, title, date_applied in pending_rejections:
        log_rejection(company, role_title=title, stage="ats_screen",
                      source="tracker", rejected_on=date_applied)
    return {"jobs": imported, "rejections_logged": len(pending_rejections)}


def main() -> None:
    import argparse
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="Import John's alumni sheet + job tracker "
                                 "(source files live in inputs/).")
    ap.add_argument("--alumni", nargs="?", const="inputs/Alumni Spreadsheet.xlsx",
                    help="Path to the PSE alumni .xlsx (default: inputs/Alumni Spreadsheet.xlsx)")
    ap.add_argument("--alumni-sheet", default="Alumni")
    ap.add_argument("--relationship", default="pse")
    ap.add_argument("--tracker", nargs="?", const="inputs/Internship & Job Tracker.xlsx",
                    help="Path to the Internship & Job Tracker .xlsx "
                         "(default: inputs/Internship & Job Tracker.xlsx)")
    args = ap.parse_args()

    if args.alumni:
        n = import_alumni(args.alumni, sheet=args.alumni_sheet, relationship=args.relationship)
        print(f"Imported {n} alumni from {args.alumni} (tagged '{args.relationship}').")
    if args.tracker:
        res = import_tracker(args.tracker)
        print(f"Imported {res['jobs']} applications; logged {res['rejections_logged']} "
              "rejections. (Details / Applicant Portal columns were excluded — no "
              "credentials stored.)")
    if not (args.alumni or args.tracker):
        ap.print_help()


if __name__ == "__main__":
    main()
