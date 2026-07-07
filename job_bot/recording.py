"""Interview Recording Analysis (Recommendation #12).

Turns a recorded practice answer (or a whole session) into measurable feedback:
pacing (words per minute), filler frequency per minute, answer length, STAR
compliance, and the specific phrases to cut — building on the Phase 7 rubric.

Input is a *transcript* (text) plus an optional spoken `duration_seconds` (from
the recording's length). Transcription itself is out of scope/offline — feed the
text from any transcriber (e.g. an MCP, Whisper, or your phone's voice memo
transcript). Everything else runs locally with no API key.
"""

from __future__ import annotations

import re

from .rubric import FILLERS, _band, score_answer

# Conversational speaking pace guidance (words per minute).
PACE_SLOW, PACE_FAST = 110, 175
# Weak hedges/qualifiers worth flagging beyond the rubric's filler list.
HEDGES = ["i think", "maybe", "probably", "kind of", "sort of", "just", "a little bit",
          "to be honest", "honestly", "i guess", "or something", "stuff like that"]


def _filler_breakdown(text: str) -> dict[str, int]:
    low = text.lower()
    counts = {f: low.count(f) for f in FILLERS}
    return {k: v for k, v in counts.items() if v > 0}


def _hedges(text: str) -> dict[str, int]:
    low = text.lower()
    counts = {h: len(re.findall(rf"(?<![a-z]){re.escape(h)}(?![a-z])", low)) for h in HEDGES}
    return {k: v for k, v in counts.items() if v > 0}


def analyze_recording(transcript: str, duration_seconds: float | None = None,
                      question: str = "Tell me about yourself", qtype: str = "behavioral",
                      use_llm: bool | None = None) -> dict:
    rub = score_answer(_q(question, qtype), transcript, use_llm=use_llm)
    words = rub.word_count
    fillers = _filler_breakdown(transcript)
    hedges = _hedges(transcript)

    pacing = None
    delivery: list[str] = []
    if duration_seconds and duration_seconds > 0:
        minutes = duration_seconds / 60.0
        wpm = round(words / minutes) if minutes else 0
        fpm = round(rub.filler_count / minutes, 1) if minutes else 0
        pacing = {"wpm": wpm, "duration_seconds": round(duration_seconds),
                  "fillers_per_min": fpm}
        if wpm > PACE_FAST:
            delivery.append(f"Speaking fast ({wpm} wpm) — slow to {PACE_SLOW}-{PACE_FAST} "
                            "wpm; pause at clause breaks.")
        elif wpm < PACE_SLOW:
            delivery.append(f"Speaking slowly ({wpm} wpm) — raise energy toward "
                            f"{PACE_SLOW}-{PACE_FAST} wpm to sound confident.")
        else:
            delivery.append(f"Good pace ({wpm} wpm).")
        if fpm > 4:
            delivery.append(f"High filler rate ({fpm}/min) — silence beats 'um'.")

    cut: list[str] = []
    if fillers:
        cut.append("Fillers: " + ", ".join(f"'{k}' ×{v}" for k, v in
                                            sorted(fillers.items(), key=lambda x: -x[1])))
    if hedges:
        cut.append("Hedges that weaken you: " + ", ".join(f"'{k}' ×{v}" for k, v in
                                                           sorted(hedges.items(), key=lambda x: -x[1])))

    return {
        "question": question,
        "score": rub.score,
        "band": rub.band,
        "word_count": words,
        "star": {"S": rub.has_situation, "T": rub.has_task,
                 "A": rub.has_action, "R": rub.has_result},
        "quantified": rub.quantified,
        "ownership": rub.ownership,
        "filler_count": rub.filler_count,
        "filler_breakdown": fillers,
        "hedges": hedges,
        "pacing": pacing,
        "delivery_notes": delivery,
        "phrases_to_cut": cut,
        "strengths": rub.strengths,
        "improvements": rub.improvements,
    }


def analyze_session(answers: list[dict], use_llm: bool | None = None) -> dict:
    """answers: [{question, transcript, duration_seconds?, qtype?}, ...]"""
    results = [analyze_recording(a["transcript"], a.get("duration_seconds"),
                                 a.get("question", "Question"), a.get("qtype", "behavioral"),
                                 use_llm=use_llm) for a in answers]
    if not results:
        return {"count": 0, "answers": [], "summary": {}}

    scores = [r["score"] for r in results]
    total_fillers = sum(r["filler_count"] for r in results)
    wpms = [r["pacing"]["wpm"] for r in results if r["pacing"]]
    # Most common improvement across the session.
    imp_counts: dict[str, int] = {}
    for r in results:
        for i in r["improvements"]:
            key = re.sub(r"\(.*?\)", "", i).strip()
            imp_counts[key] = imp_counts.get(key, 0) + 1
    top_focus = sorted(imp_counts.items(), key=lambda x: -x[1])[:3]

    summary = {
        "avg_score": round(sum(scores) / len(scores), 1),
        "best": round(max(scores), 1),
        "worst": round(min(scores), 1),
        "band": _band(sum(scores) / len(scores)),
        "total_fillers": total_fillers,
        "avg_wpm": round(sum(wpms) / len(wpms)) if wpms else None,
        "top_focus_areas": [k for k, _ in top_focus],
    }
    return {"count": len(results), "answers": results, "summary": summary}


def _q(text: str, qtype: str):
    from .interview_models import Question
    try:
        return Question(text=text, qtype=qtype)
    except Exception:
        return text


def format_analysis(a: dict) -> str:
    lines = ["\n" + "=" * 60,
             f"RECORDING ANALYSIS — {a['band']}  ({a['score']}/100)",
             f"Q: {a['question']}",
             "=" * 60,
             f"  Words: {a['word_count']}   "
             f"STAR: {''.join(k for k, v in a['star'].items() if v) or 'none'}   "
             f"Quantified: {'yes' if a['quantified'] else 'no'}   "
             f"Ownership: {a['ownership']:.0%}"]
    if a["pacing"]:
        p = a["pacing"]
        lines.append(f"  Pace: {p['wpm']} wpm over {p['duration_seconds']}s   "
                     f"Fillers/min: {p['fillers_per_min']}")
    for d in a["delivery_notes"]:
        lines.append(f"  • {d}")
    for c in a["phrases_to_cut"]:
        lines.append(f"  ✂ {c}")
    if a["strengths"]:
        lines.append("  Strengths: " + "; ".join(a["strengths"]))
    if a["improvements"]:
        lines.append("  Improve:")
        for i in a["improvements"]:
            lines.append(f"     → {i}")
    lines.append("=" * 60 + "\n")
    return "\n".join(lines)


DEMO = ("So, um, basically when I was working at the Scion Group, I kind of had this "
        "situation where, you know, the billing records were a mess. I think I was responsible "
        "for fixing them, and honestly I just sort of went through the CRM and, like, validated "
        "everything. As a result we improved data accuracy by 18 percent, which was actually "
        "really good I guess.")


def main() -> None:
    import argparse
    import json
    import sys
    from pathlib import Path

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="Interview recording analysis (Recommendation #12).")
    ap.add_argument("--file", type=Path, help="Transcript text file")
    ap.add_argument("--text", help="Inline transcript text")
    ap.add_argument("--duration", type=float, help="Spoken duration in seconds (for pacing)")
    ap.add_argument("--question", default="Tell me about a time you improved a process")
    ap.add_argument("--qtype", default="behavioral")
    ap.add_argument("--session", type=Path, help="JSON list of {question,transcript,duration_seconds}")
    ap.add_argument("--demo", action="store_true", help="Analyze a built-in filler-heavy sample")
    ap.add_argument("--no-llm", action="store_true")
    args = ap.parse_args()
    use_llm = False if args.no_llm else None

    if args.session:
        data = json.loads(args.session.read_text("utf-8"))
        res = analyze_session(data, use_llm=use_llm)
        for r in res["answers"]:
            print(format_analysis(r))
        s = res["summary"]
        print("=" * 60)
        print(f"SESSION SUMMARY — {res['count']} answers, avg {s['avg_score']}/100 ({s['band']})")
        print(f"  Best {s['best']} / Worst {s['worst']}   Total fillers {s['total_fillers']}"
              + (f"   Avg pace {s['avg_wpm']} wpm" if s['avg_wpm'] else ""))
        if s["top_focus_areas"]:
            print("  Focus next on: " + "; ".join(s["top_focus_areas"]))
        print("=" * 60)
        return

    transcript = (DEMO if args.demo else
                  (args.file.read_text("utf-8", errors="replace") if args.file else (args.text or "")))
    duration = args.duration or (22.0 if args.demo else None)
    if not transcript.strip():
        raise SystemExit("Provide a transcript via --file, --text, --session, or --demo.")
    print(format_analysis(analyze_recording(transcript, duration, args.question,
                                            args.qtype, use_llm=use_llm)))


if __name__ == "__main__":
    main()
