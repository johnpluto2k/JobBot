"""Bullet workbench: tailored bullets for a JD, for a résumé you format yourself.

The Phase-4 generator (`job_bot.generate`) owns the whole document — it picks a
template, trims to one page, and typesets a PDF. That is the right shape when
you want a finished file, and the wrong shape when you already have a résumé
you like and only want the *words* changed for a specific posting.

This module is that second shape. Given a JD and the résumé text you actually
edit, it returns per-bullet:

  * the original, verbatim
  * a tailored rewrite in the JD's language (never new facts)
  * which JD keywords the bullet genuinely supports
  * a verdict — lead / keep / cut — so you know what to drop for space
  * whether it fills the lines it occupies (see `line_fit`), because a bullet
    that puts three words on a second line burns a whole line of page

plus your skills line reordered so JD-matching skills come first. Nothing is
rendered; you paste the results into your own document.

Usage:
    python -m job_bot.bullets --jd jd.txt --resume resume.txt
    python -m job_bot.bullets --jd jd.txt          # falls back to master profile
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import config, line_fit
from .extract import (_make_bullet, _normalize_md, _parse_entries, _split_list,
                      _split_sections, _strip_md)
from .jd_models import JobPosting
from .similarity import contains_phrase
from .tailor import (MAX_BULLETS, _bullet_relevance, _jd_aliases, _jd_matches,
                     profile_facts_json, print_llm_usage)
from .writing_style import RESUME_BULLET_RULES, STYLE_RULES, polish_bullet

# Verdicts. `cut` never means "this bullet is bad" — it means this JD does not
# reward it, and the space it occupies is better spent on the bullets above it.
LEAD, KEEP, CUT = "lead", "keep", "cut"


@dataclass
class TailoredBullet:
    section: str            # experience | leadership | projects
    entry: str              # the heading this bullet sits under
    original: str
    tailored: str
    relevance: float        # 0..1, same scale the generator ranks by
    verdict: str            # LEAD | KEEP | CUT
    keywords: list[str] = field(default_factory=list)
    fit: line_fit.Fit | None = None      # how well `tailored` fills its lines

    @property
    def changed(self) -> bool:
        """True only when the wording actually moved.

        `polish_bullet` deterministically restyles every bullet ("and" -> "&",
        no trailing period), so a raw comparison marks the whole résumé as
        rewritten even with no API key. Compare polished-to-polished: the flag
        should mean "Claude reworded this", not "the house style differs"."""
        return self.tailored.strip() != polish_bullet(self.original).strip()

    def as_dict(self) -> dict:
        return {
            "section": self.section, "entry": self.entry,
            "original": self.original, "tailored": self.tailored,
            "relevance": round(self.relevance, 3), "verdict": self.verdict,
            "keywords": self.keywords, "changed": self.changed,
            "fit": self.fit.as_dict() if self.fit else None,
        }


@dataclass
class BulletWorkbench:
    source: str                     # "resume" (pasted) or "profile" (fallback)
    bullets: list[TailoredBullet]
    skills: list[str]               # reordered: JD-matching first
    rewritten: bool                 # False when no API key — originals kept

    def as_dict(self) -> dict:
        return {
            "source": self.source,
            "bullets": [b.as_dict() for b in self.bullets],
            "skills": self.skills,
            "rewritten": self.rewritten,
        }


# --------------------------------------------------------------------------- #
# Reading the résumé you actually edit
# --------------------------------------------------------------------------- #
def parse_resume_text(text: str) -> dict:
    """Pull entries + bullets out of pasted résumé text.

    Reuses the Phase-1 heuristic parser (`extract._split_sections` /
    `_parse_entries`) rather than a second one: whatever quirks of your layout
    that parser already handles — pipe-separated headers, unmarked bullets,
    markdown from a .docx — are handled here for free.

    Returns {"experience": [(heading, [bullet, ...]), ...], ..., "skills": [...]}.
    """
    sections = _split_sections(_normalize_md(text))
    out: dict[str, list] = {}
    for kind in ("experience", "leadership", "projects"):
        entries = []
        for org_line, sub_line, raw_bullets in _parse_entries(sections.get(kind, [])):
            if not raw_bullets:
                continue
            heading = " — ".join(
                p for p in (_strip_md(org_line or ""), _strip_md(sub_line or "")) if p
            ) or "(untitled)"
            entries.append((heading, raw_bullets))
        out[kind] = entries
    skills: list[str] = []
    for raw in sections.get("skills", []):
        line = _strip_md(raw)
        # "Technical: Python, SQL, Excel" -> drop the category label
        body = line.split(":", 1)[1] if ":" in line[:30] else line
        skills.extend(_split_list(body))
    out["skills"] = [s for s in dict.fromkeys(skills) if s]
    return out


def _entries_from_profile(profile: dict) -> dict:
    """Same shape as `parse_resume_text`, read off master_profile.json — the
    fallback when nothing is pasted."""
    out: dict[str, list] = {}
    for kind, key in (("experience", "experience"), ("leadership", "leadership"),
                      ("projects", "projects")):
        entries = []
        for e in profile.get(key, []):
            bits = [e.get("organization") or e.get("name") or "", e.get("role") or ""]
            heading = " — ".join(p for p in bits if p) or "(untitled)"
            texts = [b.get("text", "") for b in e.get("bullets", []) if b.get("text")]
            if texts:
                entries.append((heading, texts))
        out[kind] = entries
    out["skills"] = [s for g in profile.get("skills", []) for s in g.get("skills", [])]
    return out


# --------------------------------------------------------------------------- #
# Ranking
# --------------------------------------------------------------------------- #
def _keywords_hit(text: str, job: JobPosting, jd_aliases: set[str]) -> list[str]:
    """JD keywords this bullet genuinely supports.

    Reported per canonical keyword (not per alias) so "SOX" and "Sarbanes-Oxley"
    surface as one hit, and matched against the *rewritten* text so the list
    describes the bullet you'd actually paste.
    """
    from .skills_ontology import SKILL_ALIASES

    low = text.lower()
    return [kw for kw in job.all_keywords
            if any(contains_phrase(low, a) for a in SKILL_ALIASES.get(kw, [kw]))]


def _rank_entry(raw_bullets: list[str], kind: str, jd_aliases: set[str],
                jd_text: str) -> list[tuple[str, float, str]]:
    """(text, relevance, verdict) for one entry's bullets, strongest first.

    The keep/cut line is `MAX_BULLETS[kind]` — the same budget the generator
    uses when it selects bullets for a one-page résumé, so the workbench and the
    generator agree on what earns its space.
    """
    scored = sorted(
        ((t, _bullet_relevance(_make_bullet(t).model_dump(), jd_aliases, jd_text))
         for t in raw_bullets),
        key=lambda pair: pair[1], reverse=True,
    )
    budget = MAX_BULLETS[kind]
    out = []
    for rank, (text, rel) in enumerate(scored):
        verdict = LEAD if rank == 0 else (KEEP if rank < budget else CUT)
        out.append((text, rel, verdict))
    return out


def _order_skills(skills: list[str], job: JobPosting) -> list[str]:
    jd_kw = set(job.all_keywords)
    matching = [s for s in skills if _jd_matches(s, jd_kw)]
    return matching + [s for s in skills if s not in matching]


# --------------------------------------------------------------------------- #
# Line fill
# --------------------------------------------------------------------------- #
def _length_target(text: str) -> int:
    """How long this bullet should be so it fills whole lines.

    A bullet that wraps and leaves its last line 40% full wastes more than half
    a line; the fix is to shrink it into the lines above, not to pad it out. So
    a ragged bullet targets one line *fewer* than it currently occupies. A
    bullet that already fills its lines keeps its length, and a short one-liner
    targets a full single line — the prompt is what stops that turning into
    padding, since it may only fill with facts already on the page.
    """
    fit = line_fit.measure(text)
    if fit.verdict == line_fit.RAGGED:
        return line_fit.target_chars(text, max(1, fit.lines - 1))
    return line_fit.target_chars(text, fit.lines)


# --------------------------------------------------------------------------- #
# Rewriting
# --------------------------------------------------------------------------- #
def _rewrite(texts: list[str], job: JobPosting, ground_truth: str,
             targets: list[int] | None = None) -> list[str]:
    """Rewrite bullets in the JD's language. Returns originals on any failure —
    a bullet you can paste is worth more than an exception."""
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    system = [{
        "type": "text",
        "text": (
            "You rewrite resume bullets to mirror a target job description's "
            "language WITHOUT inventing any facts, numbers, tools, or outcomes "
            "not already present in the bullet or in the source material below.\n"
            "HARD RULES — a bullet that breaks one of these is worse than no "
            "rewrite at all, because the candidate will be asked about it in an "
            "interview:\n"
            "1. Never change WHAT the work was about. 'breeder reporting' may "
            "not become 'financial reporting'; a recipe app may not become a "
            "compliance system. The domain is a fact.\n"
            "2. Never append a purpose or outcome clause the original does not "
            "state — no '...supporting audit readiness', '...strengthening "
            "internal controls' unless the original already says so.\n"
            "3. Change verbs and terminology, not substance. Reach for a JD "
            "term only where it genuinely names what was already done.\n"
            "4. When in doubt, return the bullet unchanged. An honest original "
            "beats a keyword-stuffed rewrite.\n"
            "LENGTH — each bullet carries a `target_chars`. Land within about "
            "5% of it, so the bullet fills its lines on the page instead of "
            "dribbling three words onto a line of its own. Getting there by "
            "cutting filler is always right; getting there by adding words is "
            "only allowed when the added words are facts already in the "
            "original bullet or the source material. If you cannot reach the "
            "target honestly, come in under it — rules 1-4 outrank the length.\n"
            "Strong action verb first, no pronouns. Return ONLY a JSON array "
            "of strings of the same length and order as the input.\n"
            + RESUME_BULLET_RULES + STYLE_RULES + "\n"
            "SOURCE MATERIAL (ground truth — never claim beyond this):\n"
            + ground_truth
        ),
        "cache_control": {"type": "ephemeral"},
    }]
    if targets is None:
        targets = [_length_target(t) for t in texts]
    payload = [{"text": t, "target_chars": n} for t, n in zip(texts, targets)]
    user = (
        f"TARGET ROLE: {job.title} ({job.role_type}). "
        f"KEY TERMS: {', '.join(job.all_keywords)}\n\n"
        f"BULLETS:\n{json.dumps(payload, indent=2)}"
    )
    msg = client.messages.create(
        model=config.ANTHROPIC_MODEL_FAST,
        max_tokens=min(2000, 150 + 60 * len(texts)),
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    print_llm_usage(f"bullet workbench ({config.ANTHROPIC_MODEL_FAST})", msg)
    raw = "".join(b.text for b in msg.content if b.type == "text").strip()
    start = raw.find("[")
    if start < 0:
        return texts
    new, _ = json.JSONDecoder().raw_decode(raw[start:])
    if len(new) != len(texts):
        return texts
    return [n.strip() if isinstance(n, str) and n.strip() else old
            for n, old in zip(new, texts)]


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def tailor_bullets(job: JobPosting, resume_text: str | None = None,
                   profile: dict | None = None,
                   use_llm: bool | None = None,
                   rewrite_cuts: bool = False) -> BulletWorkbench:
    """Tailor every bullet in `resume_text` (or the master profile) against `job`.

    Only kept bullets are sent for rewriting by default: a cut bullet isn't
    going in the document, so paying to reword it is waste. Pass
    `rewrite_cuts=True` to reword everything anyway.
    """
    if resume_text and resume_text.strip():
        entries, source = parse_resume_text(resume_text), "resume"
        ground_truth = resume_text.strip()
    else:
        profile = profile if profile is not None else _load_profile()
        entries, source = _entries_from_profile(profile), "profile"
        ground_truth = profile_facts_json(profile)

    jd_aliases = _jd_aliases(job)
    jd_text = job.raw_text

    out: list[TailoredBullet] = []
    for kind in ("experience", "leadership", "projects"):
        for heading, raw_bullets in entries.get(kind, []):
            for text, rel, verdict in _rank_entry(raw_bullets, kind, jd_aliases, jd_text):
                out.append(TailoredBullet(
                    section=kind, entry=heading, original=text, tailored=text,
                    relevance=rel, verdict=verdict))

    if use_llm is None:
        use_llm = config.has_llm()
    rewritten = False
    targets = [b for b in out if rewrite_cuts or b.verdict != CUT]
    if use_llm and config.has_llm() and targets:
        try:
            new = _rewrite([b.original for b in targets], job, ground_truth)
            for b, t in zip(targets, new):
                b.tailored = t
            rewritten = True
        except Exception as exc:
            print(f"  ! bullet rewrite failed ({exc}); keeping original phrasing")

    for b in out:
        b.tailored = polish_bullet(b.tailored)

    # Repair pass: whatever still spills onto a line it doesn't fill gets one
    # more attempt, this time purely as a trim. Asking for length and JD
    # language in a single shot reliably loses the length half.
    if rewritten:
        _tighten(targets, job, ground_truth)

    for b in out:
        b.tailored = polish_bullet(b.tailored)
        b.keywords = _keywords_hit(b.tailored, job, jd_aliases)
        b.fit = line_fit.measure(b.tailored)

    return BulletWorkbench(source=source, bullets=out, rewritten=rewritten,
                           skills=_order_skills(entries.get("skills", []), job))


VARIANTS_PER_BULLET = 3


def _tighten(bullets: list[TailoredBullet], job: JobPosting,
             ground_truth: str) -> None:
    """Make the bullets that waste a line fill their lines instead.

    Asking a model to hit a length does not work. Told "about 101 characters"
    it returns 116 — one line plus three words, the exact waste we're removing
    — and telling it to cut a measured 18 more characters just produces another
    near miss. Two rounds of that converged on nothing.

    So the model does what it is good at (write several honest shortenings) and
    this code does what it is good at (measure them exactly and pick). Each
    ragged bullet comes back as a ladder of progressively shorter variants; we
    keep the one that fills best. Variants are delete-only, so the worst case
    is a bullet that says less, never one that says something untrue.
    """
    ragged = [b for b in bullets if line_fit.measure(b.tailored).wastes_a_line]
    if not ragged:
        return
    try:
        ladders = _shortening_ladder(ragged, ground_truth)
    except Exception as exc:
        print(f"  ! line-fill pass failed ({exc}); keeping first-pass wording")
        return
    fixed = 0
    for bullet, ladder in zip(ragged, ladders):
        best = _best_fitting(bullet.tailored, ladder)
        if best != bullet.tailored:
            bullet.tailored = best
            fixed += 1
    still = sum(1 for b in ragged if line_fit.measure(b.tailored).wastes_a_line)
    print(f"  · line fill: {fixed}/{len(ragged)} ragged bullets tightened"
          + (f", {still} still short (reported, not faked)" if still else ""))


def _best_fitting(current: str, variants: list[str]) -> str:
    """Pick the wording that fills its lines best: fewest lines first, then the
    fullest last line — so among options that cost the same space, the one that
    says the most wins, rather than the shortest.

    `current` competes too, so a bad ladder can never make a bullet worse. A
    variant longer than `current` is dropped outright: the ladder prompt is
    delete-only, so extra length means it added something, and an addition is
    exactly the failure mode that puts a claim John can't defend on the page.
    """
    def key(text: str):
        fit = line_fit.measure(text)
        return (fit.lines, -fit.last_fill)

    candidates = [current] + [
        polished for polished in
        (polish_bullet(v) for v in variants if isinstance(v, str) and v.strip())
        if len(polished) <= len(current)
    ]
    return min(candidates, key=key)


def _shortening_ladder(ragged: list[TailoredBullet],
                       ground_truth: str) -> list[list[str]]:
    """Ask for `VARIANTS_PER_BULLET` progressively shorter cuts of each bullet."""
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    system = [{
        "type": "text",
        "text": (
            "You shorten resume bullets. For each input bullet return "
            f"{VARIANTS_PER_BULLET} progressively shorter versions: the first "
            "trimmed lightly, the last cut to its essentials (roughly half). "
            "Another program measures them against the page and picks one, so "
            "give a real spread of lengths rather than three near-identical "
            "lines.\n"
            "RULES:\n"
            "1. DELETE words only. Never add a word, number, tool, or claim "
            "that is not already in the bullet.\n"
            "2. Cut filler first — 'that', 'in order to', doubled adjectives, "
            "a trailing clause that restates the point. Metrics and specific "
            "nouns go last.\n"
            "3. Keep the leading action verb, and keep every version true.\n"
            "4. No markdown, no bold, no asterisks.\n"
            "Return ONLY a JSON array of arrays of strings: one inner array "
            "per input bullet, in order.\n"
            + RESUME_BULLET_RULES + STYLE_RULES + "\n"
            "SOURCE MATERIAL (ground truth):\n" + ground_truth
        ),
        "cache_control": {"type": "ephemeral"},
    }]
    texts = [b.tailored for b in ragged]
    msg = client.messages.create(
        model=config.ANTHROPIC_MODEL_FAST,
        max_tokens=min(4000, 200 + 90 * VARIANTS_PER_BULLET * len(texts)),
        system=system,
        messages=[{"role": "user", "content":
                   f"BULLETS:\n{json.dumps(texts, indent=2)}"}],
    )
    print_llm_usage(f"line-fill variants ({config.ANTHROPIC_MODEL_FAST})", msg)
    raw = "".join(b.text for b in msg.content if b.type == "text").strip()
    start = raw.find("[")
    if start < 0:
        return [[] for _ in texts]
    ladders, _ = json.JSONDecoder().raw_decode(raw[start:])
    if len(ladders) != len(texts):
        return [[] for _ in texts]
    return [lad if isinstance(lad, list) else [] for lad in ladders]


def _load_profile() -> dict:
    if not config.PROFILE_JSON.exists():
        raise SystemExit(
            f"No résumé text given and no master profile at {config.PROFILE_JSON}. "
            "Paste a résumé or run `python -m job_bot.build_profile` first."
        )
    return json.loads(config.PROFILE_JSON.read_text(encoding="utf-8"))


SECTION_LABELS = {"experience": "Experience", "leadership": "Leadership",
                  "projects": "Projects"}
VERDICT_MARK = {LEAD: "★ lead", KEEP: "· keep", CUT: "✕ cut"}


def _fill_note(fit: line_fit.Fit) -> str:
    """Plain-language version of a Fit, for the CLI and the copy-all markdown."""
    pct = round(fit.last_fill * 100)
    if fit.verdict == line_fit.RAGGED:
        return (f"line {fit.lines} is only {pct}% full — cut ~{fit.trim_chars} "
                f"chars to save a line")
    if fit.verdict == line_fit.SHORT:
        return f"fills {pct}% of the line — room for ~{fit.add_chars} more chars"
    return f"fills {pct}% of the last line"


def to_markdown(wb: BulletWorkbench, job: JobPosting) -> str:
    """The workbench as pasteable markdown — the CLI's output, and what the
    'copy all' button in the UI produces."""
    lines = [f"# Tailored bullets — {job.title or 'role'} @ {job.company or '—'}", ""]
    if not wb.rewritten:
        lines += ["_No API key — bullets are originals, ranked but not reworded._", ""]
    last_entry = None
    for b in wb.bullets:
        if b.entry != last_entry:
            lines += ["", f"## {SECTION_LABELS[b.section]} — {b.entry}", ""]
            last_entry = b.entry
        kw = f"  `{', '.join(b.keywords)}`" if b.keywords else ""
        lines.append(f"- [{VERDICT_MARK[b.verdict]}] {b.tailored}{kw}")
        if b.fit and b.fit.verdict != line_fit.FULL:
            lines.append(f"    - {_fill_note(b.fit)}")
        if b.changed:
            lines.append(f"    - was: {b.original}")
    if wb.skills:
        lines += ["", "## Skills (JD-matching first)", "", ", ".join(wb.skills)]
    return "\n".join(lines)


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(
        description="Tailored bullets for a JD — for a résumé you format yourself.")
    ap.add_argument("--jd", type=Path, required=True, help="Job description text file")
    ap.add_argument("--resume", type=Path,
                    help="Your résumé as text (default: master_profile.json)")
    ap.add_argument("--url", help="Job posting URL")
    ap.add_argument("--company", help="Override company name")
    ap.add_argument("--no-llm", action="store_true", help="Rank only, no rewriting")
    ap.add_argument("--all", action="store_true", help="Also reword cut bullets")
    ap.add_argument("--json", action="store_true", help="Emit JSON instead of markdown")
    args = ap.parse_args()

    from .jd_parser import parse_jd

    jd_text = args.jd.read_text(encoding="utf-8", errors="replace")
    resume_text = (args.resume.read_text(encoding="utf-8", errors="replace")
                   if args.resume else None)
    job = parse_jd(jd_text, url=args.url, use_llm=(False if args.no_llm else None))
    if args.company:
        job.company = args.company

    wb = tailor_bullets(job, resume_text=resume_text,
                        use_llm=(False if args.no_llm else None),
                        rewrite_cuts=args.all)
    if args.json:
        print(json.dumps(wb.as_dict(), indent=2, ensure_ascii=False))
    else:
        print(to_markdown(wb, job))


if __name__ == "__main__":
    main()
