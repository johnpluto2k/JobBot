"""One-page layout fitting for a TailoredResume (business / VMH track).

The renderers used to be size-blind: `render_docx` wrote fixed 10.5pt type at
Word's default 1.15 line spacing (so a full profile spilled onto a second,
mostly blank page) while `render_pdf` only ever shrank (so a short profile left
a band of dead space at the bottom). Both symptoms are the same bug — nobody
measured the content against the page.

This module measures. It describes the resume as a list of paragraph blocks,
estimates their height with a Calibri wrap model calibrated against Word's own
layout, and exposes:

* `normalize_bullets(resume, counts)` — force one bullet count per section, so
  every role in Experience shows the same number of lines. Ragged counts read
  as "ran out of things to say about the older jobs".
* `trim_to_fit(resume)` — cut whole uniform rows (a bullet off *every* entry in
  a section at once, weakest section first) until one page is reachable inside
  the contract's 10–11pt type band. Returns a copy plus what it dropped.
* `fit_sizes(resume)` — pick the type/spacing/margin scale that fills the page.
* `assign_tracking(...)` — per-bullet condensed letter-spacing, so a bullet that
  spills three words onto a second line is pulled back instead of leaving a
  stub line mostly white.

Section order, the 10–11pt type band and the absence of a Summary section all
come from `docs/resume_track_contract.md` — that document is the authority, not
this file.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from .resume_models import TailoredResume
from .writing_style import split_metrics

FONT = "Calibri"
BODY_PT = 10.5
NAME_PT = 18.0
HEAD_PT = 11.5

# Contract: business-track body type stays inside 10–11pt. The fitter is free
# to move within that band and nowhere else — spacing and trimming carry the
# rest of the load.
BODY_MIN_PT, BODY_MAX_PT = 10.0, 11.0

# US Letter, in points.
PAGE_W, PAGE_H = 612.0, 792.0
VMARGIN = 36.0                          # 0.5" — the ATS floor, never tighter
HMARGIN_MAX, HMARGIN_MIN = 54.0, 54.0   # fixed 0.75" — see note below
USABLE_H = PAGE_H - 2 * VMARGIN         # 720pt

# The side margins deliberately do NOT compress. Body text is justified (a
# deliberate choice), and justification opens visible inter-word rivers once
# the measure passes ~7in at 10pt. Narrowing the margins to buy vertical space
# would widen the measure and make every long bullet look stretched, so
# compression is spent on vertical gaps and trimming only.

# Aim slightly under a full page: the wrap model is an estimate, and
# overshooting costs a whole extra page while undershooting costs a few points
# of white space.
FILL_TARGET = 0.965

# Trimming is destructive, so it uses a looser budget than the scale search:
# only drop content that genuinely cannot be laid out.
TRIM_TARGET = 1.0

# Calibri metrics as fractions of the point size: mean advance width over
# mixed-case English prose, and the single-spaced line height. Calibrated
# against Word's own layout of a rendered resume.
_CHAR_EM = 0.435
_CHAR_EM_BOLD = 0.458
_LINE_EM = 1.22

# The per-block model runs slightly pessimistic against Word's real layout
# (measured: 694.8pt predicted vs 661.1pt actual on the Deloitte fixture, a
# 4.9% over-estimate). Uncorrected, that pessimism is paid for in content: the
# trimmer dropped a whole Projects section to reclaim space the page already
# had. Re-measure with tools/measure_fit.py after changing any metric above.
_CALIBRATION = 0.952

BULLET_INDENT = 12.0

# A wrapped bullet whose last line fills less than this much of the column is a
# stub — the "bleed" that leaves most of a line white. We spend up to MAX_TRACK
# points of condensed letter-spacing to pull it back onto the line above.
# -0.3pt at 10pt type is a 3% squeeze: invisible on its own, and Word renders
# it natively via the run-level w:spacing property.
STUB_FILL = 0.55
_TRACK_STEPS = (-0.1, -0.15, -0.2, -0.25, -0.3, -0.35, -0.4, -0.45, -0.5)
# Bullets need only a nudge. The skills/coursework lines are one long list that
# can strand a single word ("... Payment Integrations, Data" / "Analysis"), and
# pulling that back is worth a slightly deeper squeeze — 0.5pt at 10pt is 5%,
# still under the threshold where condensed type reads as condensed.
MAX_TRACK = {"bullet": -0.3, "body": -0.5}

# Soft skills listed under a header that reads TECHNICAL SKILLS is a category
# error, and "Business Development, Client Outreach" is sales vocabulary on an
# assurance resume — a Big 4 reviewer reads it as aiming at a different job.
# The business template shows hard skills only; the tech track (render_rendercv)
# still renders whatever the profile holds.
HIDDEN_SKILL_GROUPS = {"professional", "soft"}
# A group with one member restates its own label ("Analytical: Data Analysis")
# and burns a whole line saying nothing.
MIN_GROUP_MEMBERS = 2

# Bullets shown per entry, per section, before any trimming. Uniform by
# construction — see `normalize_bullets`.
DEFAULT_BULLETS = {"experience": 2, "leadership": 2, "projects": 3}
MIN_BULLETS = {"experience": 1, "leadership": 1, "projects": 2}
# Below this the Projects section is not rendered at all (contract rule).
MIN_PROJECTS_FOR_SECTION = 2


# --------------------------------------------------------------------- blocks
@dataclass
class Block:
    """One paragraph, described independently of the size it renders at."""

    kind: str                    # name|contact|head|entry|sub|body|bullet
    runs: list = field(default_factory=list)   # [(text, bold, italic)]
    tail: str = ""               # right-tabbed text (entry / sub blocks)
    track: float = 0.0           # condensed letter-spacing, in points (<= 0)

    @property
    def text(self) -> str:
        return "".join(r[0] for r in self.runs)

    @property
    def bold(self) -> bool:
        return bool(self.runs) and self.runs[0][1]

    @property
    def char_em(self) -> float:
        """Mean advance width for this block, weighted across its runs.

        Taking the weight from run[0] alone measured "Technical: Python, SQL,
        ..." as if all of it were bold — a label-prefixed list line is almost
        entirely regular weight, so the width came out too wide and the wrap
        prediction with it."""
        bold_n = sum(len(t) for t, b, _ in self.runs if b)
        total = sum(len(t) for t, _, _ in self.runs)
        if not total:
            return _CHAR_EM
        return (_CHAR_EM_BOLD * bold_n + _CHAR_EM * (total - bold_n)) / total


# Profile text mixes typographic and straight quotes, which renders as
# "Kim’s" sitting next to "company's" on the same page. Normalize to straight
# quotes at render: consistent on the page and the safest glyph through an ATS
# text extractor.
_GLYPHS = {"‘": "'", "’": "'", "“": '"', "”": '"',
           "′": "'", " ": " "}


def clean_text(text: str) -> str:
    for bad, good in _GLYPHS.items():
        text = text.replace(bad, good)
    return text


def _metric_runs(text: str) -> list:
    """Playbook: bold all metrics — recruiters scan numbers first."""
    return [(clean_text(chunk), is_metric, False)
            for chunk, is_metric in split_metrics(text)]


def display_skill_groups(resume: TailoredResume) -> list:
    """Skill groups as the business template should show them: hard skills
    only, and no group so small it just repeats its own label."""
    from .resume_models import SkillGroup

    keep = [SkillGroup(label=g.label, skills=list(g.skills))
            for g in (resume.skill_groups or [])
            if g.skills and g.label.lower() not in HIDDEN_SKILL_GROUPS]
    big = [g for g in keep if len(g.skills) >= MIN_GROUP_MEMBERS]
    small = [g for g in keep if len(g.skills) < MIN_GROUP_MEMBERS]
    if not big:
        return keep
    for g in small:
        big[0].skills.extend(s for s in g.skills if s not in big[0].skills)
    return big


def blocks_for(resume: TailoredResume) -> list[Block]:
    """The single description of the resume's paragraph structure. Both the
    height estimate and the DOCX writer walk this, so they cannot drift.

    Section order is the business-track contract's: Experience → Leadership →
    Education → Projects → Technical Skills. There is deliberately no Summary
    block — the contract has no Summary section for this track.
    """
    b: list[Block] = []

    b.append(Block("name", [((resume.name or "").upper(), True, False)]))
    b.append(Block("contact", [(resume.contact_line, False, False)]))

    def head(text: str) -> None:
        b.append(Block("head", [(text.upper(), True, False)]))

    def entry(left: str, right: str | None,
              sub: str | None = None, sub_right: str | None = None) -> None:
        b.append(Block("entry", [(left, True, False)], tail=right or ""))
        if sub or sub_right:
            b.append(Block("sub", [(sub or "", False, True)], tail=sub_right or ""))

    def bullets(items) -> None:
        for text in items:
            b.append(Block("bullet", _metric_runs(text)))

    def role_section(title: str, roles) -> None:
        if not roles:
            return
        head(title)
        for role in roles:
            # Role left, location right — a parser gets an unambiguous location
            # string and the eye gets a clean second column, instead of the two
            # run together behind a pipe on the left.
            entry(role.organization or role.role or "", role.dates,
                  sub=role.role if role.organization else None,
                  sub_right=role.location)
            bullets(role.bullets)

    role_section("Experience", resume.experience)
    role_section("Leadership & Activities", resume.leadership)

    if resume.education:
        head("Education")
        for e in resume.education:
            entry(e.school or "", e.graduation_date)
            line = e.degree or ""
            if e.gpa:
                line += f"   |   GPA: {e.gpa}"
            b.append(Block("body", [(line, False, False)]))
            if e.secondary:
                b.append(Block("body", [(e.secondary, False, False)]))
            if e.coursework:
                b.append(Block("body", [("Relevant Coursework: ", True, False),
                                        (", ".join(e.coursework), False, False)]))
        for cert in _licensure(resume.certifications):
            b.append(Block("body", [(cert, True, False)]))

    # Contract, VMH Template Requirements: "No projects section header if <2
    # items." A lone project under a full header + rule is a section that costs
    # three lines to say one thing.
    if len(resume.projects) >= MIN_PROJECTS_FOR_SECTION:
        head("Projects")
        for p in resume.projects:
            entry(p.organization or p.role or "", None)
            bullets(p.bullets)

    groups = display_skill_groups(resume)
    if groups or resume.skills:
        head("Technical Skills")
        if groups:
            for g in groups:
                b.append(Block("body", [(f"{g.label}: ", True, False),
                                        (", ".join(g.skills), False, False)]))
        else:
            b.append(Block("body", [(", ".join(resume.skills), False, False)]))
    other = [c for c in resume.certifications if c not in _licensure(resume.certifications)]
    if other:
        b.append(Block("body", [("Certifications: ", True, False),
                                (", ".join(other), False, False)]))

    return b


# Licensure that an accounting recruiter reads as a gating credential. These
# are promoted out of the Certifications tail and into Education, where a Big 4
# reviewer looks for them.
_LICENSURE_RE = "cpa|cfa|cia|cisa|cma|enrolled agent"


def _licensure(certifications) -> list[str]:
    import re
    return [c for c in (certifications or []) if re.search(_LICENSURE_RE, c, re.I)]


# -------------------------------------------------------------------- metrics
def sizes_at(t: float) -> dict:
    """Resolve the single fit knob t in [-1, 1] into concrete layout metrics.

    Type moves only inside the contract's 10–11pt band; spacing and margins do
    the compressing, and trimming picks up whatever is left. Everything is
    monotonic in t, so callers can binary-search.
    """
    t = max(-1.0, min(1.0, t))
    body_pt = BODY_MIN_PT + (t + 1) / 2 * (BODY_MAX_PT - BODY_MIN_PT)
    f = body_pt / BODY_PT
    if t >= 0:
        g = 1.0 + t * 1.2
        hmargin = HMARGIN_MAX
    else:
        g = 1.0 + t * 0.55
        hmargin = HMARGIN_MAX + t * (HMARGIN_MAX - HMARGIN_MIN)

    return {
        # kind: (font_pt, space_before, space_after, left_indent)
        "name": (NAME_PT * f, 0.0, 2.0 * g, 0.0),
        "contact": (BODY_PT * f, 0.0, 6.0 * g, 0.0),
        "head": (HEAD_PT * f, 8.0 * g, 3.0 * g, 0.0),
        "entry": (BODY_PT * f, 5.0 * g, 0.0, 0.0),
        "sub": (BODY_PT * f, 0.0, 1.0 * g, 0.0),
        "body": (BODY_PT * f, 0.0, 2.0 * g, 0.0),
        "bullet": (BODY_PT * f, 0.0, 1.5 * g, BULLET_INDENT),
        # Distance from a section heading's text to its underline, in whole
        # points (Word's w:space). Measured in Word, the rule lands almost
        # exactly w:space below the type's descender line, so the old value of
        # 1 left ~1pt of air and read as cutting into the letters.
        "_border_space": max(4, min(7, round(4.5 * f))),
        "_hmargin": hmargin,
        "_usable_w": PAGE_W - 2 * hmargin,
        "_font_scale": f,
        "_body_pt": body_pt,
        "_gap_scale": g,
        "_t": t,
    }


def _wrap_info(text: str, pt: float, em: float, width: float,
               track: float = 0.0) -> tuple[int, float]:
    """Greedy word wrap. Returns (line count, how full the last line is)."""
    words = text.split()
    if not words:
        return 1, 1.0
    advance = pt * em + track
    cpl = max(8, int(width / advance))
    lines, cur = 1, 0
    for w in words:
        need = len(w) if cur == 0 else cur + 1 + len(w)
        if need <= cpl:
            cur = need
        else:
            lines += 1
            cur = len(w)
    return lines, cur / cpl


def _block_width(blk: Block, sizes: dict) -> float:
    return sizes["_usable_w"] - sizes[blk.kind][3]


def assign_tracking(blocks: list[Block], sizes: dict) -> None:
    """Kill stub lines: where a bullet spills a few words onto a second line,
    condense its letter-spacing just enough to pull them back up.

    Only applied where it actually removes a line — a squeeze that doesn't win
    a line back is pure inconsistency for no gain."""
    for blk in blocks:
        blk.track = 0.0
        # Body paragraphs strand words too — the Technical Skills line left
        # "Analysis" alone on a second line — so they get the same treatment.
        if blk.kind not in ("bullet", "body"):
            continue
        pt = sizes[blk.kind][0]
        width = _block_width(blk, sizes)
        lines, fill = _wrap_info(blk.text, pt, blk.char_em, width)
        if lines < 2 or fill >= STUB_FILL:
            continue
        budget = MAX_TRACK[blk.kind]
        for track in _TRACK_STEPS:
            if track < budget:
                break
            tighter, _ = _wrap_info(blk.text, pt, blk.char_em, width, track)
            if tighter < lines:
                blk.track = track
                break


def estimate_height(blocks: list[Block], sizes: dict) -> float:
    total = 0.0
    for blk in blocks:
        pt, before, after, indent = sizes[blk.kind]
        text = blk.text
        if blk.tail:
            text = f"{text}    {blk.tail}"
        if blk.kind in ("name", "contact"):
            lines = 1                        # centred single lines by design
        else:
            lines, _ = _wrap_info(text, pt, blk.char_em,
                                  _block_width(blk, sizes), blk.track)
        total += lines * pt * _LINE_EM + before + after
        if blk.kind == "head":
            total += sizes["_border_space"] + 1.0   # rule offset + rule weight
    return total * _CALIBRATION


def measure(resume: TailoredResume, t: float) -> float:
    """Estimated height of `resume` laid out at knob position `t`."""
    blocks = blocks_for(resume)
    sizes = sizes_at(t)
    assign_tracking(blocks, sizes)
    return estimate_height(blocks, sizes)


def fits_at(resume: TailoredResume, t: float, target: float = FILL_TARGET) -> bool:
    return measure(resume, t) <= USABLE_H * target


def fit_sizes(resume: TailoredResume) -> dict:
    """Largest scale whose estimated height still fits a single page."""
    budget = USABLE_H * FILL_TARGET
    lo, hi = -1.0, 1.0
    if measure(resume, lo) > budget:
        return sizes_at(lo)                  # too long even fully compressed
    if measure(resume, hi) <= budget:
        return sizes_at(hi)                  # short enough to open fully up
    for _ in range(24):
        mid = (lo + hi) / 2
        if measure(resume, mid) <= budget:
            lo = mid
        else:
            hi = mid
    return sizes_at(lo)


def layout(resume: TailoredResume) -> tuple[list[Block], dict]:
    """Blocks with tracking assigned, plus the sizes they were fitted at."""
    sizes = fit_sizes(resume)
    blocks = blocks_for(resume)
    assign_tracking(blocks, sizes)
    return blocks, sizes


# ------------------------------------------------------------------- bullets
def _sections(r: TailoredResume) -> dict:
    return {"experience": r.experience, "leadership": r.leadership,
            "projects": r.projects}


def normalize_bullets(resume: TailoredResume, counts: dict | None = None) -> dict:
    """Force one bullet count per section, in place.

    Every entry in a section shows the same number of bullets: ragged counts
    read as having run out of things to say about the older roles. The count is
    capped by the thinnest entry, so nothing is padded — if one role only has
    two real bullets, the whole section shows two.

    Returns the counts actually applied.
    """
    counts = dict(counts or DEFAULT_BULLETS)
    applied = {}
    for kind, entries in _sections(resume).items():
        have = [e for e in entries if e.bullets]
        if not have:
            applied[kind] = 0
            continue
        n = max(1, min(counts.get(kind, DEFAULT_BULLETS[kind]),
                       min(len(e.bullets) for e in have)))
        for e in have:
            del e.bullets[n:]
        applied[kind] = n
    return applied


def _available(resume: TailoredResume, kind: str) -> int:
    entries = [e for e in _sections(resume)[kind] if e.bullets]
    return min((len(e.bullets) for e in entries), default=0)


# ---------------------------------------------------------------------- trim
def _next_trim(r: TailoredResume, counts: dict
               ) -> tuple[str, Callable[[], None]] | None:
    """The single least-valuable cut left, or None at the floor of what a
    resume should still say. Bullet cuts are always *uniform rows* — one comes
    off every entry in a section at once — so the counts stay even."""

    # 1. Coursework is keyword fodder — shorten it before touching a bullet.
    for e in r.education:
        if len(e.coursework) > 4:
            n = max(4, len(e.coursework) - 2)
            return (f"coursework trimmed to {n} courses",
                    lambda: e.coursework.__setitem__(slice(None), e.coursework[:n]))

    def row(kind: str, label: str):
        current = counts.get(kind, 0)
        target = current - 1

        def apply(kind=kind, target=target) -> None:
            counts[kind] = target
            normalize_bullets(r, counts)

        return (f"{label}: {current} -> {target} bullets per entry", apply)

    def can_cut(kind: str, floor: int) -> bool:
        return (counts.get(kind, 0) > floor
                and any(e.bullets for e in _sections(r)[kind]))

    # 2-3. Supporting sections give up bullets first.
    if len(r.projects) > 1 and can_cut("projects", 2):
        return row("projects", "Projects")
    # The section goes whole: one project renders nothing (see
    # MIN_PROJECTS_FOR_SECTION), so dropping to one wastes a trim step and
    # leaves dead weight in the model.
    if r.projects:
        return ("dropped the Projects section", lambda: r.projects.clear())
    if can_cut("leadership", 1):
        return row("leadership", "Leadership")

    # 4-6. Then whole low-value entries. Shedding the weakest project or the
    # oldest job beats thinning every remaining role down to a single line —
    # the contract wants 3+ roles carrying *quantified impact*, and one bullet
    # per role cannot carry it.
    if len(r.experience) > 3:
        name = r.experience[-1].organization or r.experience[-1].role
        return (f"dropped role '{name}'", lambda: r.experience.pop())
    if len(r.leadership) > 1:
        name = r.leadership[-1].organization or r.leadership[-1].role
        return (f"dropped leadership entry '{name}'", lambda: r.leadership.pop())

    # 7. Last resort: one bullet per role.
    if can_cut("experience", 1):
        return row("experience", "Experience")

    return None


def trim_to_fit(resume: TailoredResume, max_steps: int = 40
                ) -> tuple[TailoredResume, list[str]]:
    """Return a copy of `resume` that fits one page inside the contract's type
    band, plus a list describing everything that had to come off.

    If the ladder runs out before it fits, the resume is returned as-is (with
    whatever was already dropped listed): losing more content is worse than a
    resume that runs slightly long, and the caller can surface the fact."""
    r = resume.model_copy(deep=True)
    counts = {}
    for kind, default in DEFAULT_BULLETS.items():
        avail = _available(r, kind)
        counts[kind] = min(default, avail) if avail else default
    normalize_bullets(r, counts)

    dropped: list[str] = []
    for _ in range(max_steps):
        if fits_at(r, -1.0, TRIM_TARGET):
            break
        step = _next_trim(r, counts)
        if step is None:
            break
        desc, apply = step
        apply()
        dropped.append(desc)
    return r, dropped
