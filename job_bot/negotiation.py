"""Negotiation script generator — career-ops "negotiation frameworks", adapted.

career-ops ships salary-negotiation frameworks, geographic-discount pushback, and
competing-offer leverage. John already has salary intelligence (salary.py) and
COL-adjusted offer comparison (offers.py); this layer turns those numbers into
paste-ready *scripts* he can actually say/send:

  * counter        — a data-anchored counter tuned to where the offer sits vs market
  * geo_pushback   — rebuts a "your city is cheaper" lowball, using the COL index
  * competing      — leverages another offer without bluffing
  * non_cash       — asks to trade on when base won't move (signing, PTO, start date)
  * email          — a short, professional counter email tying it together

Everything is facts-only and grounded in the market estimate — no fabricated
competing offers, no aggressive ultimatums. Degrades fine with no offer/market
data (returns general-purpose scripts).
"""

from __future__ import annotations

from .salary import assess_offer, estimate


def build(role: str, location: str | None = None, level: str = "new_grad", *,
          offer: float | None = None, market_points: list[float] | None = None,
          competing: float | None = None) -> dict:
    """Return a dict of negotiation scripts grounded in the market estimate."""
    est = estimate(role, location, level, market_points=market_points)
    p50, p75 = est["p50"], est["p75"]
    assessment = assess_offer(offer, est) if offer else None

    # A target: the median if below it, else nudge toward the 75th percentile.
    if offer and offer < p50:
        target = p50
    elif offer and offer < p75:
        target = round((offer + p75) / 2)
    else:
        target = p75
    ask = f"${target:,.0f}"

    scripts: dict[str, str] = {}

    # --- Counter ------------------------------------------------------------
    if offer:
        gap = target - offer
        scripts["counter"] = (
            f"\"Thank you — I'm genuinely excited about this role. Based on my "
            f"research for {role} roles in {est['location']} at this level, the market "
            f"midpoint is around ${p50:,.0f}. Given my background in data analysis and "
            f"internal controls, I was hoping we could get to {ask}"
            + (f" — about ${gap:,.0f} above the current offer" if gap > 0 else "")
            + ". Is there flexibility on the base?\"")
    else:
        scripts["counter"] = (
            f"\"I'm excited about the role. From my research, {role} roles in "
            f"{est['location']} at this level land around ${p50:,.0f}-${p75:,.0f}. "
            f"Could we target the upper half of that range given my skill set?\"")

    # --- Geographic-discount pushback --------------------------------------
    col = est["col_index"]
    if col < 100:
        scripts["geo_pushback"] = (
            f"\"I understand {est['location']} has a lower cost of living, but the value "
            f"I bring — controls testing, SQL/Excel analysis — isn't discounted by "
            f"geography, and much of this work is comparable across markets. I'd ask that "
            f"we benchmark to the role's national market rather than a local discount.\"")
    else:
        scripts["geo_pushback"] = (
            f"\"{est['location']}'s cost of living (index {col:.0f}, above the US average) "
            f"should be reflected in the base — the same salary buys less here, so I'd ask "
            f"we set it against this market specifically.\"")

    # --- Competing-offer leverage ------------------------------------------
    if competing:
        scripts["competing"] = (
            f"\"I want to be transparent: I have another offer at ${competing:,.0f}. Your "
            f"team is my top choice, so I'd love to make this work — if you can get close "
            f"to {ask}, I'm ready to sign.\"")
    else:
        scripts["competing"] = (
            "\"I'm in conversations with a couple of other teams, and your role is my "
            "strong preference. A base nearer " + ask + " would make it an easy yes.\" "
            "(Only say this if it's TRUE — never bluff a competing offer.)")

    # --- Non-cash levers (when base is capped) -----------------------------
    scripts["non_cash"] = (
        "If the base truly can't move, trade on: a signing bonus (often a separate "
        "budget), an earlier comp review (6 months vs 12), extra PTO, a start-date "
        "shift, a professional-development/CPA-exam budget, or remote/hybrid flexibility.")

    # --- Email template -----------------------------------------------------
    scripts["email"] = (
        f"Subject: {role} offer — quick question on compensation\n\n"
        f"Hi [Recruiter],\n\n"
        f"Thank you so much for the offer — I'm excited about the team and the work. "
        f"After researching comparable {role} roles in {est['location']}, I was hoping we "
        f"could revisit the base toward {ask}, which reflects the market midpoint-plus for "
        f"this level and the analytical/controls skills I'd bring on day one.\n\n"
        f"I'm confident we can find a number that works for both of us, and I'm ready to "
        f"move quickly. Would you have a few minutes to discuss?\n\n"
        f"Best,\n[Your name]")

    return {
        "role": role, "level": est["level"], "location": est["location"],
        "market": {"p25": est["p25"], "p50": p50, "p75": p75, "col_index": col,
                   "source": est["source"]},
        "offer": offer, "target": target, "assessment": assessment,
        "scripts": scripts,
    }


def format_scripts(pack: dict) -> str:
    m = pack["market"]
    lines = ["\n" + "=" * 64,
             f"NEGOTIATION PREP — {pack['role']} ({pack['level']}) · {pack['location']}",
             f"Market: 25th ${m['p25']:,.0f} · median ${m['p50']:,.0f} · "
             f"75th ${m['p75']:,.0f}  (COL {m['col_index']:.0f})",
             "=" * 64]
    if pack.get("assessment"):
        a = pack["assessment"]
        lines.append(f"Your offer reads as {a['verdict'].upper()} (~{a['approx_percentile']}th pct).")
    lines.append(f"Recommended ask: ${pack['target']:,.0f}\n")
    titles = {"counter": "COUNTER", "geo_pushback": "GEOGRAPHIC-DISCOUNT PUSHBACK",
              "competing": "COMPETING-OFFER LEVERAGE", "non_cash": "IF BASE IS CAPPED",
              "email": "COUNTER EMAIL"}
    for key, title in titles.items():
        lines.append(f"— {title} " + "-" * (60 - len(title)))
        lines.append(pack["scripts"][key] + "\n")
    lines.append("=" * 64 + "\n")
    return "\n".join(lines)


def main() -> None:
    import argparse
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    from .salary import LEVELS
    ap = argparse.ArgumentParser(description="Negotiation script generator (career-ops frameworks).")
    ap.add_argument("--role", required=True, help="e.g. 'IT audit', 'data analyst'")
    ap.add_argument("--location", help="e.g. 'Washington, DC'")
    ap.add_argument("--level", default="new_grad", choices=LEVELS)
    ap.add_argument("--offer", type=float, help="Your current offer's total comp")
    ap.add_argument("--competing", type=float, help="A real competing offer to leverage")
    ap.add_argument("--market", action="append", type=float, default=[],
                    help="A live market total-comp data point (repeatable)")
    args = ap.parse_args()
    pack = build(args.role, args.location, args.level, offer=args.offer,
                 market_points=args.market or None, competing=args.competing)
    print(format_scripts(pack))


if __name__ == "__main__":
    main()
