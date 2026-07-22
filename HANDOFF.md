# Job Bot Company Tracker Refactor — Handoff Document

**Date**: 2026-07-10  
**Session**: Company-first tracker implementation complete  
**Status**: ✅ COMPLETE & TESTED — Ready for deployment  
**Branch**: `overhaul/resume-and-filter`  

---

## What Was Accomplished

### Phase 1: Backend Refactor (Commit 412bf4c)
**Database & API** — Retired internal job search engine, added company-first tracking system.

**Key files created**:
- `job_bot/companies.py` — CRUD module (insert, get, list, due_for_check, mark_checked, update)
- `job_bot/intake.py` — Manual intake flow (CLI + API endpoint POST /api/intake)
- `job_bot/migrate_companies.py` — Seeded 53 companies from applications data
- `job_bot/deprecated/` — Moved search pipeline (search_jobs.py, jobsearch.py, score_job.py, jobright.py)
- `tests/test_companies.py`, `test_intake.py` — Full test coverage

**Key files modified**:
- `job_bot/db.py` — Added companies table schema (13 fields)
- `job_bot/api.py` — Added /api/intake, /api/companies endpoints
- `job_bot/newgrad.py`, `portals.py` — Updated imports to deprecated locations

**API endpoints**:
- POST `/api/intake` — Log a job manually
- GET `/api/companies` — List all or filter overdue
- GET `/api/companies/{id}` — Get one company
- PATCH `/api/companies/{id}` — Mark checked, reschedule

### Phase 2: Frontend UI (Commit 73d524b)
**React component** — Company tracker table with filtering, check-in buttons.

**Key files created**:
- `web/src/components/CompanyTrackerTab.tsx` — Full-featured company tracker UI (table, filters, KPI cards)

**Key files modified**:
- `web/src/lib/api.ts` — Added Company interface + companies() endpoint call
- `web/src/App.tsx` — Integrated CompanyTrackerTab into navigation (added Companies tab in Pipeline section)

### Phase 3: Testing & Bug Fixes (Commit f1a3738 + 8728448)
**Playwright end-to-end test** — All functionality verified in browser.

**Bug fixed**:
- JSON field parsing — portals/target_fields are JSON strings in DB, added parseJsonField() helper
- Process PATH resolution — npm subprocess now uses shutil.which()

**Test files created**:
- `test_ui_fixed.py` — Main end-to-end test (starts backend + frontend, opens browser)
- `test_api_direct.py` — Direct API endpoint testing
- `UI_TEST_REPORT.md` — Complete test results documentation

**Results**:
- ✅ Backend API — All endpoints working (54 companies in DB)
- ✅ Frontend — Loads correctly, navigation working
- ✅ Companies tab — 54 entries displayed, filtering works
- ✅ Check-in button — Functional, updates state
- ✅ 5 screenshots captured showing full flow

---

## Critical Constraint: VERIFIED ✅

**`applications.summary()` output identical before/after refactor.**

This is the canonical funnel used by the coaching skill and daily check-in. It must NEVER break.

**Before & After**:
- Total: 53 companies ✅
- By status: offer=0, interviewing=0, in_review=0, ghosted=21, rejected=32 ✅
- Interview rate: 11% ✅
- Response rate: 60% ✅

---

## Architecture Overview

### Old Flow (Retired)
```
Internal search → Score jobs → Recommend matches → Apply
❌ Results: irrelevant (Clinical Medical Physics, Police Aide as "top matches")
```

### New Flow (Implemented)
```
John searches LinkedIn/Indeed/Jobright manually
    ↓
John applies
    ↓
Logs via: python -m job_bot.intake "<url>" "<company>" "<title>" --portal linkedin
    ↓
Bot tracks company, schedules 7-day check-in
    ↓
UI shows all companies + overdue list
    ↓
John clicks "Check" to mark reviewed, reschedule
```

### Data Flow
```
Database (SQLite: companies table)
    ↓
Backend API (FastAPI: /api/companies endpoints)
    ↓
Frontend (React: CompanyTrackerTab component)
    ↓
User sees table + filters + check-in buttons
```

---

## How to Run

### Development Environment

**1. Start backend**:
```bash
python -m job_bot.api
# Listens on http://127.0.0.1:8000
```

**2. Start frontend** (separate terminal):
```bash
cd web
npm run dev
# Vite server on http://localhost:5173
# Proxies /api/* to backend
```

**3. Open browser**:
- Navigate to http://localhost:5173
- Click "Companies" tab in sidebar
- See table with 53-54 companies

### Logging a Job Manually

```bash
python -m job_bot.intake \
  "https://linkedin.com/jobs/123" \
  "KPMG" \
  "Senior Auditor" \
  --portal linkedin \
  --status applied
```

### Testing

**Full end-to-end test**:
```bash
python test_ui_fixed.py
# Starts backend + frontend, opens browser, tests all functionality
# Takes ~30 seconds, saves screenshots to screenshots/
```

**API test only**:
```bash
python test_api_direct.py
# Tests /api/companies, /api/summary, /api/applications
# No browser required, fast verification
```

---

## Current Database State

**File**: `data/job_bot.db`

**Tables**:
- `companies` (54 entries) — 53 original + 1 test entry
- `jobs`, `tracked_emails`, `interviews`, `rejections`, `offers` — Unchanged
- All other tables — Untouched

**Backup**: `data/job_bot.db.backup_before_companies` (for rollback if needed)

---

## File Locations & Importance

### Core Implementation
| File | Purpose | Status |
|------|---------|--------|
| `job_bot/companies.py` | CRUD module | ✅ Core |
| `job_bot/intake.py` | Manual intake | ✅ Core |
| `job_bot/db.py` | Schema (companies table) | ✅ Modified |
| `job_bot/api.py` | API endpoints | ✅ Modified |
| `web/src/components/CompanyTrackerTab.tsx` | UI component | ✅ Core |
| `web/src/App.tsx` | Routing | ✅ Modified |
| `web/src/lib/api.ts` | Type definitions | ✅ Modified |

### Tests
| File | Purpose |
|------|---------|
| `tests/test_companies.py` | CRUD tests |
| `tests/test_intake.py` | Intake validation |
| `test_ui_fixed.py` | E2E browser test |
| `test_api_direct.py` | API endpoint test |

### Documentation
| File | Purpose |
|------|---------|
| `REFACTOR_COMPLETE.md` | Full architecture doc |
| `UI_TEST_REPORT.md` | Test results |
| `HANDOFF.md` | This file |

### Deprecated (Safe, Not Deleted)
| File | Status |
|------|--------|
| `job_bot/search_jobs.py` | Moved to deprecated/ |
| `job_bot/jobsearch.py` | Moved to deprecated/ |
| `job_bot/score_job.py` | Moved to deprecated/ |
| `job_bot/jobright.py` | Moved to deprecated/ |

---

## What Works ✅

- [x] Companies table created and seeded
- [x] CRUD operations (insert, get, list, due_for_check, mark_checked)
- [x] Manual intake (CLI + API)
- [x] Backend API endpoints all working
- [x] Frontend component rendering
- [x] Table display with 54 companies
- [x] Filter buttons (All/Overdue)
- [x] Check-in button functionality
- [x] applications.summary() output unchanged
- [x] All existing features (coaching, growth, offers) untouched
- [x] Tests passing
- [x] E2E browser test passing
- [x] Screenshots captured and verified

---

## What's Left (If Any)

**Nothing blocking deployment.**

Optional future work:
- Dashboard exploration (separate task: see explore-mode-request.md in memory)
- Job alert management per-company
- Recruiter outreach tracking
- Custom check-in cadence (hardcoded to 7 days now, could be per-company)
- UI polish (currently functional, not designed)

---

## Git Status

**Current branch**: `overhaul/resume-and-filter`

**Recent commits**:
```
8728448 Test: End-to-end UI test PASSED
f1a3738 Fix: Parse JSON fields in CompanyTrackerTab
73d524b Phase 2: Company tracker UI
412bf4c Phase 1: Company-first tracker refactor
```

**Ready to merge** to main when:
1. Product owner confirms scope (✅ done in this session)
2. Tests pass (✅ all pass)
3. Code review (next step)

---

## Known Issues & Gotchas

### 1. JSON Fields in Database
**What**: `portals` and `target_fields` are stored as JSON strings in DB  
**Why**: SQLite doesn't have native JSON types; stored as text  
**Frontend handling**: Component uses `parseJsonField()` helper to parse before rendering  
**Status**: ✅ Fixed in commit f1a3738

### 2. Test Intake Entry
**What**: DB has 54 companies (53 + 1 "Test Corp" from manual testing)  
**Why**: We logged a test job to verify intake flow  
**Impact**: None — applications.summary() still shows 53 (correct, deduped)  
**Action**: Safe to keep or delete from DB if desired

### 3. Subprocess PATH on Windows
**What**: subprocess.Popen couldn't find npm without full path  
**Why**: Windows PATH resolution differs from Unix  
**Solution**: Used `shutil.which("npm")` to get full path  
**Status**: ✅ Fixed in test_ui_fixed.py

### 4. Check-in Cadence Hardcoded to 7 Days
**What**: All companies marked checked → reschedule for exactly 7 days  
**Why**: Simplification for MVP  
**Future**: Could make this per-company or customizable  
**Status**: ✅ Works as is, enhancement if needed

---

## Verification Checklist for Next Session

**When you pick this up**:

- [ ] Run `python test_ui_fixed.py` to verify everything still works
- [ ] Check git log to confirm all 6 commits are there
- [ ] Verify `data/job_bot.db` exists and has companies table
- [ ] Run `python -c "from job_bot import applications; print(applications.summary())"` — should show 53 companies
- [ ] Spot check: `python -m job_bot.intake "<url>" "<company>" "<title>" --portal linkedin` creates an entry
- [ ] Frontend loads: `cd web && npm run dev` then http://localhost:5173

---

## Memory Files to Review

Check `~/.claude/projects/C--ClaudeProjects-Job-Bot/memory/`:
- `company-tracker-complete.md` — Project completion status
- `project-status.md` — Overall Job Bot status
- `user-john-bae.md` — User context (targets IT Audit, DMV)
- `phase-2-tech-v4-pending.md` — Separate resume work (not related)
- `explore-mode-request.md` — Future work on dashboard exploration

---

## Next Steps After Handoff

### Immediate (If Deploying)
1. Code review on GitHub (`overhaul/resume-and-filter` branch)
2. Merge to main
3. Deploy backend + frontend
4. Manual smoke test in production

### Near Term (If Continuing Development)
1. Dashboard exploration (make it surface new/adjacent roles)
2. Job alert management
3. Recruiter tracking

### Testing
- Verify with actual user (John) navigating the UI
- Test manual intake flow end-to-end
- Monitor applications funnel for any regressions

---

## Contact Points

**If questions arise**:
- Check REFACTOR_COMPLETE.md for full architecture
- Check UI_TEST_REPORT.md for test results
- Check CLAUDE.md in project root for workflow documentation
- Check memory/ for project context

**Key decisions made this session**:
1. Retire search pipeline (deprecate, don't delete)
2. Manual intake only (no auto-scraping)
3. 7-day check-in cadence (simple, effective)
4. React component over Streamlit (consistency with existing UI)

---

**Status**: ✅ READY FOR HANDOFF  
**All tests passing** | **All documentation updated** | **No blockers**

Good luck! 🚀
