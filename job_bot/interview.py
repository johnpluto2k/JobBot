"""Phase 7 CLI: interview prep + mock interview.

    python -m job_bot.interview --story-bank            # build STAR+ story bank
    python -m job_bot.interview --questions behavioral --firm big4
    python -m job_bot.interview --drill --firm big4     # draw a practice question
    python -m job_bot.interview --drill --qtype technical --answer "..."   # score an answer
    python -m job_bot.interview --mock --firm big4 --rounds 5   # full mock (best with API key)
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

from . import config
from .ats_engine import load_profile
from .questions import FIRM_NOTES, filter_questions
from .rubric import score_answer
from .story_bank import build_story_bank


def _print_story_bank(stories) -> None:
    print(f"\n=== STORY BANK ({len(stories)} stories) ===")
    for i, s in enumerate(stories, 1):
        print(f"\n{i}. {s.title}   [{', '.join(s.competencies)}]"
              + ("  ✓quantified" if s.quantified else ""))
        print(f"   S: {s.situation}")
        if s.task:
            print(f"   T: {s.task}")
        print(f"   A: {s.action}")
        if s.result:
            print(f"   R: {s.result}")
        print(f"   +Reflection: {s.reflection or '[what did you learn? — fill in]'}")
        print(f"   +Connection: {s.connection or '[tie to target role — fill in]'}")


def _print_score(q, ans, sc) -> None:
    print(f"\nQ: {q.text}")
    print(f"A: {ans[:200]}{'…' if len(ans) > 200 else ''}")
    print(f"\nSCORE: {sc.score}/100  {sc.band}")
    star = "".join(["S" if sc.has_situation else "·", "T" if sc.has_task else "·",
                    "A" if sc.has_action else "·", "R" if sc.has_result else "·"])
    print(f"  STAR: [{star}]  quantified={sc.quantified}  ownership={sc.ownership}  "
          f"words={sc.word_count}  fillers={sc.filler_count}")
    if sc.strengths:
        print("  + " + "  + ".join(sc.strengths))
    for imp in sc.improvements:
        print(f"  → {imp}")


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="Interview prep + mock interview (Phase 7).")
    ap.add_argument("--story-bank", action="store_true")
    ap.add_argument("--questions", nargs="?", const="all", metavar="TYPE",
                    help="List questions (optionally a type: behavioral/fit/technical/case/...)")
    ap.add_argument("--drill", action="store_true", help="Draw a practice question")
    ap.add_argument("--qtype", help="Question type for --drill")
    ap.add_argument("--firm", help="Firm type: big4/ib/tech/fintech/corporate/consulting")
    ap.add_argument("--answer", help="Answer text to score against the drilled question")
    ap.add_argument("--mock", action="store_true", help="Run a full mock interview")
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--profile", type=Path)
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--save", action="store_true", help="Save story bank to data/story_bank.json")
    args = ap.parse_args()

    use_llm = False if args.no_llm else None

    if args.story_bank:
        profile = load_profile(args.profile)
        stories = build_story_bank(profile, use_llm=use_llm)
        _print_story_bank(stories)
        if args.save:
            out = config.OUTPUT_DIR / "story_bank.json"
            out.write_text(json.dumps([s.model_dump() for s in stories], indent=2), encoding="utf-8")
            print(f"\nSaved {out}")
        return

    if args.questions is not None:
        qtype = None if args.questions == "all" else args.questions
        qs = filter_questions(qtype, args.firm)
        if args.firm and args.firm in FIRM_NOTES:
            print(f"\n[{args.firm}] {FIRM_NOTES[args.firm]}")
        print(f"\n{len(qs)} question(s):")
        for q in qs:
            tag = f"[{q.qtype}]"
            print(f"  {tag:<12} {q.text}")
            if q.hint:
                print(f"               hint: {q.hint}")
        return

    if args.drill:
        qs = filter_questions(args.qtype, args.firm)
        if not qs:
            print("No questions match that filter.")
            return
        q = random.choice(qs)
        if args.answer:
            sc = score_answer(q, args.answer, use_llm=use_llm)
            _print_score(q, args.answer, sc)
        else:
            print(f"\nDRILL [{q.qtype}]{' / ' + args.firm if args.firm else ''}")
            print(f"\n  Q: {q.text}")
            if q.hint:
                print(f"  hint: {q.hint}")
            print("\n  Structure your answer (STAR+): Situation → Task → Action → Result "
                  "→ +Reflection → +Connection.")
            print("  Score it: re-run with --answer \"your answer text\".")
        return

    if args.mock:
        profile = load_profile(args.profile)
        _run_mock(profile, args.firm, args.rounds, use_llm)
        return

    ap.print_help()


def _run_mock(profile: dict, firm: str | None, rounds: int, use_llm) -> None:
    if use_llm is None:
        use_llm = config.has_llm()
    if use_llm and config.has_llm():
        _llm_mock(profile, firm, rounds)
        return
    # offline structured mock: a scripted round the candidate self-runs
    print("\n=== MOCK INTERVIEW (offline script) ===")
    if firm and firm in FIRM_NOTES:
        print(f"Interviewer profile — {FIRM_NOTES[firm]}\n")
    pool = filter_questions(None, firm)
    seq = (filter_questions("fit", firm)[:1] + filter_questions("behavioral", firm)[:rounds - 2]
           + filter_questions("questions", firm)[:1]) or pool[:rounds]
    for i, q in enumerate(seq[:rounds], 1):
        print(f"Round {i} [{q.qtype}]: {q.text}")
        if q.hint:
            print(f"   ({q.hint})")
    print("\nAnswer each aloud (record yourself), then score with: "
          "python -m job_bot.interview --drill --qtype behavioral --answer \"...\"")
    print("With an ANTHROPIC_API_KEY set, --mock runs a live in-character interviewer that "
          "asks follow-ups and scores each answer.")


def _llm_mock(profile: dict, firm: str | None, rounds: int) -> None:
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    persona = {"big4": "a Deloitte senior manager", "ib": "a Goldman Sachs analyst",
               "tech": "a Google hiring manager", "fintech": "a Stripe team lead"}.get(
                   firm or "", "an experienced interviewer")
    print(f"\n=== LIVE MOCK — interviewer: {persona} ===")
    print("(This requires an interactive terminal; run it directly, not via a pipe.)")
    sys_prompt = (
        f"You are {persona} conducting a {rounds}-round interview for a UMD Accounting + "
        "Information Science student targeting audit/tech-risk/analytics. Ask one question at a "
        "time, react to each answer with a brief follow-up, and at the end give a rubric score."
    )
    messages = [{"role": "user", "content": "Start the interview with your first question."}]
    for _ in range(rounds):
        msg = client.messages.create(model=config.ANTHROPIC_MODEL, max_tokens=400,
                                     system=sys_prompt, messages=messages)
        q = "".join(b.text for b in msg.content if b.type == "text").strip()
        print(f"\nInterviewer: {q}")
        try:
            ans = input("\nYou: ")
        except EOFError:
            print("\n(no input stream — end of offline run)")
            return
        messages.append({"role": "assistant", "content": q})
        messages.append({"role": "user", "content": ans})


if __name__ == "__main__":
    main()
