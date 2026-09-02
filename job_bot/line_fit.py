"""Does a bullet fill its line, or dribble three words onto a second one?

A résumé bullet that wraps to a second line and puts "and reporting" on it
wastes a whole line of page. John's rule for tailored bullets is that every
bullet should fill its lines all the way — so the tailoring engine has to be
able to *measure* that, not guess at character counts.

Character counts are a bad proxy: in a proportional serif, observed full lines
in John's Jake's-Resume ran anywhere from 103 to 113 characters. This module
measures typeset width instead, using an advance-width table taken from Times
(metrically close to the template's Latin Modern Roman) and normalised so the
bullet column is exactly 100.0 units.

The column width was calibrated against nine real line breaks in the rendered
PDF: for each break the true column W must satisfy

    width(line)  <=  W  <  width(line + " " + next_word)

Intersecting those nine intervals pins W to a 1.2% window, and the midpoint
reproduces all 9 observed breaks. See tests/test_line_fit.py, which keeps that
honest.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Advance widths in units where the bullet text column == 100.0.
_WIDTH_GROUPS = {
    0.391: "'",
    0.435: "|",
    0.543: " ,.",
    0.609: "/:;\\ijlt",
    0.717: "!()-I[]`fr",
    0.848: "Js",
    0.891: '"',
    0.956: "?acez",
    1.022: "^",
    1.043: "{}",
    1.087: "#$*0123456789_bdghknopquvxy",
    1.174: "~",
    1.217: "+<=>FPS",
    1.326: "ELTZ",
    1.456: "BCR",
    1.565: "ADGHKNOQUVXYw",
    1.695: "&m",
    1.804: "%",
    1.934: "M",
    2.000: "@",
    2.043: "W",
}
CHAR_WIDTH: dict[str, float] = {
    ch: w for w, chars in _WIDTH_GROUPS.items() for ch in chars
}
_DEFAULT_WIDTH = CHAR_WIDTH["n"]

# One full line of the bullet column.
COLUMN = 100.0

# A last line at or above this fraction reads as full. Real "full" lines bottom
# out around 0.90 — a line breaks as soon as the *next* word won't fit, and a
# long next word can leave that much genuine slack — so the bar sits just below.
FULL_AT = 0.88

FULL, RAGGED, SHORT = "full", "ragged", "short"


def width(text: str) -> float:
    """Typeset width of `text` in column units (100.0 == one full line)."""
    return sum(CHAR_WIDTH.get(ch, _DEFAULT_WIDTH) for ch in text)


def wrap(text: str, column: float = COLUMN) -> list[str]:
    """Greedy line-break, the way TeX fills a paragraph of short lines."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = f"{current} {word}" if current else word
        if current and width(trial) > column:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    return lines or [""]


@dataclass
class Fit:
    """How well one bullet fills the lines it occupies."""

    lines: int
    last_fill: float          # 0..1, how full the final line is
    verdict: str              # FULL | RAGGED | SHORT
    trim_chars: int = 0       # approx. characters to cut to drop a line
    add_chars: int = 0        # approx. characters that would fill the line

    @property
    def wastes_a_line(self) -> bool:
        return self.verdict == RAGGED

    def as_dict(self) -> dict:
        return {"lines": self.lines, "last_fill": round(self.last_fill, 3),
                "verdict": self.verdict, "trim_chars": self.trim_chars,
                "add_chars": self.add_chars}


def _avg_char(text: str) -> float:
    """Mean advance width of this bullet's own characters — a better ruler for
    'how many characters is that' than a global average."""
    return (width(text) / len(text)) if text else _DEFAULT_WIDTH


def measure(text: str, column: float = COLUMN) -> Fit:
    """Classify how `text` sits in the column.

    * FULL   — the last line is full; nothing to do.
    * RAGGED — it spills onto a line it doesn't fill. Cutting `trim_chars`
               characters drops a whole line off the page.
    * SHORT  — it's a single line with room left. `add_chars` says how much
               room; filling it is the writer's call, since padding a bullet
               with words that aren't true is worse than a short line.
    """
    text = re.sub(r"\s+", " ", (text or "").strip())
    lines = wrap(text, column)
    last_fill = width(lines[-1]) / column if lines else 0.0
    per_char = _avg_char(text)

    if last_fill >= FULL_AT:
        return Fit(lines=len(lines), last_fill=last_fill, verdict=FULL)
    if len(lines) == 1:
        return Fit(lines=1, last_fill=last_fill, verdict=SHORT,
                   add_chars=max(0, round((column - width(text)) / per_char)))
    # Fitting into one fewer line means losing everything past that budget,
    # with a little slack so the result doesn't land exactly on the boundary.
    budget = (len(lines) - 1) * column * 0.98
    return Fit(lines=len(lines), last_fill=last_fill, verdict=RAGGED,
               trim_chars=max(1, round((width(text) - budget) / per_char)))


def target_chars(text: str, lines: int, column: float = COLUMN) -> int:
    """Roughly how many characters `text` should be cut to, to fill `lines`
    lines exactly. Used to give the rewriter a concrete number to aim at."""
    return max(1, round(lines * column * 0.98 / _avg_char(text)))
