# Company Tracker Refactor — Implementation Plan

## Baseline (2026-07-09)
- **Total applications**: 53 companies
- **Positions**: 101
- **Funnel breakdown**: offer=0, interviewing=0, in_review=0, ghosted=21, rejected=32
- **Reached interview**: 6 companies
- **By field**: Tax=14, Audit & Assurance=14, Finance/FP&A=11, Internal Audit=10, Data=1, IT Audit=1, Other=1, Risk=1

## Critical Constraint
**`job_bot.applications.summary()` must return identical counts before, during, and after each major step.**
- Verify with: `python3 coach_snapshot.py .` → check `funnel.total` and `funnel.by_status`
- After each major step, compare to baseline above

---

## Phase 1: Database Schema + Core Module

### 1.1 Add `companies` table to db.py schema
- Fields: id, name, name_normalized (unique), career_site_url, ats_platform, portals (JSON), target_fields (JSON), tier, notes, last_checked, next_check_due, created_at
- Add to SCHEMA string in db.py
- Add migration function in `_migrate()` to create the table idempotently

### 1.2 Create `job_bot/companies.py` CRUD module
```python
- class Company(dataclass or dict)
- insert(name, **kwargs) -> id
- update(id, **kwargs)
- get(id) -> Company
- list(due_for_check=False) -> List[Company]
- due_for_check() -> List[Company]  # where next_check_due <= today
- mark_checked(id, next_check_in_days=7) -> update next_check_due to today+7
- by_name_normalized(name) -> Company or None
- get_or_create(name, **kwargs) -> (Company, created: bool)
```

### 1.3 Test that applications.summary() still works
- Run `coach_snapshot.py` → verify funnel counts identical to baseline

**VERIFY CHECKPOINT:** Applications funnel counts = baseline

---

## Phase 2: Data Migration

### 2.1 Create migration script: `job_bot/migrate_companies.py`
```python
- Extract distinct companies from jobs table (~53 companies)
- Normalize names using applications.canon()
- Dedupe by name_normalized
- For each company:
  - Create companies row
  - Parse career_site_url from jobs.url (where available)
  - Parse ats_platform from jobs.site or url (Workday, Greenhouse, iCIMS, etc.)
  - Parse portals from jobs.site (Indeed, LinkedIn, Jobright, etc.)
  - Set target_fields from applications.classify_field() on all roles for that company
  - Set tier (Big4, mid-tier, boutique, other) based on master_profile.json
  - Set created_at to earliest job.date_posted for that company
  - Set last_checked = today, next_check_due = today + 7 days
- Backup existing db before running
- Print migration summary (X companies created)
```

### 2.2 Run migration on a copy of the real DB
- cp data/job_bot.db → scratchpad/job_bot_backup.db
- Run migration on the copy
- Verify company count = 53
- Run `coach_snapshot.py` → verify funnel counts identical

### 2.3 Merge migration into main DB
- cp scratchpad/job_bot_backup.db → data/job_bot.db (if successful)
- Run migration on real DB
- Final verification: `coach_snapshot.py`

**VERIFY CHECKPOINT:** Applications funnel counts = baseline, 53 companies in table

---

## Phase 3: Deprecate Search Pipeline

### 3.1 Create `job_bot/deprecated/` package
- Move files (don't delete):
  - search_jobs.py
  - jobsearch.py
  - score_job.py
  - jobright.py
- Update imports in these files if needed (change `from . import` to relative imports)
- Create `__init__.py` with a deprecation notice

### 3.2 Update pipeline.py
- Remove or gate job-search entry points behind `--legacy-search` flag
- Document in comments that the search pipeline is deprecated

### 3.3 Keep (do not move):
- legitimacy.py (still useful for manual job paste)
- jd_parser.py (still useful for manual job paste)
- scrape_log table (historical data)

**VERIFY CHECKPOINT:** No imports from deprecated/ in main codebase; applications still work

---

## Phase 4: Manual Intake Flow

### 4.1 Create CLI command: `job_bot/commands/intake.py`
```python
def add_job_manual(
    url: str,
    company_name: str,
    title: str,
    portal: str,  # indeed | linkedin | jobright | glassdoor | ziprecruiter | workday | handshake | smith_portal
    status: str = "applied",  # applied | saved
    notes: str | None = None
) -> dict:
    """Log a job John found and applied to manually.
    
    Returns: { id, company_id, company_name, job_title, url, status, portal, logged_at }
    """
    # 1. Normalize company name
    company_disp = canon(company_name)
    
    # 2. Get or create companies row
    company_id = companies.get_or_create(company_disp)[0]["id"]
    
    # 3. Create jobs entry
    job_id = db.execute("""
        INSERT INTO jobs (title, company, url, site, status, created_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
    """, (title, company_disp, url, portal, status)).lastrowid
    
    return { ... }
```

### 4.2 Wire CLI entry point in `job_bot/cli.py` or `__main__.py`
- `python -m job_bot intake --url <url> --company <name> --title <title> --portal <portal>`
- Test with a fake posting

### 4.3 Wire API endpoint in `job_bot/api.py`
- `POST /api/intake` → same logic, returns JSON
- Test with curl/requests

**VERIFY CHECKPOINT:** Manual intake creates job + company; applications still work

---

## Phase 5: UI Update

### 5.1 Create React component: `web/src/components/CompanyTrackerTab.tsx`
- Fetch `/api/companies?due_for_check` (or all companies)
- Table columns: Company | Tier | Portals | Roles | Last Checked | Next Check Due | Actions (edit, mark checked)
- "Mark checked today" button → PATCH /api/companies/{id} next_check_due = today + 7
- Side action: "Add new company" link → form or modal to create manual entry
- Sort by: next_check_due asc (due soonest first)

### 5.2 Update `web/src/components/App.tsx`
- Replace or hide the old job-search view
- Add company tracker to the sidebar nav (or replace search tab)
- Test in browser

### 5.3 Create API endpoints in `job_bot/api.py`
```
GET /api/companies — list all
GET /api/companies?due_for_check=true — due soon
GET /api/companies/{id} — single
POST /api/companies — create (manual)
PATCH /api/companies/{id} — update (mark checked)
DELETE /api/companies/{id} — (optional: soft-delete)
```

**VERIFY CHECKPOINT:** UI loads, company tracker displays 53 companies, applications still work

---

## Phase 6: Testing

### 6.1 Add tests in `tests/test_companies.py`
- CRUD: insert, update, get, list
- due_for_check() logic
- get_or_create() idempotence
- Name normalization edge cases

### 6.2 Add tests in `tests/test_applications.py`
- Verify summary() counts unchanged after migration
- Verify manual intake job appears in applications

### 6.3 Add integration test in `tests/test_intake.py`
- Call intake CLI → job appears in DB + applications

### 6.4 Run full suite: `python -m pytest tests/`

**VERIFY CHECKPOINT:** All tests pass

---

## Phase 7: Documentation

### 7.1 Update `README.md`
- Remove reference to search pipeline (or move to "Legacy" section)
- Document new company-tracker-first workflow
- Update "Quick start" if CLI changed

### 7.2 Update `CLAUDE.md`
- Document the new manual intake flow
- Note deprecated search pipeline (if coaching needs to know)

### 7.3 Update `daily_pipeline_prompt.md`
- If it references search, update it

**VERIFY CHECKPOINT:** Documentation is clear and current

---

## Phase 8: Final Verification

### 8.1 Baseline one more time
```bash
python3 coach_snapshot.py .
```
Compare `funnel.total` (should be 53) and `funnel.by_status` to baseline.

### 8.2 Run full test suite
```bash
python -m pytest tests/ -v
```

### 8.3 Boot the app
```bash
uvicorn job_bot.api:app --reload
```
- Smoke-test: Applications tab loads with 53 companies
- Smoke-test: Company Tracker tab loads, shows all 53
- Smoke-test: Manual intake form works
- Smoke-test: Applications funnel still matches coach_snapshot

### 8.4 Verify git diff
- Deprecated files are in `job_bot/deprecated/`
- No stray imports from deprecated/
- applications.py is unchanged
- db.py schema only added (not removed)

---

## Execution Order

1. Phase 1: Schema + CRUD
2. Verify → checkpoint
3. Phase 2: Migration script + backup/run
4. Verify → checkpoint
5. Phase 3: Deprecate search pipeline
6. Verify → checkpoint
7. Phase 4: Manual intake CLI + API
8. Verify → checkpoint
9. Phase 5: UI overhaul
10. Verify → checkpoint
11. Phase 6: Tests
12. Verify → checkpoint
13. Phase 7: Documentation
14. Phase 8: Final smoke-test & release

---

## Rollback Plan

If funnel counts diverge at any checkpoint:
1. Restore from scratchpad/job_bot_backup.db
2. Revert changes to db.py / applications.py / job_bot/ modules
3. Investigate why counts changed (likely a dedupe or name-canon issue)
4. Re-run checkpoint to confirm
5. Proceed with next phase

---

## Notes

- **Name canonicalization**: Use `applications.canon()` consistently throughout migrations and intake flow — it's the dedupe key
- **Idempotency**: Migration script should be re-runnable (INSERT OR IGNORE on unique name_normalized)
- **Backward compatibility**: Keep jobs table intact; don't modify existing schema columns
- **Testing cadence**: Run `coach_snapshot.py` after every major change to catch funnel breaks early
