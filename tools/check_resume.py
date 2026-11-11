"""Check a compiled resume or cover letter PDF against the layout rules.

Run it after every compile:

    python tools/check_resume.py resume.pdf --tex resume.tex     one-page resume
    python tools/check_resume.py letter.pdf --letter             cover letter
    python tools/check_resume.py master.pdf --master             multi-page master resume

Every check prints one PASS / WARN / FAIL / SKIP line. The exit code is 1 if
any check FAILs, otherwise 0. The only dependency is pdfminer.six.

What is checked, and why:

1. Pages. A tailored resume and a cover letter are exactly one page; a
   recruiter rarely reads a second one. (--pages N changes the number,
   --master allows any length.)

2. Bullet line fill. The LAST line of every bullet must end between 92% and
   just under 100% of the way to the right margin. A bullet that stops at 60%
   wastes a third of a line; one that wraps to leave three words on a second
   line wastes most of that line. A bullet is a line whose first glyph is a
   bullet character; its text starts at the first word after the glyph, and
   wrapped lines start at that same x. Fill = (last line's right edge - text
   left) / (right margin - text left). The right margin is read from the page:
   the right end of the full-width section rules, or, when a page has no
   rules, the right edge of the widest text line (--right overrides). On a
   resume a bullet longer than one line gets a warning: the rule is one line
   per bullet. Letters skip this check; their bullets are meant to wrap.

3. Bottom gap. Blank space between the lowest text and the bottom of the
   page. A resume should fill the page (0.20-0.35in left; more than 0.6in
   fails), a letter should look like a letter (0.9-1.3in). Measured from the
   lowest glyph box, which includes the font's descender depth, so it reads
   about 0.03in smaller than a ruler on the printed ink would.

4. Bad characters. U+FFFD, or a glyph with no text mapping, means the PDF
   text layer is broken and an applicant tracking system (ATS) will read
   garbage: fail. Combining accents (U+0300-U+036F) are how LaTeX often
   encodes accented letters; parsers mangle them, so warn and suggest plain
   ASCII ("resume", "cafe"). Glyphs drawn from a bitmap (Type 3) font also
   get a warning: they print blurry and often carry no text mapping.

5. Repeated action verbs. The first word of every bullet should be different.
   A repeat fails a one-page resume and is a warning on a master resume
   (which is a superset that gets trimmed later).

6. Bullet counts (needs --tex). Counts \\resumeItem{ per entry in each
   \\section{}. Defaults: 3 per Experience entry, 3 per Projects entry, 2 per
   Leadership / Activities entry. The page is filled with whole entries, not
   by stacking extra bullets on one entry. Override with a JSON file (--counts,
   or resume/bullet_counts.json if it exists):

       {"sections": {"Experience": 3, "Projects": 3, "Leadership": 2},
        "entries": {"Data Analyst Intern": 5}}

   "entries" keys match the start of an entry's heading, ignoring case.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass, field

BULLET_GLYPHS = {"\u2022", "\u25e6", "\u2219", "\u00b7", "\u2013", "\u2012", "\u2212",
                 "-", "*", "\u25aa", "\u2023", "\u2043"}

FILL_MIN = 0.92             # last line of a bullet must reach this far
RESUME_GAP = (0.20, 0.35)   # inches of blank at the bottom of a resume
RESUME_GAP_FAIL = 0.60
LETTER_GAP = (0.90, 1.30)

DEFAULT_COUNTS = {"Experience": 3, "Projects": 3, "Leadership": 2, "Activities": 2}
DEFAULT_COUNTS_FILE = os.path.join("resume", "bullet_counts.json")

PASS, WARN, FAIL, SKIP = "PASS", "WARN", "FAIL", "SKIP"


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------
@dataclass
class Line:
    """One visual line of text: its words as (x_left, text) and its extent."""
    page: int
    x0: float
    x1: float
    y0: float          # bottom (PDF coordinates: y grows upward)
    y1: float          # top
    words: list        # [(x_left, text), ...] left to right

    @property
    def text(self):
        return " ".join(t for _, t in self.words)


@dataclass
class Bullet:
    page: int
    left: float                       # x where the bullet's text starts
    lines: list = field(default_factory=list)

    @property
    def text(self):
        first = " ".join(t for _, t in self.lines[0].words[1:])
        rest = [l.text for l in self.lines[1:]]
        return " ".join([first] + rest)

    @property
    def last_x1(self):
        return self.lines[-1].x1


@dataclass
class Result:
    name: str
    status: str
    summary: str
    details: list = field(default_factory=list)
    data: dict = field(default_factory=dict)

    def as_dict(self):
        return {"check": self.name, "status": self.status, "summary": self.summary,
                "details": self.details, **self.data}


# --------------------------------------------------------------------------
# Reading the PDF (pdfminer.six only)
# --------------------------------------------------------------------------
def read_pdf(path):
    """Return a list of pages: {"width", "height", "lines": [Line], "rules": [(x0, x1, y)]}."""
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LTChar, LTCurve, LTContainer

    pages = []
    # Only the raw glyph boxes are used; lines and words are grouped below, so
    # the result does not depend on pdfminer's own layout guessing.
    for page_no, layout in enumerate(extract_pages(path), 1):
        chars, rules, bitmap = [], [], []

        def walk(obj):
            for child in obj:
                if isinstance(child, LTChar):
                    if child.get_text().strip():
                        chars.append((child.x0, child.y0, child.x1, child.y1, child.get_text()))
                        # A Type 3 (bitmap) font has no name; pdfminer reports "unknown".
                        if child.fontname == "unknown":
                            bitmap.append(child.get_text())
                elif isinstance(child, LTCurve):        # LTLine and LTRect are LTCurves
                    if child.height < 2.0 and child.width > 0:
                        rules.append((child.x0, child.x1, child.y0))
                elif isinstance(child, LTContainer):
                    walk(child)

        walk(layout)
        pages.append({"width": layout.width, "height": layout.height,
                      "lines": group_lines(chars, page_no), "rules": rules,
                      "bitmap_glyphs": len(bitmap)})
    return pages


def group_lines(chars, page_no=1):
    """Group glyph boxes (x0, y0, x1, y1, text) into Lines, top to bottom.

    Tall glyphs claim a line first; a smaller glyph (the tiny raised bullet
    dot, for one) joins the line whose vertical span contains its centre.
    """
    rows = []   # [y0, y1, [chars]]
    for ch in sorted(chars, key=lambda c: -(c[3] - c[1])):
        centre = (ch[1] + ch[3]) / 2
        for row in rows:
            if row[0] <= centre <= row[1]:
                row[2].append(ch)
                break
        else:
            rows.append([ch[1], ch[3], [ch]])

    lines = []
    for y0, y1, members in rows:
        members.sort(key=lambda c: c[0])
        words, start, text, prev = [], None, "", None
        for ch in members:
            size = max(ch[3] - ch[1], 1.0)
            if prev is not None and ch[0] - prev[2] > max(1.0, 0.15 * size):
                words.append((start, text))
                start, text = None, ""
            if start is None:
                start = ch[0]
            text += ch[4]
            prev = ch
        if text:
            words.append((start, text))
        lines.append(Line(page=page_no, x0=members[0][0], x1=max(c[2] for c in members),
                          y0=min(c[1] for c in members), y1=max(c[3] for c in members),
                          words=words))
    lines.sort(key=lambda l: -l.y1)
    return lines


# --------------------------------------------------------------------------
# Pure checks (unit-tested without a PDF)
# --------------------------------------------------------------------------
def find_bullets(lines):
    """Group Lines (reading order, any number of pages) into Bullets."""
    bullets, cur = [], None
    for line in lines:
        w = line.words
        if len(w) > 1 and w[0][1] in BULLET_GLYPHS:
            cur = Bullet(page=line.page, left=w[1][0], lines=[line])
            bullets.append(cur)
        elif (cur is not None and line.page == cur.page
              and abs(line.x0 - cur.left) < 1.0
              and cur.lines[-1].y0 - line.y0 < 1.6 * max(line.y1 - line.y0, 8.0)):
            cur.lines.append(line)
        else:
            cur = None
    return bullets


def fill_ratio(last_x1, left, right):
    """How far a bullet's last line reaches from its text-left toward the right margin."""
    if right <= left:
        return 0.0
    return (last_x1 - left) / (right - left)


def classify_fill(ratio):
    """'ok' for 92% up to just under 100%, 'low' below, 'over' at or past the margin."""
    pct = round(ratio * 100, 1)
    if pct < FILL_MIN * 100:
        return "low"
    if pct >= 100.0:
        return "over"
    return "ok"


def detect_right_edge(pages):
    """Right margin of the text block, in points, and where the number came from."""
    widest_rule = 0.0
    for p in pages:
        for x0, x1, _ in p["rules"]:
            if x1 - x0 > 0.5 * p["width"]:
                widest_rule = max(widest_rule, x1)
    if widest_rule:
        return widest_rule, "section rule"
    widest_text = max((l.x1 for p in pages for l in p["lines"]), default=0.0)
    return widest_text, "widest text line"


def first_word(text):
    """The action verb: first word of a bullet, lower-cased, punctuation trimmed."""
    parts = text.split()
    return re.sub(r"^\W+|\W+$", "", parts[0]).lower() if parts else ""


def repeated_verbs(bullet_texts):
    """{verb: times used} for every first word used more than once."""
    counts = Counter(v for v in (first_word(t) for t in bullet_texts) if v)
    return {v: n for v, n in sorted(counts.items()) if n > 1}


def find_bad_chars(text):
    """Count characters that break ATS parsing.

    Returns {"replacement": n, "unmapped": n, "combining": n}.
    """
    return {
        "replacement": text.count("\ufffd"),
        "unmapped": len(re.findall(r"\(cid:\d+\)", text)),
        "combining": sum(1 for c in text if "\u0300" <= c <= "\u036f"),
    }


def strip_tex_comments(tex):
    return re.sub(r"(?<!\\)%.*", "", tex)


def _brace_group(s, i):
    """Text of the balanced {...} group starting at or after s[i] (skipping spaces)."""
    while i < len(s) and s[i].isspace():
        i += 1
    if i >= len(s) or s[i] != "{":
        return ""
    depth, start = 0, i + 1
    for j in range(i, len(s)):
        if s[j] == "{" and (j == 0 or s[j - 1] != "\\"):
            depth += 1
        elif s[j] == "}" and s[j - 1] != "\\":
            depth -= 1
            if depth == 0:
                return s[start:j]
    return s[start:]


def _plain(tex):
    """Readable text of a heading argument: drop commands, braces and math bars."""
    tex = re.sub(r"\\(&|\$|%|#|_)", r"\1", tex)
    tex = re.sub(r"\\[a-zA-Z]+\*?", " ", tex)
    tex = re.sub(r"[{}$|~]", " ", tex)
    return " ".join(tex.replace("--", "-").split())


TOKEN = re.compile(r"\\section\*?\s*\{|\\resume(?:Sub|Project)[Hh]eading(?![A-Za-z])|\\resumeItem\s*\{")


def count_bullets(tex):
    """[(section, entry heading, bullet count), ...] in document order."""
    body = strip_tex_comments(tex)
    start = body.find("\\begin{document}")
    body = body[start:] if start >= 0 else body
    rows, section = [], None
    for m in TOKEN.finditer(body):
        tok = m.group(0)
        if tok.startswith("\\section"):
            section = _plain(_brace_group(body, m.end() - 1))
        elif tok.startswith("\\resumeItem"):
            if rows and rows[-1][0] == section:
                rows[-1][2] += 1
        else:
            rows.append([section, _plain(_brace_group(body, m.end())), 0])
    return [tuple(r) for r in rows]


def load_count_rules(path=None):
    """Merge a JSON override file over the defaults. Returns {"sections", "entries"}."""
    rules = {"sections": dict(DEFAULT_COUNTS), "entries": {}}
    if path:
        with open(path, encoding="utf-8") as fh:
            override = json.load(fh)
        rules["sections"].update(override.get("sections", {}))
        rules["entries"].update(override.get("entries", {}))
    return rules


def expected_count(section, entry, rules):
    """Bullets this entry should have, or None if its section has no rule."""
    for prefix, want in rules["entries"].items():
        if entry.lower().startswith(prefix.lower()):
            return want
    for prefix, want in rules["sections"].items():
        if section and section.lower().startswith(prefix.lower()):
            return want
    return None


def evaluate_counts(rows, rules):
    """[(section, entry, have, want, ok)] for entries whose section has a rule."""
    out = []
    for section, entry, have in rows:
        want = expected_count(section, entry, rules)
        if want is not None:
            out.append((section, entry, have, want, have == want))
    return out


def classify_gap(inches, letter=False):
    lo, hi = LETTER_GAP if letter else RESUME_GAP
    if not letter and inches > RESUME_GAP_FAIL:
        return FAIL
    return PASS if lo <= round(inches, 2) <= hi else WARN


# --------------------------------------------------------------------------
# Checks that turn measurements into Results
# --------------------------------------------------------------------------
def check_pages(pages, want, master):
    n = len(pages)
    label = f"{n} page{'s' if n != 1 else ''}"
    if master:
        return Result("pages", PASS, f"{label} (master resume: any length)", data={"pages": n})
    if n == want:
        return Result("pages", PASS, label, data={"pages": n})
    return Result("pages", FAIL, f"{label}, must be exactly {want}", data={"pages": n})


def check_fill(bullets, right, source, verbose=False):
    rows, low, over, multi = [], 0, 0, 0
    for b in bullets:
        ratio = fill_ratio(b.last_x1, b.left, right)
        kind = classify_fill(ratio)
        low += kind == "low"
        over += kind == "over"
        multi += len(b.lines) > 1
        rows.append({"page": b.page, "lines": len(b.lines), "fill": round(ratio * 100, 1),
                     "state": kind, "text": b.text})
    details = []
    for r in rows:
        if r["state"] != "ok" or verbose:
            tag = {"low": "LOW ", "over": "OVER", "ok": "ok  "}[r["state"]]
            details.append(f"{tag} p{r['page']} {r['lines']}L {r['fill']:5.1f}%  {r['text'][:80]}")
    where = f"right edge {right:.1f}pt from {source}"
    if not bullets:
        return Result("bullet fill", WARN, "no bullets found", data={"bullets": rows, "right": right})
    if low or over:
        parts = ([f"{low} under {FILL_MIN:.0%}"] if low else []) + \
                ([f"{over} at or past 100%"] if over else [])
        return Result("bullet fill", FAIL, f"{len(bullets)} bullets, {', '.join(parts)} ({where})",
                      details, {"bullets": rows, "right": right, "right_source": source})
    fills = [r["fill"] for r in rows]
    return Result("bullet fill", PASS,
                  f"{len(bullets)} bullets, last lines {min(fills):.1f}%-{max(fills):.1f}% ({where})",
                  details, {"bullets": rows, "right": right, "right_source": source})


def check_one_line(bullets):
    multi = [b for b in bullets if len(b.lines) > 1]
    if not multi:
        return Result("one line each", PASS, "every bullet is a single line")
    return Result("one line each", WARN, f"{len(multi)} bullet(s) wrap past one line",
                  [f"p{b.page} {len(b.lines)}L  {b.text[:80]}" for b in multi])


def check_bottom_gap(pages, letter):
    last = pages[-1]
    if not last["lines"]:
        return Result("bottom gap", FAIL, "no text on the page")
    inches = min(l.y0 for l in last["lines"]) / 72.0
    lo, hi = LETTER_GAP if letter else RESUME_GAP
    status = classify_gap(inches, letter)
    target = f"target {lo:.2f}-{hi:.2f}in"
    if status == FAIL:
        note = f"{inches:.2f}in blank at the bottom, over {RESUME_GAP_FAIL:.1f}in ({target}): add content"
    elif status == WARN:
        note = f"{inches:.2f}in blank at the bottom ({target})"
    else:
        note = f"{inches:.2f}in blank at the bottom ({target})"
    return Result("bottom gap", status, note, data={"inches": round(inches, 3)})


def check_bad_chars(pages):
    text = "\n".join(l.text for p in pages for l in p["lines"])
    bad = find_bad_chars(text)
    details = []
    if bad["replacement"] or bad["unmapped"]:
        for p in pages:
            for l in p["lines"]:
                if "\ufffd" in l.text or "(cid:" in l.text:
                    details.append(f"p{l.page}  {l.text[:80]}")
        return Result("bad characters", FAIL,
                      f"{bad['replacement']} U+FFFD and {bad['unmapped']} unmapped glyph(s): "
                      "the PDF text layer is broken", details, bad)
    if bad["combining"]:
        for p in pages:
            for l in p["lines"]:
                if any("\u0300" <= c <= "\u036f" for c in l.text):
                    details.append(f"p{l.page}  {l.text[:80]}")
        return Result("bad characters", WARN,
                      f"{bad['combining']} combining accent(s); ATS parsers mangle them, "
                      'write plain ASCII ("resume", "cafe")', details, bad)
    bitmap = sum(p.get("bitmap_glyphs", 0) for p in pages)
    if bitmap:
        bad["bitmap"] = bitmap
        return Result("bad characters", WARN,
                      f"{bitmap} glyph(s) come from a bitmap (Type 3) font: they print blurry and may "
                      "not copy as text. Usually a symbol such as \\$ or \\textbullet on a TeX install "
                      "missing a font; compile on Overleaf or switch the symbol's font", data=bad)
    return Result("bad characters", PASS, "none", data=bad)


def check_verbs(bullets, master):
    repeats = repeated_verbs(b.text for b in bullets)
    if not repeats:
        return Result("repeated verbs", PASS, f"{len(bullets)} bullets, every first word is different",
                      data={"repeats": {}})
    details = [f"{verb} x{n}" for verb, n in repeats.items()]
    return Result("repeated verbs", WARN if master else FAIL,
                  f"{len(repeats)} first word(s) used more than once", details, {"repeats": repeats})


def check_counts(tex_path, counts_path):
    with open(tex_path, encoding="utf-8") as fh:
        rows = count_bullets(fh.read())
    rules = load_count_rules(counts_path)
    table = evaluate_counts(rows, rules)
    details = [f"{'ok ' if ok else 'BAD'} {have} (want {want})  [{section}] {entry[:60]}"
               for section, entry, have, want, ok in table]
    bad = sum(1 for row in table if not row[4])
    data = {"entries": [{"section": s, "entry": e, "have": h, "want": w, "ok": ok}
                        for s, e, h, w, ok in table],
            "rules_file": counts_path}
    source = f"rules: {counts_path}" if counts_path else "default rules"
    if not table:
        return Result("bullet counts", WARN, "no entries found under Experience / Projects / Leadership",
                      details, data)
    if bad:
        return Result("bullet counts", FAIL, f"{bad} of {len(table)} entries have the wrong number "
                      f"of bullets ({source})", details, data)
    return Result("bullet counts", PASS, f"{len(table)} entries match ({source})", details, data)


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------
def run(args):
    pages = read_pdf(args.pdf)
    lines = [l for p in pages for l in p["lines"]]
    bullets = find_bullets(lines)
    results = [check_pages(pages, args.pages, args.master)]

    if args.letter:
        results.append(Result("bullet fill", SKIP, "letters wrap their bullets on purpose"))
    else:
        if args.right:
            right, source = args.right, "--right"
        else:
            right, source = detect_right_edge(pages)
        results.append(check_fill(bullets, right, source, args.verbose))
        results.append(check_one_line(bullets))

    if args.master:
        results.append(Result("bottom gap", SKIP, "not checked for a master resume"))
    else:
        results.append(check_bottom_gap(pages, args.letter))

    results.append(check_bad_chars(pages))

    if args.letter:
        results.append(Result("repeated verbs", SKIP, "not checked for letters"))
    else:
        results.append(check_verbs(bullets, args.master))

    if args.letter or args.master:
        results.append(Result("bullet counts", SKIP,
                              "not checked for a " + ("letter" if args.letter else "master resume")))
    elif not args.tex:
        results.append(Result("bullet counts", SKIP, "pass --tex <file.tex> to check bullets per entry"))
    else:
        counts_path = args.counts or (DEFAULT_COUNTS_FILE if os.path.exists(DEFAULT_COUNTS_FILE) else None)
        results.append(check_counts(args.tex, counts_path))
    return results


def build_parser():
    p = argparse.ArgumentParser(description="Check a compiled resume or cover letter PDF.")
    p.add_argument("pdf", help="the compiled PDF")
    p.add_argument("--tex", help="the .tex source (enables the bullet-count check)")
    p.add_argument("--letter", action="store_true", help="the PDF is a cover letter")
    p.add_argument("--master", action="store_true",
                   help="multi-page master resume: skip the page, bottom-gap and bullet-count checks")
    p.add_argument("--pages", type=int, default=1, help="required page count (default 1)")
    p.add_argument("--right", type=float, help="right margin of the text block in points (default: detected)")
    p.add_argument("--counts", help="JSON file overriding the bullets-per-entry rules")
    p.add_argument("--verbose", action="store_true", help="list every bullet with its fill, not only the bad ones")
    p.add_argument("--json", action="store_true", help="print one JSON object instead of text")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    for path in (args.pdf, args.tex, args.counts):
        if path and not os.path.exists(path):
            print(f"check_resume: file not found: {path}", file=sys.stderr)
            return 2

    results = run(args)
    failed = any(r.status == FAIL for r in results)
    kind = "letter" if args.letter else "master resume" if args.master else "resume"

    if args.json:
        print(json.dumps({"file": args.pdf, "kind": kind, "ok": not failed,
                          "checks": [r.as_dict() for r in results]}, indent=2, ensure_ascii=False))
    else:
        print(f"check_resume: {args.pdf} ({kind})")
        for r in results:
            print(f"{r.status}  {r.name:<15} {r.summary}")
            for d in r.details:
                print(f"        {d}")
        warned = sum(r.status == WARN for r in results)
        if failed:
            print("RESULT: FAIL")
        else:
            print("RESULT: PASS" + (f" with {warned} warning(s)" if warned else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
