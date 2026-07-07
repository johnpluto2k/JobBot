"""Phase 8: assisted application autofill.

Maps the master profile to the fields a job application typically asks for, and
(when Playwright + a browser are available) opens the application URL and fills
matching fields. It deliberately does NOT auto-submit — you review and submit,
which respects site terms and avoids costly mistakes.

Without a browser, it emits a copy-paste "answer sheet" so you can fill any form
quickly by hand.
"""

from __future__ import annotations

import re
from pathlib import Path

from .db import connect


def build_answer_map(profile: dict) -> list[tuple[str, str]]:
    """Return ordered (field-label-regex, value) pairs. First match wins."""
    p = profile.get("personal", {})
    name = (p.get("name") or "").strip()
    first, last = (name.split()[0] if name else ""), (name.split()[-1] if name else "")
    edu = (profile.get("education") or [{}])[0]
    exp = (profile.get("experience") or [{}])[0]
    loc = p.get("location") or ""
    city = loc.split(",")[0].strip() if "," in loc else loc
    state = loc.split(",")[-1].strip() if "," in loc else ""

    pairs: list[tuple[str, str]] = [
        (r"first[\s_]*name", first),
        (r"last[\s_]*name|surname|family[\s_]*name", last),
        (r"full[\s_]*name|^name$|your name|legal name", name),
        (r"e-?mail", p.get("email") or ""),
        (r"phone|mobile|tel", p.get("phone") or ""),
        (r"linkedin", p.get("linkedin") or ""),
        (r"github", p.get("github") or ""),
        (r"city", city),
        (r"state|province", state),
        (r"location|address", loc),
        (r"school|university|college|institution", edu.get("school") or ""),
        (r"degree", edu.get("degree") or ""),
        (r"major|field of study|discipline|concentration", edu.get("major") or "Accounting"),
        (r"gpa", str(edu.get("gpa") or "")),
        (r"graduat|expected.*grad|completion date", edu.get("graduation_date") or ""),
        (r"current.*(company|employer)|employer", exp.get("organization") or ""),
        (r"current.*(title|position)|job title|position", exp.get("role") or ""),
    ]
    return [(pat, val) for pat, val in pairs if val]


def answer_sheet(profile: dict) -> str:
    rows = build_answer_map(profile)
    seen, lines = set(), ["# Application answer sheet", ""]
    labels = {
        "first": "First name", "last": "Last name", "full": "Full name", "mail": "Email",
        "phone": "Phone", "linkedin": "LinkedIn", "github": "GitHub", "city": "City",
        "state": "State", "location": "Location", "school": "School", "degree": "Degree",
        "major": "Major", "gpa": "GPA", "graduat": "Graduation date",
        "company": "Current employer", "title": "Current title",
    }
    for pat, val in rows:
        key = next((k for k in labels if k in pat), pat)
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"- **{labels.get(key, key)}:** {val}")
    return "\n".join(lines)


def autofill_url(url: str, profile: dict, submit: bool = False,
                 headless: bool = False, screenshot: Path | None = None) -> dict:
    """Open the URL and fill matching fields. Returns a summary dict. Never
    submits unless submit=True (off by default)."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return {"ok": False, "reason": f"Playwright not available ({exc})", "filled": []}

    answers = build_answer_map(profile)
    filled: list[str] = []
    try:
        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch(headless=headless)
            except Exception as exc:
                return {"ok": False,
                        "reason": f"No browser binary ({exc}). Run: python -m playwright install chromium",
                        "filled": []}
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)

            controls = page.query_selector_all("input, textarea, select")
            for el in controls:
                try:
                    itype = (el.get_attribute("type") or "").lower()
                    if itype in ("hidden", "submit", "button", "file", "password", "checkbox", "radio"):
                        continue
                    label = _control_label(page, el)
                    if not label:
                        continue
                    for pat, val in answers:
                        if re.search(pat, label):
                            tag = el.evaluate("e => e.tagName.toLowerCase()")
                            if tag == "select":
                                _select_option(el, val)
                            else:
                                el.fill(val)
                            filled.append(f"{label[:40]} = {val}")
                            break
                except Exception:
                    continue

            if screenshot:
                screenshot.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(screenshot), full_page=True)

            if submit:
                btn = page.query_selector("button[type=submit], input[type=submit]")
                if btn:
                    btn.click()
                    filled.append("[submitted]")
            else:
                # leave the page open briefly for the human if not headless
                if not headless:
                    page.wait_for_timeout(1500)
            browser.close()
        return {"ok": True, "filled": filled, "submitted": submit}
    except Exception as exc:
        return {"ok": False, "reason": str(exc), "filled": filled}


def _control_label(page, el) -> str:
    parts = []
    for attr in ("name", "id", "aria-label", "placeholder"):
        v = el.get_attribute(attr)
        if v:
            parts.append(v)
    # associated <label for=id>
    eid = el.get_attribute("id")
    if eid:
        lab = page.query_selector(f"label[for='{eid}']")
        if lab:
            parts.append(lab.inner_text())
    return " ".join(parts).lower()


def _select_option(el, val: str) -> None:
    low = val.lower()
    for opt in el.query_selector_all("option"):
        if low in (opt.inner_text() or "").lower():
            el.select_option(value=opt.get_attribute("value"))
            return


def mark_status(url: str, status: str) -> bool:
    con = connect()
    cur = con.execute("UPDATE jobs SET status=? WHERE url=?", (status, url))
    con.commit()
    changed = cur.rowcount
    con.close()
    return bool(changed)
