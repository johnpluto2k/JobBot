"""Offer Comparison Engine (Recommendation #13).

Logs competing offers and builds a structured, weighted comparison so the
decision is driven by data instead of emotion. Pure-logic — no API key needed.

For each offer it computes:
  • Total comp        = base + bonus + equity + benefits_value
  • COL-adjusted comp = total scaled to US-average purchasing power (col_index)
  • A weighted score across money, growth, and fit using the candidate's own
    priority weights, normalized across the offers on the table.

Cost-of-living indices: 100 = US average. A higher index means your dollar buys
less, so COL-adjusted comp = total_comp * 100 / col_index.
"""

from __future__ import annotations

from .db import connect

# Rough cost-of-living indices (100 = US average), DMV-focused for John.
COL_INDEX: dict[str, float] = {
    "washington": 152, "washington, dc": 152, "dc": 152, "arlington": 155,
    "mclean": 160, "tysons": 158, "bethesda": 156, "baltimore": 110,
    "college park": 130, "rockville": 145, "reston": 150, "alexandria": 150,
    "new york": 187, "nyc": 187, "manhattan": 230, "san francisco": 195,
    "sf": 195, "boston": 162, "chicago": 120, "seattle": 172, "los angeles": 173,
    "remote": 100, "richmond": 102, "atlanta": 107, "dallas": 103,
}

# Default priority weights (money / growth / fit). Sum need not be 1; normalized.
DEFAULT_WEIGHTS = {"money": 0.5, "growth": 0.25, "fit": 0.25}


def col_for(location: str | None) -> float:
    if not location:
        return 100.0
    low = location.strip().lower()
    for key, idx in COL_INDEX.items():
        if key in low:
            return float(idx)
    return 100.0


def log_offer(company: str, role_title: str | None = None, *, base: float = 0.0,
              bonus: float = 0.0, equity: float = 0.0, benefits_value: float = 0.0,
              location: str | None = None, col_index: float | None = None,
              growth: float = 3.0, fit: float = 3.0, deadline: str | None = None,
              notes: str | None = None) -> int:
    """Persist an offer; auto-fills the COL index from the location if omitted."""
    col = col_index if col_index is not None else col_for(location)
    con = connect()
    try:
        cur = con.execute(
            "INSERT INTO offers (company, role_title, location, base, bonus, equity, "
            "benefits_value, col_index, growth, fit, deadline, notes) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (company, role_title, location, base, bonus, equity, benefits_value,
             col, growth, fit, deadline, notes))
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


def _rows(status: str = "open") -> list[dict]:
    con = connect()
    try:
        q = "SELECT * FROM offers"
        params: tuple = ()
        if status != "all":
            q += " WHERE status=?"
            params = (status,)
        q += " ORDER BY created_at DESC"
        return [dict(r) for r in con.execute(q, params)]
    finally:
        con.close()


def _norm(values: list[float]) -> list[float]:
    """Min-max normalize to 0..1; all-equal -> all 1.0 (no discriminating signal)."""
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi == lo:
        return [1.0 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


def compare(weights: dict | None = None, status: str = "open") -> dict:
    """Score every offer on the table against the candidate's priority weights."""
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    wsum = sum(w.values()) or 1.0
    w = {k: v / wsum for k, v in w.items()}

    offers = _rows(status)
    if not offers:
        return {"offers": [], "weights": w, "winner": None, "insights": []}

    for o in offers:
        o["total_comp"] = round((o["base"] or 0) + (o["bonus"] or 0)
                                + (o["equity"] or 0) + (o["benefits_value"] or 0), 0)
        col = o["col_index"] or 100.0
        o["adjusted_comp"] = round(o["total_comp"] * 100.0 / col, 0)

    money = _norm([o["adjusted_comp"] for o in offers])
    growth = _norm([o["growth"] or 0 for o in offers])
    fit = _norm([o["fit"] or 0 for o in offers])

    for o, m, g, f in zip(offers, money, growth, fit):
        o["score"] = round(100 * (w["money"] * m + w["growth"] * g + w["fit"] * f), 1)
        o["subscores"] = {"money": round(m, 2), "growth": round(g, 2), "fit": round(f, 2)}

    offers.sort(key=lambda x: x["score"], reverse=True)
    winner = offers[0]
    insights = _insights(offers, w)
    return {"offers": offers, "weights": w, "winner": winner, "insights": insights}


def _insights(offers: list[dict], w: dict) -> list[str]:
    out: list[str] = []
    win = offers[0]
    out.append(f"Top pick: {win['company']} ({win['role_title'] or 'role'}) — "
               f"score {win['score']}, COL-adjusted comp ${win['adjusted_comp']:,.0f}.")

    # Highlight where the nominal-vs-adjusted picture flips.
    by_total = sorted(offers, key=lambda x: x["total_comp"], reverse=True)
    if by_total[0]["company"] != max(offers, key=lambda x: x["adjusted_comp"])["company"]:
        rich = by_total[0]
        real = max(offers, key=lambda x: x["adjusted_comp"])
        out.append(f"{rich['company']} pays the most on paper (${rich['total_comp']:,.0f}) but "
                   f"{real['company']} wins on cost-of-living-adjusted purchasing power "
                   f"(${real['adjusted_comp']:,.0f} vs ${rich['adjusted_comp']:,.0f}).")

    if len(offers) > 1:
        gap = win["score"] - offers[1]["score"]
        runner = offers[1]
        if gap < 8:
            out.append(f"It's close: {runner['company']} trails by only {gap:.1f} pts — "
                       f"non-comp factors (team, mentorship, location) should break the tie.")
        else:
            out.append(f"{win['company']} leads {runner['company']} by {gap:.1f} pts — a clear "
                       f"lead under your current priorities ({_wlabel(w)}).")

    deadlines = [o for o in offers if o.get("deadline")]
    if deadlines:
        nxt = min(deadlines, key=lambda x: x["deadline"])
        out.append(f"Soonest deadline: {nxt['company']} by {nxt['deadline']} — "
                   f"if you want more time, ask for an extension now.")
    return out


def _wlabel(w: dict) -> str:
    return ", ".join(f"{k} {v*100:.0f}%" for k, v in
                     sorted(w.items(), key=lambda kv: kv[1], reverse=True))


def format_comparison(c: dict) -> str:
    if not c["offers"]:
        return ("\nNo open offers logged. Add one with:\n"
                "  python -m job_bot.offers --add --company X --base 75000 --bonus 8000 "
                "--location \"Washington, DC\"\n")
    lines = ["\n" + "=" * 70,
             f"OFFER COMPARISON  ·  weights: {_wlabel(c['weights'])}",
             "=" * 70,
             f"\n{'RANK':<5}{'COMPANY':<16}{'TOTAL':>12}{'COL-ADJ':>12}{'SCORE':>8}  FACTORS"]
    for i, o in enumerate(c["offers"], 1):
        s = o["subscores"]
        lines.append(f"{i:<5}{(o['company'] or '—')[:15]:<16}"
                     f"${o['total_comp']:>10,.0f}${o['adjusted_comp']:>11,.0f}"
                     f"{o['score']:>8.1f}  money {s['money']:.2f} / growth {s['growth']:.2f}"
                     f" / fit {s['fit']:.2f}")
    lines.append("\nINSIGHTS")
    for ins in c["insights"]:
        lines.append(f"  • {ins}")
    lines.append("=" * 70 + "\n")
    return "\n".join(lines)


def main() -> None:
    import argparse
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="Offer comparison engine (Recommendation #13).")
    ap.add_argument("--add", action="store_true", help="Log a new offer")
    ap.add_argument("--compare", action="store_true", help="Compare open offers (default)")
    ap.add_argument("--list", action="store_true", help="List all offers")
    ap.add_argument("--company")
    ap.add_argument("--role")
    ap.add_argument("--location")
    ap.add_argument("--base", type=float, default=0.0)
    ap.add_argument("--bonus", type=float, default=0.0)
    ap.add_argument("--equity", type=float, default=0.0)
    ap.add_argument("--benefits", type=float, default=0.0)
    ap.add_argument("--col", type=float, help="Cost-of-living index (100=US avg); else from location")
    ap.add_argument("--growth", type=float, default=3.0, help="1-5 company growth/trajectory")
    ap.add_argument("--fit", type=float, default=3.0, help="1-5 role/team fit")
    ap.add_argument("--deadline", help="Decision deadline YYYY-MM-DD")
    ap.add_argument("--w-money", type=float, help="Priority weight: money")
    ap.add_argument("--w-growth", type=float, help="Priority weight: growth")
    ap.add_argument("--w-fit", type=float, help="Priority weight: fit")
    args = ap.parse_args()

    if args.add:
        if not args.company:
            raise SystemExit("--add needs --company (and ideally --base/--location).")
        oid = log_offer(args.company, args.role, base=args.base, bonus=args.bonus,
                        equity=args.equity, benefits_value=args.benefits,
                        location=args.location, col_index=args.col, growth=args.growth,
                        fit=args.fit, deadline=args.deadline)
        print(f"Logged offer #{oid}: {args.company}"
              + (f" — {args.role}" if args.role else "") + ".")
        return

    if args.list:
        for o in _rows("all"):
            print(f"  #{o['id']:<3} {o['status']:<9} {(o['company'] or '—'):<18} "
                  f"base ${o['base'] or 0:,.0f}  {o['location'] or ''}")
        return

    weights = {}
    if args.w_money is not None:
        weights["money"] = args.w_money
    if args.w_growth is not None:
        weights["growth"] = args.w_growth
    if args.w_fit is not None:
        weights["fit"] = args.w_fit
    print(format_comparison(compare(weights or None)))


if __name__ == "__main__":
    main()
