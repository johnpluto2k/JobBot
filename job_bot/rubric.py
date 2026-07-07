"""Phase 7: rubric scoring for interview answers.

Heuristic scorer checks STAR completeness, quantification, ownership (I vs we),
length, and filler words. Claude provides richer feedback when a key is present.
"""

from __future__ import annotations

import re

from . import config
from .interview_models import AnswerScore, Question

FILLERS = ["um", "uh", "like", "you know", "kind of", "sort of", "basically",
           "actually", "literally", "i guess", "i mean"]

SIT_CUES = ["when", "while", "during", "at the time", "we were", "i was working",
            "the situation", "context"]
TASK_CUES = ["my job", "i was responsible", "my role", "i needed", "tasked", "goal was",
             "i had to"]
ACTION_CUES = ["i ", "i led", "i built", "i analyzed", "i created", "i decided",
               "i implemented", "i organized", "i reached out"]
RESULT_CUES = ["as a result", "resulting", "led to", "increased", "reduced", "saved",
               "improved", "achieved", "delivered", "%", "$"]


def score_answer(question: Question | str, answer: str,
                 use_llm: bool | None = None) -> AnswerScore:
    qtext = question.text if isinstance(question, Question) else str(question)
    qtype = question.qtype if isinstance(question, Question) else "behavioral"
    low = answer.lower()
    words = re.findall(r"[a-zA-Z']+", answer)
    wc = len(words)

    has_s = any(c in low for c in SIT_CUES)
    has_t = any(c in low for c in TASK_CUES)
    has_a = any(c in low for c in ACTION_CUES)
    has_r = any(c in low for c in RESULT_CUES)
    quantified = bool(re.search(r"[%$]|\b\d+\b", answer))

    i_count = len(re.findall(r"\bi\b", low))
    we_count = len(re.findall(r"\bwe\b", low))
    ownership = i_count / (i_count + we_count) if (i_count + we_count) else 0.0

    filler = sum(low.count(f) for f in FILLERS)

    score = 0.0
    strengths: list[str] = []
    improvements: list[str] = []

    # STAR structure (max 50 for behavioral; technical/fit weighted differently)
    if qtype in ("behavioral", "hirevue"):
        for present, name, pts in [(has_s, "Situation", 10), (has_t, "Task", 10),
                                   (has_a, "Action", 15), (has_r, "Result", 15)]:
            if present:
                score += pts
                strengths.append(f"{name} is present.")
            else:
                improvements.append(f"Add a clear {name}.")
    else:
        score += 30 if wc >= 40 else 15  # substance for non-behavioral
        if qtype == "technical":
            improvements.append("Be precise and structured; define terms before applying them.")

    # quantification
    if quantified:
        score += 15
        strengths.append("Quantified impact.")
    else:
        improvements.append("Quantify the result ($, %, counts).")

    # ownership
    if ownership >= 0.5:
        score += 10
        strengths.append("Strong ownership ('I' over 'we').")
    elif (i_count + we_count) > 0:
        improvements.append("Use 'I' more than 'we' — own your specific actions.")

    # length / pacing
    ideal = (60, 180) if qtype in ("behavioral", "hirevue") else (40, 200)
    if ideal[0] <= wc <= ideal[1]:
        score += 15
        strengths.append(f"Good length ({wc} words).")
    elif wc < ideal[0]:
        improvements.append(f"Too short ({wc} words) — add specifics; aim for {ideal[0]}–{ideal[1]}.")
    else:
        improvements.append(f"Too long ({wc} words) — tighten to {ideal[0]}–{ideal[1]}.")

    # fillers
    if filler == 0:
        score += 10
        strengths.append("No filler words.")
    else:
        penalty = min(10, filler * 2)
        score -= penalty
        improvements.append(f"Cut filler words ({filler} found).")

    score = max(0.0, min(100.0, score))
    result = AnswerScore(
        score=round(score, 1), band=_band(score),
        has_situation=has_s, has_task=has_t, has_action=has_a, has_result=has_r,
        quantified=quantified, ownership=round(ownership, 2), word_count=wc,
        filler_count=filler, strengths=strengths, improvements=improvements,
    )

    if use_llm is None:
        use_llm = config.has_llm()
    if use_llm and config.has_llm():
        try:
            _llm_feedback(result, qtext, answer)
        except Exception:
            pass
    return result


def _band(s: float) -> str:
    if s >= 85:
        return "🟢 Strong"
    if s >= 70:
        return "🟡 Solid"
    if s >= 50:
        return "🟠 Developing"
    return "🔴 Needs work"


def _llm_feedback(result: AnswerScore, qtext: str, answer: str) -> None:
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    prompt = (
        f"As an interviewer, give 2 concise, specific improvements for this answer.\n"
        f"Q: {qtext}\nA: {answer}\nReturn 2 bullet lines."
    )
    msg = client.messages.create(model=config.ANTHROPIC_MODEL, max_tokens=300,
                                 messages=[{"role": "user", "content": prompt}])
    text = "".join(b.text for b in msg.content if b.type == "text").strip()
    extra = [l.strip("-• ").strip() for l in text.splitlines() if l.strip()]
    result.improvements.extend(extra[:2])
