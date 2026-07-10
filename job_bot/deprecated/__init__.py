"""Deprecated modules — do not use in new code.

As of 2026-07-09, the search and scoring pipeline has been retired in favor of
a company-first tracking model. The bot no longer searches for jobs; John finds
them manually on LinkedIn, Indeed, Jobright, etc., then logs them via the
manual intake flow.

This package contains the old search, scoring, and job-scraping modules for
reference and potential rollback only. Do not import these in new code.

If you need to re-enable the search pipeline, use the --legacy-search flag
in pipeline.py (not yet implemented; see IMPLEMENTATION_PLAN.md).
"""
