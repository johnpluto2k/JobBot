"""Tests for tools/check_resume.py.

The end-to-end tests read the committed PDFs in examples/, so no LaTeX install
is needed. The unit tests exercise the pure functions on synthetic input.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import check_resume as cr  # noqa: E402

EXAMPLES = ROOT / "examples"
RESUME_PDF = str(EXAMPLES / "sam_rivera_resume.pdf")
RESUME_TEX = str(EXAMPLES / "sam_rivera_resume.tex")
LETTER_PDF = str(EXAMPLES / "sam_rivera_cover_letter.pdf")


@pytest.fixture(autouse=True)
def _no_local_counts_file(tmp_path, monkeypatch):
    """Run from an empty folder so a stray resume/bullet_counts.json cannot leak in."""
    monkeypatch.chdir(tmp_path)


def run_json(capsys, *argv):
    code = cr.main([*argv, "--json"])
    report = json.loads(capsys.readouterr().out)
    return code, report, {c["check"]: c for c in report["checks"]}


# ---------------------------------------------------------------- end to end
def test_example_resume_passes_every_check(capsys):
    code, report, checks = run_json(capsys, RESUME_PDF, "--tex", RESUME_TEX)
    assert code == 0 and report["ok"] is True
    assert {name: c["status"] for name, c in checks.items()} == {
        "pages": "PASS", "bullet fill": "PASS", "one line each": "PASS", "bottom gap": "PASS",
        "bad characters": "PASS", "repeated verbs": "PASS", "bullet counts": "PASS",
    }
    bullets = checks["bullet fill"]["bullets"]
    assert len(bullets) == 24
    assert all(92.0 <= b["fill"] < 100.0 and b["lines"] == 1 for b in bullets)
    assert 0.20 <= checks["bottom gap"]["inches"] <= 0.35
    # 0.4in side margins on letter paper: the text block ends at 612 - 28.8 pt.
    assert checks["bullet fill"]["right"] == pytest.approx(583.2, abs=0.5)
    assert [e["have"] for e in checks["bullet counts"]["entries"]] == [3, 3, 3, 2, 2, 2, 3, 3, 3]


def test_example_letter_passes_as_letter(capsys):
    code, report, checks = run_json(capsys, LETTER_PDF, "--letter")
    assert code == 0 and report["kind"] == "letter"
    assert checks["pages"]["status"] == "PASS"
    assert checks["bottom gap"]["status"] == "PASS"
    assert 0.9 <= checks["bottom gap"]["inches"] <= 1.3
    assert checks["bad characters"]["status"] == "PASS"
    assert checks["bullet fill"]["status"] == "SKIP"


def test_letter_checked_as_resume_fails(capsys):
    # Two-line bullets with short last lines and an inch of blank: not a resume.
    code, _, checks = run_json(capsys, LETTER_PDF)
    assert code == 1
    assert checks["bullet fill"]["status"] == "FAIL"
    assert checks["bottom gap"]["status"] == "FAIL"
    assert checks["one line each"]["status"] == "WARN"


def test_text_output_and_exit_code(capsys):
    assert cr.main([RESUME_PDF, "--tex", RESUME_TEX]) == 0
    out = capsys.readouterr().out
    assert "PASS  pages" in out and out.strip().endswith("RESULT: PASS")


def test_count_override_file_can_fail_the_example(tmp_path, capsys):
    rules = tmp_path / "counts.json"
    rules.write_text(json.dumps({"entries": {"Data Analyst Intern": 5}}), encoding="utf-8")
    code, _, checks = run_json(capsys, RESUME_PDF, "--tex", RESUME_TEX, "--counts", str(rules))
    assert code == 1 and checks["bullet counts"]["status"] == "FAIL"


def test_default_counts_file_is_picked_up(tmp_path, capsys):
    (tmp_path / "resume").mkdir()
    (tmp_path / "resume" / "bullet_counts.json").write_text(
        json.dumps({"sections": {"Projects": 4}}), encoding="utf-8")
    code, _, checks = run_json(capsys, RESUME_PDF, "--tex", RESUME_TEX)
    assert code == 1
    assert [e["entry"][:7] for e in checks["bullet counts"]["entries"] if not e["ok"]] == \
        ["Transit", "Campus ", "Pocket "]


def test_master_mode_skips_page_gap_and_counts(capsys):
    code, _, checks = run_json(capsys, RESUME_PDF, "--master")
    assert code == 0
    assert checks["bottom gap"]["status"] == "SKIP"
    assert checks["bullet counts"]["status"] == "SKIP"
    assert checks["bullet fill"]["status"] == "PASS"


def test_missing_file_is_an_error_not_a_pass(capsys):
    assert cr.main(["no_such_file.pdf"]) == 2


# ---------------------------------------------------------------- verbs
def test_repeated_verbs_ignores_case_and_punctuation():
    texts = ["Built a dashboard", "built a script", "Analyzed records", "Led a team",
             "Co-built, with two others, an app", "Analyzed: more records", ""]
    assert cr.repeated_verbs(texts) == {"analyzed": 2, "built": 2}


def test_no_repeats_returns_empty():
    assert cr.repeated_verbs(["Built x", "Wrote y", "Led z"]) == {}


def test_check_verbs_fails_resume_but_warns_master():
    line = lambda y, verb: cr.Line(1, 50, 500, y, y + 10, [(50, "•"), (60, verb), (90, "things")])
    bullets = cr.find_bullets([line(700, "Built"), line(688, "Built")])
    assert cr.check_verbs(bullets, master=False).status == cr.FAIL
    assert cr.check_verbs(bullets, master=True).status == cr.WARN


# ---------------------------------------------------------------- bullet counts
TEX = r"""
\newcommand{\resumeItem}[1]{\item\small{#1}}
\newcommand{\resumeSubheading}[4]{\item #1 #2 #3 #4}
\begin{document}
\section{Education}
  \resumeSubheading
    {Some University}{2027}{B.S. Something}{GPA}
\section{Experience}
  \resumeSubheading
    {Data Analyst Intern}{City, ST}
    {Acme \& Sons -- Freight}{2026}
    \resumeItemListStart
      \resumeItem{One}
      \resumeItem{Two with {nested} braces}
      % \resumeItem{Commented out, must not count}
      \resumeItem{Three, 9\% better}
    \resumeItemListEnd
  \resumeSubheading{Cashier}{City, ST}{Shop}{2025}
    \resumeItemListStart
      \resumeItem{One}
    \resumeItemListEnd
\section{Projects}
  \resumeProjectHeading
    {\textbf{Ledger -- Tracker} $|$ \emph{Python}}{}
    \resumeItemListStart
      \resumeItem{One} \resumeItem{Two}
      \resumeItem{Three}
    \resumeItemListEnd
\section{Leadership \& Involvement}
  \resumeSubheading
    {Chess Club}{City, ST}{President}{2025}
      \resumeItem{One}
      \resumeItem{Two}
\section{Activities}
  \resumeSubheading
    {Intramural Soccer}{City, ST}{Captain}{2024}
      \resumeItem{One}
\end{document}
"""


def test_count_bullets_parses_sections_and_entries():
    assert cr.count_bullets(TEX) == [
        ("Education", "Some University", 0),
        ("Experience", "Data Analyst Intern", 3),
        ("Experience", "Cashier", 1),
        ("Projects", "Ledger - Tracker Python", 3),
        ("Leadership & Involvement", "Chess Club", 2),
        ("Activities", "Intramural Soccer", 1),
    ]


def test_default_rules_flag_wrong_counts_and_skip_unruled_sections():
    table = cr.evaluate_counts(cr.count_bullets(TEX), cr.load_count_rules())
    assert [(entry, have, want, ok) for _, entry, have, want, ok in table] == [
        ("Data Analyst Intern", 3, 3, True),
        ("Cashier", 1, 3, False),
        ("Ledger - Tracker Python", 3, 3, True),
        ("Chess Club", 2, 2, True),
        ("Intramural Soccer", 1, 2, False),
    ]


def test_json_override_changes_sections_and_entries(tmp_path):
    path = tmp_path / "bullet_counts.json"
    path.write_text(json.dumps({"sections": {"Activities": 1, "Projects": 4},
                                "entries": {"cashier": 1}}), encoding="utf-8")
    rules = cr.load_count_rules(str(path))
    assert rules["sections"]["Experience"] == 3          # defaults survive
    table = {entry: (want, ok) for _, entry, _, want, ok in
             cr.evaluate_counts(cr.count_bullets(TEX), rules)}
    assert table["Cashier"] == (1, True)                 # entry prefix, case-insensitive
    assert table["Intramural Soccer"] == (1, True)       # section override
    assert table["Ledger - Tracker Python"] == (4, False)
    assert table["Data Analyst Intern"] == (3, True)


def test_entry_override_beats_section_rule():
    rules = {"sections": {"Experience": 3}, "entries": {"Data Analyst": 5}}
    assert cr.expected_count("Experience", "Data Analyst Intern", rules) == 5
    assert cr.expected_count("Experience", "Cashier", rules) == 3
    assert cr.expected_count("Skills", "Anything", rules) is None


# ---------------------------------------------------------------- bad characters
def test_bad_chars_counts_each_kind():
    assert cr.find_bad_chars("plain resume text") == {"replacement": 0, "unmapped": 0, "combining": 0}
    assert cr.find_bad_chars("bad � glyph �")["replacement"] == 2
    assert cr.find_bad_chars("résumé and café")["combining"] == 3
    assert cr.find_bad_chars("(cid:136) A bullet")["unmapped"] == 1


def _page(text, bitmap=0):
    return {"width": 612, "height": 792, "rules": [], "bitmap_glyphs": bitmap,
            "lines": [cr.Line(1, 72, 300, 700, 710, [(72, text)])]}


def test_check_bad_chars_statuses():
    assert cr.check_bad_chars([_page("resume")]).status == cr.PASS
    assert cr.check_bad_chars([_page("résumé")]).status == cr.WARN
    assert cr.check_bad_chars([_page("r�sum�")]).status == cr.FAIL
    assert cr.check_bad_chars([_page("(cid:15)")]).status == cr.FAIL
    assert cr.check_bad_chars([_page("resume", bitmap=2)]).status == cr.WARN


# ---------------------------------------------------------------- fill math
def bullet_line(y, last_x1, left=60.0):
    return cr.Line(1, 50.0, last_x1, y, y + 10, [(50.0, "•"), (left, "Built"), (90.0, "things")])


def wrapped_line(y, x1, left=60.0):
    return cr.Line(1, left, x1, y, y + 10, [(left, "and"), (80.0, "more")])


def test_fill_ratio_and_classification():
    assert cr.fill_ratio(530.0, 60.0, 560.0) == pytest.approx(0.94)
    assert cr.fill_ratio(100.0, 60.0, 60.0) == 0.0
    assert cr.classify_fill(0.9194) == "low"       # judged on the printed figure, 91.9%
    assert cr.classify_fill(0.92) == "ok"
    assert cr.classify_fill(0.999) == "ok"
    assert cr.classify_fill(1.0) == "over"
    assert cr.classify_fill(1.02) == "over"


def test_find_bullets_groups_wrapped_lines_and_stops_at_other_text():
    lines = [
        cr.Line(1, 40, 200, 720, 732, [(40, "Experience")]),
        bullet_line(700, 560.0),                # bullet 1, wraps...
        wrapped_line(688, 300.0),               # ...onto a second line at the text-left
        bullet_line(676, 530.0),                # bullet 2, one line
        cr.Line(1, 40, 300, 660, 672, [(40, "Next"), (70, "Heading")]),
        wrapped_line(648, 400.0),               # same x as bullet text, but no open bullet
        cr.Line(1, 50, 400, 630, 640, [(50, "-"), (60, "Dash"), (90, "bullet")]),
        cr.Line(1, 50, 55, 610, 620, [(50, "•")]),   # a lone glyph is not a bullet
    ]
    bullets = cr.find_bullets(lines)
    assert [len(b.lines) for b in bullets] == [2, 1, 1]
    assert bullets[0].text == "Built things and more"
    assert bullets[0].last_x1 == 300.0 and bullets[0].left == 60.0
    assert cr.first_word(bullets[2].text) == "dash"


def test_wrapped_line_on_another_page_or_far_below_is_not_joined():
    far = cr.find_bullets([bullet_line(700, 560.0), wrapped_line(640, 300.0)])
    assert len(far[0].lines) == 1
    other = wrapped_line(688, 300.0)
    other.page = 2
    assert len(cr.find_bullets([bullet_line(700, 560.0), other])[0].lines) == 1


def test_check_fill_reports_low_and_overfull_bullets():
    bullets = cr.find_bullets([bullet_line(700, 530.0), bullet_line(688, 400.0), bullet_line(676, 561.0)])
    result = cr.check_fill(bullets, 560.0, "--right")
    assert result.status == cr.FAIL
    assert [b["state"] for b in result.data["bullets"]] == ["ok", "low", "over"]
    assert [b["fill"] for b in result.data["bullets"]] == [94.0, 68.0, 100.2]
    assert len(result.details) == 2 and result.details[0].startswith("LOW")
    assert cr.check_fill(bullets[:1], 560.0, "--right").status == cr.PASS


def test_right_edge_prefers_full_width_rule_over_text():
    page = {"width": 612, "height": 792, "lines": [bullet_line(700, 570.0)],
            "rules": [(28.8, 583.2, 650.0), (100.0, 200.0, 600.0)]}
    assert cr.detect_right_edge([page]) == (583.2, "section rule")
    page["rules"] = [(100.0, 200.0, 600.0)]         # only a short underline left
    assert cr.detect_right_edge([page]) == (570.0, "widest text line")


def test_group_lines_attaches_small_raised_bullet_and_splits_words():
    glyphs = [(50, 703, 53, 708, "•")]                              # tiny, raised dot
    glyphs += [(60 + 5 * i, 700, 65 + 5 * i, 710, c) for i, c in enumerate("Built")]
    glyphs += [(90 + 5 * i, 700, 95 + 5 * i, 710, c) for i, c in enumerate("it")]
    glyphs += [(60 + 5 * i, 688, 65 + 5 * i, 698, c) for i, c in enumerate("next")]
    lines = cr.group_lines(glyphs)
    assert [l.text for l in lines] == ["• Built it", "next"]
    assert lines[0].words[1] == (60, "Built") and lines[0].x1 == 100


# ---------------------------------------------------------------- bottom gap
@pytest.mark.parametrize("inches, letter, status", [
    (0.27, False, "PASS"), (0.20, False, "PASS"), (0.35, False, "PASS"),
    (0.10, False, "WARN"), (0.45, False, "WARN"), (0.61, False, "FAIL"),
    (1.10, True, "PASS"), (0.50, True, "WARN"), (2.00, True, "WARN"),
])
def test_classify_gap(inches, letter, status):
    assert cr.classify_gap(inches, letter) == status
