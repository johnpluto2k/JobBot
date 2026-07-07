"""Alumni / Network Coverage Map (Recommendation #14).

Aggregates the connections table by company and overlays it on the target
companies and the live job pipeline, so the networking strategy becomes visible:
which firms have the strongest warm coverage, which targets have weak or zero
coverage (the gaps to fix), and exactly who to reach out to first.

Coverage strength per company = sum of contact warmths, with a small bonus for
relationship diversity (a recruiter + an alum + a team member beats three of the
same). Everything reads from SQLite; no API key required.
"""

from __future__ import annotations

import json

from . import config
from .db import connect
from .skills_ontology import KNOWN_COMPANIES

# Relationship affinity for John specifically — warmer ties first.
REL_RANK = {"recruiter": 5, "pse": 4, "iefs": 4, "terptax": 4, "umd": 3, "alum": 3,
            "first_degree": 2, "second_degree": 1}


def _target_companies() -> list[str]:
    """Pull target firms from the master profile (targets.companies / firms)."""
    if not config.PROFILE_JSON.exists():
        return []
    prof = json.loads(config.PROFILE_JSON.read_text(encoding="utf-8"))
    targets = prof.get("targets") or {}
    names: list[str] = []
    for field in ("target_firms", "companies", "firms", "target_companies", "employers"):
        v = targets.get(field)
        if isinstance(v, list):
            names += [str(x) for x in v]
    # de-dup, preserve order
    seen, out = set(), []
    for n in names:
        k = n.strip().lower()
        if k and k not in seen:
            seen.add(k)
            out.append(n.strip())
    return out


def build_map() -> dict:
    con = connect()
    try:
        conns = [dict(r) for r in con.execute(
            "SELECT company, name, title, relationship, warmth FROM connections "
            "WHERE company IS NOT NULL AND company<>''")]
        job_companies = {r["company"].lower(): r["company"]
                         for r in con.execute("SELECT DISTINCT company FROM jobs "
                                              "WHERE company IS NOT NULL AND company<>''")
                         if r["company"]}
    finally:
        con.close()

    # Aggregate connections by company.
    by_company: dict[str, dict] = {}
    for c in conns:
        comp = c["company"].strip()
        key = comp.lower()
        slot = by_company.setdefault(key, {
            "company": comp, "contacts": [], "warmth_sum": 0.0, "relationships": set()})
        slot["contacts"].append(c)
        slot["warmth_sum"] += float(c.get("warmth") or 0)
        if c.get("relationship"):
            slot["relationships"].add(c["relationship"])

    for slot in by_company.values():
        diversity = len(slot["relationships"])
        slot["coverage"] = round(slot["warmth_sum"] + 0.15 * max(0, diversity - 1), 2)
        slot["count"] = len(slot["contacts"])
        slot["relationships"] = sorted(slot["relationships"])
        # Best person to reach first: warmest, tie-broken by relationship affinity.
        slot["contacts"].sort(
            key=lambda x: (float(x.get("warmth") or 0),
                           REL_RANK.get(x.get("relationship") or "", 0)), reverse=True)
        slot["reach_first"] = slot["contacts"][0]["name"] if slot["contacts"] else None

    covered = sorted(by_company.values(), key=lambda s: s["coverage"], reverse=True)

    # Gap analysis: target companies (or active pipeline companies) with no/weak coverage.
    targets = _target_companies()
    target_keys = {t.lower(): t for t in targets}
    # also treat known firms that appear in the pipeline as implicit targets
    for k, disp in job_companies.items():
        if any(kc in k for kc in KNOWN_COMPANIES) and k not in target_keys:
            target_keys.setdefault(k, disp)

    gaps = []
    for key, disp in target_keys.items():
        match = next((s for s in covered if key in s["company"].lower()
                      or s["company"].lower() in key), None)
        if match is None:
            gaps.append({"company": disp, "coverage": 0.0, "count": 0, "status": "no coverage"})
        elif match["coverage"] < 0.6:
            gaps.append({"company": disp, "coverage": match["coverage"],
                         "count": match["count"], "status": "weak coverage"})

    return {
        "covered": covered,
        "gaps": gaps,
        "targets": targets,
        "total_contacts": len(conns),
        "companies_with_contacts": len(by_company),
    }


def format_map(m: dict) -> str:
    lines = ["\n" + "=" * 64,
             "ALUMNI / NETWORK COVERAGE MAP",
             f"{m['total_contacts']} contacts across {m['companies_with_contacts']} companies",
             "=" * 64,
             "\nSTRONGEST COVERAGE (reach out here first)"]
    if not m["covered"]:
        lines.append("  (no connections imported — run "
                      "`python -m job_bot.decide --import-connections Connections.csv`)")
    for s in m["covered"][:10]:
        rels = ", ".join(s["relationships"]) or "—"
        lines.append(f"  {s['coverage']:>5.2f}  {s['company'][:22]:<22} "
                     f"{s['count']} contact(s) [{rels}]  → start with {s['reach_first']}")

    lines.append("\nCOVERAGE GAPS (targets to build warmth at)")
    if not m["gaps"]:
        lines.append("  None — every target company has warm coverage. 🎉")
    for g in m["gaps"]:
        lines.append(f"  ⚠ {g['company'][:24]:<24} {g['status']}"
                     + (f" (coverage {g['coverage']})" if g["count"] else ""))
    lines.append("=" * 64 + "\n")
    return "\n".join(lines)


def main() -> None:
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print(format_map(build_map()))


if __name__ == "__main__":
    main()
