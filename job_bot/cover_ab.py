"""Cover Letter A/B Testing (Recommendation #10).

Generates two genuinely different cover-letter variants for a role and tracks
which voice earns responses over time, so the system learns John's most
effective tone per firm type:

  • Variant A — formal + finance-led: leads with accounting rigor, controls, and
    CPA-track credibility; measured, traditional tone (fits Big 4 / banks).
  • Variant B — conversational + tech-led: leads with data/analytics and the
    information-science angle; warmer, more direct (fits tech / fintech).

Each variant is logged to `cover_variants`. As you mark which was sent and
whether it drew a response, `analyze()` reports response rate by style/angle and
by firm type, and recommends the winning voice.
"""

from __future__ import annotations

from datetime import date

from . import config
from .db import connect
from .jd_models import JobPosting

FIRM_TYPES = {"big4", "bank", "tech", "other"}


def _facts(profile: dict, job: JobPosting) -> dict:
    personal = profile.get("personal", {})
    edu = (profile.get("education") or [{}])[0]
    exps = profile.get("experience", []) + profile.get("leadership", [])
    top = exps[0] if exps else {}
    bullet = (top.get("bullets") or [{}])[0].get("text", "")
    kws = [k for k in (job.required_keywords or [])[:5]]
    return {
        "name": personal.get("name") or "John Bae",
        "email": personal.get("email") or "",
        "phone": personal.get("phone") or "",
        "company": job.company or "your team",
        "title": job.title or "the role",
        "grad": edu.get("graduation_date") or "2027",
        "org": top.get("organization", ""),
        "bullet": bullet,
        "kw": ", ".join(kws[:3]) or "audit, data analysis, and internal controls",
        "role_type": job.role_type or "high-impact",
    }


def _variant_formal_finance(f: dict) -> str:
    today = date.today().strftime("%B %d, %Y")
    exp = (f" At {f['org']}, I {f['bullet'][0].lower() + f['bullet'][1:]}."
           if f["bullet"] else "")
    return f"""{today}

Dear {f['company']} Hiring Team,

I am writing to apply for the {f['title']} position. As an Accounting and Information Science student at the University of Maryland graduating in {f['grad']}, I have built disciplined strengths in {f['kw']} — the foundation this role demands, and the same rigor I am carrying toward the CPA.

Your posting emphasizes {f['kw']}, and my record maps directly to it.{exp} I bring a controls-minded, detail-first approach and consistently document and quantify the impact of my work.

I would welcome the opportunity to bring this discipline to {f['company']} and to discuss how my background supports your team's objectives. Thank you for your time and consideration.

Sincerely,
{f['name']}
{f['email']}  |  {f['phone']}
"""


def _variant_conversational_tech(f: dict) -> str:
    today = date.today().strftime("%B %d, %Y")
    exp = (f" When I {f['bullet'][0].lower() + f['bullet'][1:]} at {f['org']}, I saw firsthand how "
           "the right data turns a messy process into a clear decision." if f["bullet"] else "")
    return f"""{today}

Hi {f['company']} team,

I'm excited about the {f['title']} role — it sits right where I've been pointing my career: the intersection of accounting and data. I'm a UMD Accounting + Information Science student (graduating {f['grad']}), and I like solving control and risk problems with analytics, not just spreadsheets.

What caught my eye is your focus on {f['kw']}.{exp} I move quickly, ask good questions, and care about getting the numbers — and the story behind them — right.

I'd love to talk about how I can help {f['company']}'s team. Thanks for considering my application!

Best,
{f['name']}
{f['email']}  |  {f['phone']}
"""


def generate_variants(profile: dict, job: JobPosting, *, firm_type: str = "other",
                      use_llm: bool | None = None) -> list[dict]:
    f = _facts(profile, job)
    if use_llm is None:
        use_llm = config.has_llm()
    a_text, b_text = None, None
    if use_llm and config.has_llm():
        try:
            a_text = _llm_variant(f, "formal", "finance")
            b_text = _llm_variant(f, "conversational", "tech")
        except Exception as exc:  # pragma: no cover
            print(f"  ! LLM variant generation failed ({exc}); using templates")
    a_text = a_text or _variant_formal_finance(f)
    b_text = b_text or _variant_conversational_tech(f)
    return [
        {"label": "A", "style": "formal", "angle": "finance", "firm_type": firm_type,
         "company": job.company, "role_title": job.title, "text": a_text},
        {"label": "B", "style": "conversational", "angle": "tech", "firm_type": firm_type,
         "company": job.company, "role_title": job.title, "text": b_text},
    ]


def _llm_variant(f: dict, style: str, angle: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    tone = ("formal and measured, leading with accounting rigor and internal controls"
            if style == "formal" else
            "warm and conversational, leading with data/analytics and the information-science angle")
    prompt = (
        f"Write a one-page cover letter ({3} short paragraphs) for {f['name']}, a UMD "
        f"Accounting + Information Science student (grad {f['grad']}) applying to the "
        f"{f['title']} role at {f['company']}. Voice: {tone}. Work in these terms naturally: "
        f"{f['kw']}. Use only real facts; invent nothing. Return only the letter."
    )
    msg = client.messages.create(model=config.ANTHROPIC_MODEL, max_tokens=900,
                                 messages=[{"role": "user", "content": prompt}])
    return "".join(b.text for b in msg.content if b.type == "text").strip()


def log_variants(variants: list[dict]) -> list[int]:
    con = connect()
    ids = []
    try:
        for v in variants:
            cur = con.execute(
                "INSERT INTO cover_variants (company, role_title, firm_type, style, angle, label) "
                "VALUES (?,?,?,?,?,?)",
                (v["company"], v["role_title"], v["firm_type"], v["style"], v["angle"], v["label"]))
            ids.append(cur.lastrowid)
        con.commit()
    finally:
        con.close()
    return ids


def mark_sent(variant_id: int, on: str | None = None) -> None:
    con = connect()
    try:
        con.execute("UPDATE cover_variants SET sent=1, sent_date=? WHERE id=?",
                    (on or date.today().isoformat(), variant_id))
        con.commit()
    finally:
        con.close()


def record_response(variant_id: int, response: str, on: str | None = None) -> None:
    con = connect()
    try:
        con.execute("UPDATE cover_variants SET response=?, response_date=? WHERE id=?",
                    (response, on or date.today().isoformat(), variant_id))
        con.commit()
    finally:
        con.close()


def _rate(rows: list[dict]) -> dict:
    sent = [r for r in rows if r["sent"]]
    positive = [r for r in sent if r["response"] in ("reply", "interview")]
    return {"sent": len(sent), "responses": len(positive),
            "rate": round(100 * len(positive) / len(sent), 1) if sent else None}


def analyze() -> dict:
    con = connect()
    try:
        rows = [dict(r) for r in con.execute("SELECT * FROM cover_variants")]
    finally:
        con.close()
    if not rows:
        return {"total": 0, "by_style": {}, "by_angle": {}, "by_firm_type": {},
                "winner": None, "insights": []}

    def group(field: str) -> dict:
        keys = sorted({r[field] for r in rows if r.get(field)})
        return {k: _rate([r for r in rows if r.get(field) == k]) for k in keys}

    by_style = group("style")
    by_angle = group("angle")
    by_firm = group("firm_type")

    # Winner = style with the best response rate among those with sent data.
    scored = [(k, v["rate"]) for k, v in by_style.items() if v["rate"] is not None]
    winner = max(scored, key=lambda kv: kv[1])[0] if scored else None

    insights = []
    if winner:
        insights.append(f"Your '{winner}' voice has the best response rate so far "
                        f"({by_style[winner]['rate']}% over {by_style[winner]['sent']} sent).")
    else:
        insights.append("Not enough sent/response data yet — log outcomes with "
                        "`--sent` and `--response` to learn your best voice.")
    for ft, v in by_firm.items():
        if v["rate"] is not None and v["sent"] >= 2:
            insights.append(f"At {ft} firms you're converting {v['rate']}% "
                            f"({v['responses']}/{v['sent']}).")
    return {"total": len(rows), "by_style": by_style, "by_angle": by_angle,
            "by_firm_type": by_firm, "winner": winner, "insights": insights}


def main() -> None:
    import argparse
    import sys
    from pathlib import Path

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="Cover-letter A/B testing (Recommendation #10).")
    ap.add_argument("--file", type=Path, help="JD file to generate variants for")
    ap.add_argument("--text", help="Inline JD text")
    ap.add_argument("--company")
    ap.add_argument("--firm-type", default="other", choices=sorted(FIRM_TYPES))
    ap.add_argument("--profile", type=Path)
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--sent", type=int, metavar="ID", help="Mark a variant id as sent")
    ap.add_argument("--response", nargs=2, metavar=("ID", "OUTCOME"),
                    help="Record a response: ID none|reply|interview")
    ap.add_argument("--analyze", action="store_true", help="Show A/B response analysis")
    args = ap.parse_args()

    if args.sent is not None:
        mark_sent(args.sent)
        print(f"Marked variant #{args.sent} as sent.")
        return
    if args.response:
        record_response(int(args.response[0]), args.response[1])
        print(f"Recorded '{args.response[1]}' for variant #{args.response[0]}.")
        return
    if args.analyze:
        _print_analysis(analyze())
        return

    from .ats_engine import load_profile
    from .jd_parser import parse_jd

    raw = args.file.read_text(encoding="utf-8", errors="replace") if args.file else (args.text or "")
    if not raw.strip():
        raise SystemExit("Provide a JD via --file or --text (or use --analyze).")
    profile = load_profile(args.profile)
    job = parse_jd(raw, use_llm=False)
    if args.company:
        job.company = args.company
    variants = generate_variants(profile, job, firm_type=args.firm_type,
                                 use_llm=False if args.no_llm else None)
    ids = log_variants(variants)
    config.ensure_dirs()
    for v, vid in zip(variants, ids):
        slug = (job.company or "company").lower().replace(" ", "_")
        out = config.OUTPUT_DIR / f"cover_{slug}_{v['label']}.txt"
        out.write_text(v["text"], encoding="utf-8")
        print(f"\n{'='*64}\nVARIANT {v['label']} (#{vid}) — {v['style']} / {v['angle']}  → {out.name}")
        print("=" * 64)
        print(v["text"])
    print(f"\nLogged 2 variants. After sending, run: "
          f"`python -m job_bot.cover_ab --sent {ids[0]}` then "
          f"`--response {ids[0]} reply`. `--analyze` to see your best voice.")


def _print_analysis(a: dict) -> None:
    if a["total"] == 0:
        print("\nNo cover-letter variants logged yet. Generate some with "
              "`python -m job_bot.cover_ab --file jd.txt --firm-type big4`.")
        return
    print(f"\n=== COVER-LETTER A/B ANALYSIS ({a['total']} variants) ===")
    for label, grp in (("By style", a["by_style"]), ("By angle", a["by_angle"]),
                       ("By firm type", a["by_firm_type"])):
        parts = [f"{k}: {v['rate']}% ({v['responses']}/{v['sent']})" if v["rate"] is not None
                 else f"{k}: no data" for k, v in grp.items()]
        print(f" {label:<14} " + ("  ".join(parts) or "—"))
    print("\n Insights:")
    for i in a["insights"]:
        print(f"   • {i}")
    print("=" * 50)


if __name__ == "__main__":
    main()
