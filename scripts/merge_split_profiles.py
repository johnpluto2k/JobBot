#!/usr/bin/env python3
"""One-off: reunite the two master_profile.json copies the worktree split created.

`data/` is gitignored, so it was never shared between git worktrees - each one
grew a private copy of master_profile.json and job_bot.db. Two copies then drifted
in opposite directions:

  canonical  C:\\ClaudeProjects\\Job Bot\\data\\master_profile.json      (what the app reads)
  phantom    ...\\orca\\workspaces\\Job Bot\\resume-adjuster\\data\\...  (edited 2026-08-31)

Neither is a superset, so copying either way loses real data:

  * phantom has the CowSync Full-Stack Developer role - John's only paid software
    experience, and per COACH_STATE the strongest bridge between his Accounting
    and Information Science halves. It also has richer skills (Full-Stack Web
    Development, REST APIs, Business Development, Client Outreach).
  * canonical has personal.github (phantom has null), the 'big-tech' persona and
    'Google' in target_firms (the deliberate Summer 2027 Google track), and the
    CURRENT project URLs. Phantom's project URLs point at github.com/johnbae2k,
    an account that is no longer used - those would be dead links on a resume.

Merge rules, applied per field, chosen so nothing from either copy is dropped:

  experience  <- phantom   (verified strict superset of canonical)
  skills      <- phantom   (verified per-category superset)
  targets     <- canonical (verified superset)
  projects    <- canonical (identical to phantom except the stale URLs)
  personal    <- canonical, with any null field filled in from phantom
  everything else: byte-identical in both, canonical kept

The script refuses to write unless every one of those expectations still holds,
so it cannot silently do the wrong thing if the inputs have moved on.

Usage:  python scripts/merge_split_profiles.py [--apply]
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

CANONICAL = Path(r"C:\ClaudeProjects\Job Bot\data\master_profile.json")
PHANTOM = Path(r"C:\Users\yohan\orca\workspaces\Job Bot\resume-adjuster\data\master_profile.json")


def _key(entry: dict) -> tuple:
    return (entry.get("organization"), entry.get("role"))


def _skill_map(profile: dict) -> dict[str, set]:
    return {g.get("category"): set(g.get("skills") or []) for g in (profile.get("skills") or [])}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write the merge (default: dry run)")
    args = ap.parse_args()

    if not PHANTOM.exists():
        print(f"phantom copy not found: {PHANTOM}\nNothing to merge.")
        return 0

    A = json.loads(CANONICAL.read_text(encoding="utf-8"))
    B = json.loads(PHANTOM.read_text(encoding="utf-8"))

    problems = []

    # --- verify the assumptions the merge rules rest on -----------------------
    exp_a = {_key(e) for e in (A.get("experience") or [])}
    exp_b = {_key(e) for e in (B.get("experience") or [])}
    if not exp_a.issubset(exp_b):
        problems.append(f"canonical experience not a subset of phantom: missing {exp_a - exp_b}")

    sa, sb = _skill_map(A), _skill_map(B)
    for cat, skills in sa.items():
        if not skills.issubset(sb.get(cat, set())):
            problems.append(f"canonical skills[{cat}] not a subset of phantom: {skills - sb.get(cat, set())}")

    ta, tb = A.get("targets") or {}, B.get("targets") or {}
    for k, v in tb.items():
        if isinstance(v, list) and not set(v).issubset(set(ta.get(k) or [])):
            problems.append(f"phantom targets[{k}] has values canonical lacks: {set(v) - set(ta.get(k) or [])}")

    pa = {p.get("name"): p for p in (A.get("projects") or [])}
    pb = {p.get("name"): p for p in (B.get("projects") or [])}
    if set(pa) != set(pb):
        problems.append(f"project name sets differ: {set(pa) ^ set(pb)}")
    for name, p in pa.items():
        other = pb.get(name, {})
        diff = {k for k in set(p) | set(other) if p.get(k) != other.get(k)}
        if diff - {"url"}:
            problems.append(f"project {name!r} differs beyond url: {diff - {'url'}}")

    if problems:
        print("REFUSING TO MERGE - the inputs no longer match this script's assumptions:")
        for p in problems:
            print("  -", p)
        return 1

    # --- build the merge ------------------------------------------------------
    merged = dict(A)
    merged["experience"] = B["experience"]
    merged["skills"] = B["skills"]

    personal = dict(A.get("personal") or {})
    filled = []
    for k, v in (B.get("personal") or {}).items():
        if personal.get(k) in (None, "", []) and v not in (None, "", []):
            personal[k] = v
            filled.append(k)
    merged["personal"] = personal

    # --- report ---------------------------------------------------------------
    gained = [f"{e.get('role')} at {e.get('organization')}"
              for e in merged["experience"] if _key(e) not in exp_a]
    print("merge plan")
    print(f"  experience : {len(A.get('experience') or [])} -> {len(merged['experience'])}")
    for g in gained:
        print(f"      + {g}")
    for cat, skills in _skill_map(merged).items():
        added = skills - sa.get(cat, set())
        if added:
            print(f"  skills[{cat}] + {sorted(added)}")
    print(f"  personal   : kept canonical{', filled ' + ', '.join(filled) if filled else ''}")
    print(f"  targets    : kept canonical (personas={ta.get('personas')})")
    print(f"  projects   : kept canonical URLs (phantom pointed at the stale johnbae2k account)")

    # --- prove nothing was lost ----------------------------------------------
    checks = {
        "CowSync present": any((e.get("organization") or "").lower() == "cowsync"
                               for e in merged["experience"]),
        "every canonical role kept": exp_a.issubset({_key(e) for e in merged["experience"]}),
        "github URL kept": bool((merged.get("personal") or {}).get("github")),
        "Google still a target firm": "Google" in (merged.get("targets") or {}).get("target_firms", []),
        "big-tech persona kept": "big-tech" in (merged.get("targets") or {}).get("personas", []),
        "project URLs on the live account": all(
            "johnbae2k" not in (p.get("url") or "") for p in merged.get("projects") or []),
        "canonical skills all retained": all(
            s.issubset(_skill_map(merged).get(c, set())) for c, s in sa.items()),
        "phantom skills all retained": all(
            s.issubset(_skill_map(merged).get(c, set())) for c, s in sb.items()),
    }
    print("\nno-loss checks")
    for label, ok in checks.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not all(checks.values()):
        print("\nA check failed - not writing.")
        return 1

    if not args.apply:
        print("\nDry run - nothing written. Re-run with --apply to commit.")
        return 0

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(CANONICAL, CANONICAL.with_suffix(f".json.backup_{stamp}"))
    shutil.copy2(PHANTOM, CANONICAL.parent / f"master_profile.phantom_{stamp}.json")
    CANONICAL.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nAPPLIED. Backups written next to {CANONICAL.name}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
