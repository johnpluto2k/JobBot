"""Tests for job_bot.line_fit — the line-fill measurement.

The important test is `test_reproduces_observed_line_breaks`: the width table
and column constant are only worth anything if they predict where LaTeX
actually broke John's résumé. Those nine breaks were read off the compiled PDF
of his Jake's-Resume Overleaf project on 2026-09-02. If the template's margins
or font change, that test fails first and tells you to recalibrate.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from job_bot.line_fit import (COLUMN, FULL, RAGGED, SHORT, Fit,  # noqa: E402
                              measure, target_chars, width, wrap)

# (bullet text, the line LaTeX put first) — from the rendered PDF.
OBSERVED = [
    ("Builds & ships full-stack features for a Wagyu genetics SaaS platform alongside the lead "
     "developer, spanning customer-facing interfaces, backend APIs & data models, & third-party "
     "payment integrations",
     "Builds & ships full-stack features for a Wagyu genetics SaaS platform alongside the lead "
     "developer, spanning"),
    ("Pitches the platform to Wagyu ranchers on customer sales calls, supporting the company's "
     "first paying accounts in a traditionally non-software-buying market",
     "Pitches the platform to Wagyu ranchers on customer sales calls, supporting the company's "
     "first paying accounts in"),
    ("Manages compliance-ready lease, payment, & regulatory records for 800+ tenants, "
     "strengthening internal controls, documentation accuracy, & audit preparedness across "
     "property operations",
     "Manages compliance-ready lease, payment, & regulatory records for 800+ tenants, "
     "strengthening internal controls,"),
    ("Supported faculty with grading analytics reporting dashboards, improving turnaround time, "
     "instructional consistency, & performance tracking across multiple course sections",
     "Supported faculty with grading analytics reporting dashboards, improving turnaround time, "
     "instructional"),
    ("Increased student satisfaction ratings by 15% by analyzing feedback, redesigning "
     "instructional workflows, & delivering individualized academic support to improve "
     "comprehension",
     "Increased student satisfaction ratings by 15% by analyzing feedback, redesigning "
     "instructional workflows, &"),
    ("Designed inventory tracking & procurement controls that reduced waste by 12%, improved "
     "margin visibility, & strengthened vendor accountability & financial transparency",
     "Designed inventory tracking & procurement controls that reduced waste by 12%, improved "
     "margin visibility, &"),
    ("Prepared & reviewed 30+ individual & family tax returns under IRS VITA/TCE standards, "
     "ensuring regulatory compliance, accurate documentation, & high-quality client service",
     "Prepared & reviewed 30+ individual & family tax returns under IRS VITA/TCE standards, "
     "ensuring regulatory"),
    ("Represented chapter as KPMG Case Competition semifinalist, performing AI risk analysis & "
     "proposing solutions projected to reduce hospital energy use by 80%",
     "Represented chapter as KPMG Case Competition semifinalist, performing AI risk analysis & "
     "proposing solutions"),
]


def test_reproduces_observed_line_breaks():
    """The whole model is worthless if it can't predict a real break."""
    wrong = [(text[:40], wrap(text)[0][-25:], first[-25:])
             for text, first in OBSERVED if wrap(text)[0] != first]
    assert not wrong, f"mispredicted breaks: {wrong}"


def test_observed_full_lines_all_clear_the_full_bar():
    """Every one of those first lines is, by definition, as full as LaTeX could
    make it — so FULL_AT must not be set above the tightest of them."""
    for _, first in OBSERVED:
        assert measure(first).verdict == FULL, \
            f"a genuinely full line scored {measure(first).last_fill:.2f}: {first[:50]}"


def test_ragged_bullet_is_flagged_with_a_cut_size():
    # One full line plus three words on the next.
    text = ("Reconciled monthly rent ledgers in Excel and flagged discrepancies to management "
            "across the property portfolio every month")
    fit = measure(text)
    assert fit.lines == 2
    assert fit.verdict == RAGGED
    assert fit.wastes_a_line
    assert fit.trim_chars > 0
    # Cutting the advertised number of characters really does drop it to one line.
    assert measure(text[: len(text) - fit.trim_chars]).lines == 1


def test_short_single_line_reports_room_not_a_trim():
    fit = measure("Reconciled monthly rent ledgers in Excel")
    assert fit.lines == 1
    assert fit.verdict == SHORT
    assert fit.add_chars > 0
    assert fit.trim_chars == 0


def test_mildly_short_last_line_is_still_reported():
    """The CowSync bullet fills 81% of its second line — not egregious, but not
    full, and John asked to see it. It reports RAGGED rather than being waved
    through, and the trim is the whole overflow (you cannot drop a line by
    cutting only the gap)."""
    fit = measure(OBSERVED[0][0])
    assert fit.lines == 2
    assert 0.78 < fit.last_fill < 0.85
    assert fit.verdict == RAGGED
    assert measure(OBSERVED[0][0][: -fit.trim_chars]).lines == 1


def test_a_genuinely_full_two_liner_passes():
    """The one bullet in the whole master profile that fills its last line."""
    text = ("Designed and deployed a Node.js / Express backend as serverless functions on "
            "Vercel, exposing 5 REST endpoints (read/write to Supabase Postgres + "
            "Spoonacular proxy) consumed by a vanilla-JS frontend across 5 pages.")
    fit = measure(text)
    assert fit.lines == 2
    assert fit.verdict == FULL, f"last_fill was {fit.last_fill:.2f}"
    assert fit.trim_chars == 0


def test_width_is_additive_and_column_is_one_line():
    assert width("") == 0
    assert width("ab") == width("a") + width("b")
    line = wrap("word " * 60)[0]
    assert width(line) <= COLUMN


def test_target_chars_lands_within_the_line_budget():
    text = OBSERVED[2][0]
    for n in (1, 2):
        n_chars = target_chars(text, n)
        assert measure(text[:n_chars]).lines <= n


def test_measure_normalises_whitespace():
    assert measure("  Built   a\n thing  ").lines == 1
    assert isinstance(measure("x"), Fit)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
