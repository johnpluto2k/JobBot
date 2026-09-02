"""Tests for the company posting watcher (job_bot/watch.py).

All offline - the HTTP layer is stubbed, so these never touch a real job board.
"""
from __future__ import annotations

import pytest

from job_bot import watch


# --- location filter ---------------------------------------------------------
@pytest.mark.parametrize("location,expected", [
    ("Washington, DC", True),
    ("McLean, VA", True),
    ("Silver Spring, Maryland", True),
    ("Remote - US", True),
    ("United States", True),
    ("Multiple Locations", True),
    ("", True),                       # unknown location is kept, not guessed at
    ("London, UK", False),
    ("Bengaluru, India", False),
    ("San Francisco, CA", False),     # real US city, just not the DMV
    ("Nevada", False),
])
def test_location_filter(location, expected):
    assert watch.location_ok(location) is expected


def test_two_letter_markers_match_on_word_boundaries():
    """Regression: 'Mumbai Shivaji Park' contains the substring 'va' (shi-VA-ji).

    A substring check accepted it as Virginia. This is the same class of bug that
    let the alias 'EY' match 'Morgan Stanley' in the inbox classifier.
    """
    assert watch.location_ok("Mumbai Shivaji Park") is False
    assert watch.location_ok("Arlington, VA") is True


def test_foreign_beats_remote():
    """Regression: 'remote' used to be checked before the foreign filter."""
    assert watch.location_ok("Toronto, Remote-Canada") is False
    assert watch.location_ok("Chicago, US-Remote, Canada") is False
    assert watch.location_ok("Remote U.S.") is True


def test_anywhere_mode_keeps_other_us_cities():
    assert watch.location_ok("San Francisco, CA", dmv_only=False) is True
    assert watch.location_ok("London, UK", dmv_only=False) is False


# --- fetchers ----------------------------------------------------------------
class _Resp:
    def __init__(self, payload, status=200):
        self._payload, self.status_code = payload, status

    def json(self):
        return self._payload


class _FakeRequests:
    def __init__(self, payload, status=200):
        self._payload, self._status = payload, status
        self.calls = []

    def get(self, url, **kw):
        self.calls.append(("GET", url, kw))
        return _Resp(self._payload, self._status)

    def post(self, url, **kw):
        self.calls.append(("POST", url, kw))
        return _Resp(self._payload, self._status)


def test_ashby_parses_postings(monkeypatch):
    payload = {"data": {"jobBoard": {"jobPostings": [
        {"id": "abc123", "title": "Risk Analyst", "locationName": "Remote - US"},
        {"id": "def456", "title": "Senior Risk Manager", "locationName": "Remote - US"},
        {"id": "ghi789", "title": "Chef", "locationName": "Remote - US"},
    ]}}}
    monkeypatch.setattr(watch, "_requests", lambda: _FakeRequests(payload))
    rows = watch._fetch_ashby("vanta", ["risk"])
    # senior role dropped, non-matching title dropped
    assert [r["title"] for r in rows] == ["Risk Analyst"]
    assert rows[0]["url"] == "https://jobs.ashbyhq.com/vanta/abc123"
    assert rows[0]["site"] == "ashby"


def test_smartrecruiters_requires_positive_total_found(monkeypatch):
    """The API returns HTTP 200 with totalFound=0 for ANY token, real or not.

    Treating a 200 as proof the board exists produced ~190 false-positive boards
    in an earlier sweep, so a zero total must yield nothing.
    """
    empty = {"totalFound": 0, "content": [{"id": "1", "name": "Audit Analyst"}]}
    monkeypatch.setattr(watch, "_requests", lambda: _FakeRequests(empty))
    assert watch._fetch_smartrecruiters("not-a-real-company", ["audit"]) == []

    real = {"totalFound": 1, "content": [
        {"id": "1", "name": "Audit Analyst", "location": {"city": "Arlington", "region": "VA"}}]}
    monkeypatch.setattr(watch, "_requests", lambda: _FakeRequests(real))
    rows = watch._fetch_smartrecruiters("servicenow", ["audit"])
    assert len(rows) == 1
    assert rows[0]["location"] == "Arlington, VA"


def test_workday_dedupes_across_keyword_searches(monkeypatch):
    """The same posting comes back for several searchText values; count it once."""
    payload = {"jobPostings": [
        {"title": "Audit Associate", "externalPath": "/job/abc", "locationsText": "McLean, VA"},
    ]}
    fake = _FakeRequests(payload)
    monkeypatch.setattr(watch, "_requests", lambda: fake)
    rows = watch._fetch_workday("x.wd1.myworkdayjobs.com", "x", "Careers", ["audit", "risk"])
    assert len(rows) == 1
    assert rows[0]["url"] == "https://x.wd1.myworkdayjobs.com/en-US/Careers/job/abc"


def test_workday_reads_location_out_of_the_title_when_the_field_is_blank(monkeypatch):
    """Regression: some tenants leave locationsText empty and append the location
    to the title instead. Those postings looked location-less, and unknown
    locations are kept, so one tenant flooded the pipeline with out-of-area roles.
    """
    payload = {"jobPostings": [
        {"title": "Audit Analyst | Memphis, TN", "externalPath": "/job/a", "locationsText": ""},
        {"title": "Audit Analyst | McLean, VA", "externalPath": "/job/b", "locationsText": ""},
    ]}
    monkeypatch.setattr(watch, "_requests", lambda: _FakeRequests(payload))
    rows = watch._fetch_workday("x.wd1.myworkdayjobs.com", "x", "Careers", ["audit"])
    kept = [r for r in rows if watch.location_ok(r["location"])]
    assert [r["location"] for r in rows] == ["Memphis, TN", "McLean, VA"]
    assert len(kept) == 1 and kept[0]["location"] == "McLean, VA"


def test_title_suffix_that_is_not_a_location_is_ignored():
    assert watch._location_from_title("Analyst | Data & Analytics") == ""
    assert watch._location_from_title("Risk Analyst | Remote") == ""
    assert watch._location_from_title("Audit Associate | McLean, VA") == "McLean, VA"


def test_workday_applies_the_keyword_filter(monkeypatch):
    """Regression: this fetcher trusted Workday's searchText and did not re-check
    the title. Tenants that ignore searchText return their whole board - Raymond
    James answered all four searches with the same 102 unrelated rows.
    """
    payload = {"jobPostings": [
        {"title": "Internal Audit Advisor", "externalPath": "/job/a", "locationsText": "McLean, VA"},
        {"title": "Trade Specialist - RJ Trust", "externalPath": "/job/b", "locationsText": "McLean, VA"},
        {"title": "Sommelier", "externalPath": "/job/c", "locationsText": "McLean, VA"},
    ]}
    monkeypatch.setattr(watch, "_requests", lambda: _FakeRequests(payload))
    rows = watch._fetch_workday("x.wd1.myworkdayjobs.com", "x", "Careers", ["audit"])
    assert [r["title"] for r in rows] == ["Internal Audit Advisor"]


def test_fetch_returns_empty_on_http_error(monkeypatch):
    monkeypatch.setattr(watch, "_requests", lambda: _FakeRequests({}, status=500))
    assert watch._fetch_ashby("vanta", ["risk"]) == []
    assert watch._fetch_smartrecruiters("x", ["risk"]) == []


# --- watch_company -----------------------------------------------------------
def test_unknown_platform_reports_error_without_raising():
    res = watch.watch_company({"name": "Acme", "ats_platform": "Taleo"}, save=False)
    assert res["error"] and "Taleo" in res["error"]
    assert res["found"] == 0


def test_fetcher_exception_is_captured_not_raised(monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("board exploded")

    monkeypatch.setitem(watch.FETCHERS, "Greenhouse", boom)
    res = watch.watch_company(
        {"name": "Acme", "ats_platform": "Greenhouse", "ats_token": "acme"}, save=False)
    assert res["error"].startswith("RuntimeError")
    assert res["found"] == 0


def test_out_of_range_rows_are_filtered(monkeypatch):
    payload = {"data": {"jobBoard": {"jobPostings": [
        {"id": "1", "title": "Risk Analyst", "locationName": "Arlington, VA"},
        {"id": "2", "title": "Risk Analyst", "locationName": "Bengaluru, India"},
    ]}}}
    monkeypatch.setattr(watch, "_requests", lambda: _FakeRequests(payload))
    res = watch.watch_company(
        {"name": "Vanta", "ats_platform": "Ashby", "ats_token": "vanta"}, save=False)
    assert res["found"] == 2
    assert res["in_range"] == 1
