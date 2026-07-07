"""Salary Intelligence Layer (Recommendation #5).

Gives a market salary range for a role + location + experience level so John can
sanity-check an offer or prep a negotiation. Two layers, degrading gracefully:

  1. A curated baseline table of US-average total-comp ranges for the roles John
     targets (Big 4 audit/risk, IB analyst, data/business analyst, etc.), keyed
     by experience level. Always available offline.
  2. Live market points — Glassdoor / Levels.fyi / LinkedIn figures fed in via
     `market_points=[...]` (from web search or a salary MCP); when present they
     blend with / override the baseline.

Location is handled with the same cost-of-living index used by the offer engine,
so a DMV range and an NYC range are comparable in real purchasing power.

This module reads market data the caller supplies; it does not scrape sites
directly (ToS-safe, dependency-free) — mirroring the rest of the system.
"""

from __future__ import annotations

from statistics import median

from .offers import col_for

# Curated US-average TOTAL-COMP baselines (base + typical bonus), USD, by level.
# Levels: intern | new_grad | analyst (0-2 yr) | senior (3-5 yr).
ROLE_BASELINES: dict[str, dict[str, tuple[int, int, int]]] = {
    # role_key: { level: (p25, p50, p75) }
    "audit": {
        "intern": (4800, 5600, 6500), "new_grad": (62000, 70000, 78000),
        "analyst": (70000, 80000, 92000), "senior": (88000, 100000, 115000),
    },
    "technology risk": {
        "intern": (5200, 6200, 7200), "new_grad": (68000, 76000, 85000),
        "analyst": (76000, 86000, 98000), "senior": (95000, 108000, 125000),
    },
    "data analyst": {
        "intern": (5500, 6800, 8000), "new_grad": (68000, 78000, 90000),
        "analyst": (78000, 90000, 105000), "senior": (100000, 118000, 138000),
    },
    "business analyst": {
        "intern": (5500, 6800, 8200), "new_grad": (70000, 82000, 95000),
        "analyst": (80000, 95000, 112000), "senior": (105000, 125000, 145000),
    },
    "investment banking": {
        "intern": (9000, 11000, 13000), "new_grad": (100000, 110000, 120000),
        "analyst": (110000, 150000, 190000), "senior": (175000, 225000, 300000),
    },
    "financial analyst": {
        "intern": (4800, 5800, 7000), "new_grad": (60000, 68000, 78000),
        "analyst": (68000, 80000, 95000), "senior": (90000, 105000, 125000),
    },
}

# Map free-text role to a baseline key.
ROLE_ALIASES: list[tuple[str, str]] = [
    ("technology risk", "technology risk"), ("it risk", "technology risk"),
    ("it audit", "technology risk"), ("cyber", "technology risk"),
    ("internal audit", "audit"), ("external audit", "audit"), ("assurance", "audit"),
    ("audit", "audit"),
    ("data analyst", "data analyst"), ("data scientist", "data analyst"),
    ("analytics", "data analyst"),
    ("business analyst", "business analyst"), ("product analyst", "business analyst"),
    ("investment bank", "investment banking"), ("ib analyst", "investment banking"),
    ("financial analyst", "financial analyst"), ("fp&a", "financial analyst"),
    ("finance", "financial analyst"),
]

LEVELS = ["intern", "new_grad", "analyst", "senior"]

# How much of a location's cost-of-living differential actually shows up in pay.
# ~0.5 reflects that firms pay a partial geographic premium, not the full COL gap.
GEO_DAMPEN = 0.5


def role_key(role: str) -> str:
    low = (role or "").lower()
    for alias, key in ROLE_ALIASES:
        if alias in low:
            return key
    return "financial analyst"  # safe default for John's finance-leaning search


def estimate(role: str, location: str | None = None, level: str = "new_grad", *,
             market_points: list[float] | None = None) -> dict:
    """Return a market range for the role/location/level.

    `market_points` are real observed total-comp figures (USD) from web search /
    a salary source; when given they blend with the curated baseline (median of
    the two p50s) and widen the band to cover the observations.
    """
    key = role_key(role)
    level = level if level in LEVELS else "new_grad"
    p25, p50, p75 = ROLE_BASELINES[key][level]

    # Convert the US-average baseline to the local market. Salaries track cost of
    # living only PARTIALLY — employers pay a geographic premium worth roughly half
    # the COL differential, not the full amount (a new-grad auditor in DC does not
    # earn 52% above the US average). So we dampen the COL delta by GEO_DAMPEN.
    # (Offer comparison still uses the FULL COL index — that measures real
    # purchasing power of actual dollars, which is a different question.)
    col = col_for(location)
    factor = 1.0 + GEO_DAMPEN * (col / 100.0 - 1.0)
    lp25, lp50, lp75 = (round(p25 * factor), round(p50 * factor), round(p75 * factor))

    source = "curated baseline (COL-adjusted)"
    if market_points:
        mp = sorted(float(x) for x in market_points)
        obs_med = median(mp)
        # Blend curated midpoint with observed median; widen band to the data.
        lp50 = round((lp50 + obs_med) / 2)
        lp25 = min(lp25, round(mp[0]))
        lp75 = max(lp75, round(mp[-1]))
        source = f"curated + {len(mp)} live market point(s)"

    return {
        "role": role, "role_key": key, "level": level,
        "location": location or "US average", "col_index": col,
        "p25": lp25, "p50": lp50, "p75": lp75,
        "market_points": sorted(market_points) if market_points else [],
        "source": source,
    }


def assess_offer(total_comp: float, est: dict) -> dict:
    """Position an offer against the market estimate -> verdict + advice."""
    p25, p50, p75 = est["p25"], est["p50"], est["p75"]
    if total_comp < p25:
        verdict, advice = "below market", (
            f"At ${total_comp:,.0f} you're under the 25th percentile (${p25:,.0f}). "
            "Strong case to negotiate up toward the median; lead with your data/controls skills.")
    elif total_comp < p50:
        verdict, advice = "low-market", (
            f"Below median (${p50:,.0f}) but within range. Ask for ${p50:,.0f}+; "
            "a counter near the midpoint is very reasonable.")
    elif total_comp <= p75:
        verdict, advice = "at market", (
            f"Solid — between median and the 75th percentile (${p75:,.0f}). "
            "You can still test for a small bump or a signing bonus.")
    else:
        verdict, advice = "above market", (
            f"Above the 75th percentile (${p75:,.0f}) — a strong offer. "
            "Focus negotiation on non-cash terms (start date, PTO, learning budget).")
    pct = _percentile(total_comp, p25, p50, p75)
    return {"verdict": verdict, "advice": advice, "approx_percentile": pct}


def _percentile(x: float, p25: float, p50: float, p75: float) -> int:
    """Rough percentile placement by linear interpolation between anchors."""
    if x <= p25:
        return max(1, round(25 * x / p25)) if p25 else 1
    if x <= p50:
        return round(25 + 25 * (x - p25) / (p50 - p25)) if p50 > p25 else 25
    if x <= p75:
        return round(50 + 25 * (x - p50) / (p75 - p50)) if p75 > p50 else 50
    return min(99, round(75 + 24 * (x - p75) / p75)) if p75 else 90


def format_estimate(est: dict, offer: float | None = None) -> str:
    lines = ["\n" + "=" * 60,
             f"SALARY INTELLIGENCE — {est['role']} ({est['level']})",
             f"{est['location']}  ·  COL index {est['col_index']:.0f}  ·  {est['source']}",
             "=" * 60,
             f"\n  Market total-comp range (USD):",
             f"    25th  ${est['p25']:>9,.0f}",
             f"    50th  ${est['p50']:>9,.0f}   <- target the median or above",
             f"    75th  ${est['p75']:>9,.0f}"]
    if est["market_points"]:
        lines.append("  Live market points: "
                      + ", ".join(f"${p:,.0f}" for p in est["market_points"]))
    if offer is not None:
        a = assess_offer(offer, est)
        lines += [f"\n  Your offer: ${offer:,.0f}  ->  {a['verdict'].upper()} "
                  f"(~{a['approx_percentile']}th pct)",
                  f"  {a['advice']}"]
    lines.append("=" * 60 + "\n")
    return "\n".join(lines)


def main() -> None:
    import argparse
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="Salary intelligence (Recommendation #5).")
    ap.add_argument("--role", required=True, help="e.g. 'IT audit', 'data analyst'")
    ap.add_argument("--location", help="e.g. 'Washington, DC'")
    ap.add_argument("--level", default="new_grad", choices=LEVELS)
    ap.add_argument("--offer", type=float, help="Your offer's total comp to assess")
    ap.add_argument("--market", action="append", type=float, default=[],
                    help="A live market total-comp data point (repeatable)")
    args = ap.parse_args()
    est = estimate(args.role, args.location, args.level,
                   market_points=args.market or None)
    print(format_estimate(est, args.offer))


if __name__ == "__main__":
    main()
