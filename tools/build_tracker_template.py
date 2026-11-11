"""Build templates/tracker_template.xlsx, the blank application tracker.

Maintainers only: users never run this. It needs openpyxl
(`pip install openpyxl`). The workbook is uploaded to Google Drive during
setup, where it becomes the user's own Google Sheet.

Layout (the coach's instructions in rules/tracker_sheet.md depend on it):

  Tracker   summary boxes in rows 3-13, column headers in row 15, data from row 16
  Outreach  headers in row 1, data from row 2
  Setup     the lists behind the dropdowns (tracks, statuses)

Run from the repo root:  python tools/build_tracker_template.py
"""
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

OUT = Path(__file__).resolve().parent.parent / "templates" / "tracker_template.xlsx"

HEADER_ROW = 15
FIRST = HEADER_ROW + 1
LAST = 1000

COLUMNS = [  # (header, width)
    ("Company", 26), ("Position", 44), ("Date Applied", 13), ("Application Status", 18),
    ("Details", 52), ("Applicant Portal", 34), ("Cold Apply", 11), ("Location", 22),
    ("Salary (posted)", 20), ("Work Mode", 16), ("Grad Date Used", 15), ("Deadline", 12),
    ("Track", 16),
]
STATUSES = ["Submitted", "Rejected", "In Progress", "Interviewing", "Offer", "Ghosted", "Withdrawn"]
STATUS_FILL = {
    "Submitted": "DCE9F9", "In Progress": "FFF2CC", "Interviewing": "E4DFEC",
    "Offer": "D9EAD3", "Rejected": "F4CCCC", "Ghosted": "E7E6E6", "Withdrawn": "EFEFEF",
}
TRACK_SLOTS = 8
OUTREACH = [
    ("Contact", 24), ("Company", 20), ("Email", 28), ("LinkedIn", 34), ("Email source", 22),
    ("Email verification", 17), ("Target role / requisition", 30), ("Status", 14),
    ("Planned send date", 16), ("Sent date", 12), ("Follow-up date", 14), ("Subject", 30),
    ("Email draft", 50), ("Reply / outcome", 34), ("Next action", 34), ("Notes", 40),
]
OUTREACH_STATUS = ["Planned", "Drafted", "Sent", "Replied", "Follow-up due", "Closed"]

NAVY = "1F3864"
WHITE_BOLD = Font(bold=True, color="FFFFFF")
HEAD_FILL = PatternFill("solid", fgColor=NAVY)
BOX_FILL = PatternFill("solid", fgColor="F3F6FA")
THIN = Side(style="thin", color="C9D1DC")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def rng(col: str) -> str:
    return f"${col}${FIRST}:${col}${LAST}"


def header(ws, row, names):
    for i, (name, width) in enumerate(names, start=1):
        c = ws.cell(row=row, column=i, value=name)
        c.font, c.fill = WHITE_BOLD, HEAD_FILL
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.column_dimensions[c.column_letter].width = width
    ws.row_dimensions[row].height = 30


def box(ws, top_left, rows):
    """Write a small label/value box and outline it."""
    col = top_left[0]
    r0 = int(top_left[1:])
    nxt = chr(ord(col) + 1)
    for i, (label, value, bold) in enumerate(rows):
        a, b = ws[f"{col}{r0 + i}"], ws[f"{nxt}{r0 + i}"]
        a.value, b.value = label, value
        for c in (a, b):
            c.border, c.fill = BOX, BOX_FILL
            c.font = Font(bold=bold)
        b.alignment = Alignment(horizontal="center")


def build() -> Path:
    wb = Workbook()

    # ---- Setup: lists behind the dropdowns --------------------------------
    setup = wb.active
    setup.title = "Setup"
    setup["A1"], setup["B1"], setup["D1"] = "Tracks", "Statuses", "How this sheet works"
    for c in ("A1", "B1", "D1"):
        setup[c].font, setup[c].fill = WHITE_BOLD, HEAD_FILL
    for i, s in enumerate(STATUSES, start=2):
        setup[f"B{i}"] = s
    notes = [
        "Tracks: the kinds of role you are applying to (for example Consulting, Data, Software).",
        f"Type up to {TRACK_SLOTS} of them in A2:A{TRACK_SLOTS + 1}. They fill the Track dropdown and the By Track box.",
        "Statuses: the Application Status dropdown. Leave these as they are; the coach reads them.",
        "Tracker tab: one row per application. Column headers are in row 15; do not move them.",
        "Outreach tab: one row per person you plan to contact.",
        "Your coach reads this sheet before every check-in and adds a row when you apply.",
    ]
    for i, n in enumerate(notes, start=2):
        setup[f"D{i}"] = n
    setup.column_dimensions["A"].width = 24
    setup.column_dimensions["B"].width = 18
    setup.column_dimensions["D"].width = 100

    # ---- Tracker ----------------------------------------------------------
    ws = wb.create_sheet("Tracker", 0)
    ws.merge_cells("A3:B4")
    ws["A3"] = "Job Tracker"
    ws["A3"].font = Font(bold=True, size=20, color=NAVY)
    ws["A3"].alignment = Alignment(vertical="center")

    d = rng("D")
    box(ws, "A6", [("Key", "Count", True)] + [
        (s, f'=COUNTIF({d},A{7 + i})', False) for i, s in enumerate(STATUSES)
    ])
    box(ws, "D3", [
        ("At a Glance", None, True),
        ("Total applications", f"=COUNTA({rng('A')})", False),
        ("Applied in the last 7 days", f'=COUNTIF({rng("C")},">="&(TODAY()-7))', False),
        ("Last applied", f'=IF(COUNT({rng("C")})=0,"",MAX({rng("C")}))', False),
        ("Heard back",
         f'=COUNTIF({d},"Interviewing")+COUNTIF({d},"Offer")+COUNTIF({d},"Rejected")', False),
    ])
    ws["E6"].number_format = "m/d/yy"
    box(ws, "H3", [("By Track", "Apps", True)] + [
        (f'=IF(Setup!A{2 + i}="","",Setup!A{2 + i})',
         f'=IF(Setup!A{2 + i}="","",COUNTIF({rng("M")},Setup!A{2 + i}))', False)
        for i in range(TRACK_SLOTS)
    ])

    header(ws, HEADER_ROW, COLUMNS)
    ws.freeze_panes = f"A{FIRST}"
    ws.auto_filter.ref = f"A{HEADER_ROW}:M{LAST}"

    for col in ("C", "L"):
        for r in range(FIRST, LAST + 1):
            ws[f"{col}{r}"].number_format = "m/d/yy"
    for col in ("B", "E"):
        for r in range(FIRST, 201):
            ws[f"{col}{r}"].alignment = Alignment(wrap_text=True, vertical="top")

    status_dv = DataValidation(type="list", formula1=f"=Setup!$B$2:$B${1 + len(STATUSES)}", allow_blank=True)
    cold_dv = DataValidation(type="list", formula1='"Yes,No"', allow_blank=True)
    track_dv = DataValidation(type="list", formula1=f"=Setup!$A$2:$A${1 + TRACK_SLOTS}", allow_blank=True)
    for dv, col in ((status_dv, "D"), (cold_dv, "G"), (track_dv, "M")):
        dv.showErrorMessage = True
        ws.add_data_validation(dv)
        dv.add(f"{col}{FIRST}:{col}{LAST}")

    for status, color in STATUS_FILL.items():
        ws.conditional_formatting.add(
            f"D{FIRST}:D{LAST}",
            CellIsRule(operator="equal", formula=[f'"{status}"'], fill=PatternFill("solid", bgColor=color, fgColor=color)),
        )

    # ---- Outreach ---------------------------------------------------------
    out = wb.create_sheet("Outreach", 1)
    header(out, 1, OUTREACH)
    out.freeze_panes = "A2"
    st = DataValidation(type="list", formula1='"' + ",".join(OUTREACH_STATUS) + '"', allow_blank=True)
    ver = DataValidation(type="list", formula1='"Verified,Unverified"', allow_blank=True)
    out.add_data_validation(st)
    out.add_data_validation(ver)
    st.add("H2:H500")
    ver.add("F2:F500")
    for col in ("I", "J", "K"):
        for r in range(2, 501):
            out[f"{col}{r}"].number_format = "m/d/yy"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)
    return OUT


if __name__ == "__main__":
    print(build())
