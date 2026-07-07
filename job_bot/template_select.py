"""Map a career field to the résumé template/renderer that fits it.

Tech/CS-track fields render via the RenderCV engineering theme (Typst PDF — the
``engineeringresumes`` theme in ``render_rendercv.py``); every other field keeps
the VMH/business ``docx`` renderer (``render_docx``/``render_pdf``) that John has
historically submitted. Fields come from ``applications.classify_field``.
"""

from __future__ import annotations

# Fields that should render on the CS/tech (RenderCV/engineering) template.
TECH_FIELDS = {"Data & Analytics", "Software / Engineering"}

# NOTE: "IT Audit / Tech Risk" is deliberately treated as business/VMH by
# default — it's still an audit/risk-track role at accounting-style firms, not a
# SWE/CS résumé. Move it into TECH_FIELDS if John wants IT-audit applications on
# the engineering template instead.


def renderer_for_field(field: str) -> str:
    """Renderer key for a career field: ``'rendercv'`` (CS/tech template) or
    ``'docx'`` (VMH/business template)."""
    return "rendercv" if field in TECH_FIELDS else "docx"
