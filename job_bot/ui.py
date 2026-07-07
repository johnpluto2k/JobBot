"""Design system for the Job Bot dashboard.

A small, dependency-free component layer that gives the Streamlit app a modern,
minimal SaaS look (Linear / Stripe / Ramp family): an Inter type system, a soft
off-white canvas with a restrained gradient glow, white cards with hover lift,
status-accented KPI cards, a pipeline funnel, grouped notification cards, and
friendly empty states.

Everything here renders through Streamlit's HTML support — no extra packages,
no React. Functions return HTML strings (render with ``st.markdown(..,
unsafe_allow_html=True)``) or, where a native widget is needed, draw directly.

Limits worth knowing (Streamlit, not laziness): no JS, so number counters and
drag-and-drop aren't available; entrance motion is CSS-only and GPU-friendly.
"""

from __future__ import annotations

from datetime import datetime
from html import escape

import streamlit as st

# --- Palette ------------------------------------------------------------------
ACCENT = "#4F46E5"
INK = "#15181D"
MUTED = "#6B7280"
LINE = "#ECEEF1"
SURFACE = "#FAFBFC"

# Status accents — subtle, never harsh. (text color, soft tint background)
STATUS_COLORS = {
    "blue":   ("#2563EB", "#EEF3FF"),
    "violet": ("#7C3AED", "#F3EEFF"),
    "red":    ("#D9536A", "#FCEEF0"),
    "amber":  ("#C2710C", "#FCF1E2"),
    "green":  ("#0F9D6E", "#E7F7F0"),
    "slate":  ("#475569", "#EEF1F5"),
}

# --- Icons (Lucide-style, stroke-based, consistent 1.75 width) ----------------
_I = ('<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" '
      'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
      'stroke-linecap="round" stroke-linejoin="round">{}</svg>')
ICONS = {
    "briefcase": _I.format('<rect width="20" height="14" x="2" y="7" rx="2"/>'
                           '<path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>'),
    "video":     _I.format('<path d="m22 8-6 4 6 4V8Z"/>'
                           '<rect width="14" height="12" x="2" y="6" rx="2"/>'),
    "x-circle":  _I.format('<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/>'
                           '<path d="m9 9 6 6"/>'),
    "clock":     _I.format('<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>'),
    "gift":      _I.format('<rect x="3" y="8" width="18" height="4" rx="1"/>'
                           '<path d="M12 8v13M19 12v7a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-7"/>'
                           '<path d="M7.5 8a2.5 2.5 0 0 1 0-5C11 3 12 8 12 8M16.5 8a2.5 2.5 0 0 0 0-5C13 3 12 8 12 8"/>'),
    "calendar":  _I.format('<path d="M8 2v4M16 2v4"/><rect width="18" height="18" x="3" y="4" rx="2"/>'
                           '<path d="M3 10h18"/>'),
    "mail":      _I.format('<rect width="20" height="16" x="2" y="4" rx="2"/>'
                           '<path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>'),
    "inbox":     _I.format('<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/>'
                           '<path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>'),
    "flame":     _I.format('<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/>'),
    "trending":  _I.format('<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/>'
                           '<polyline points="16 7 22 7 22 13"/>'),
    "users":     _I.format('<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/>'
                           '<circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/>'
                           '<path d="M16 3.13a4 4 0 0 1 0 7.75"/>'),
    "check":     _I.format('<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="m9 11 3 3L22 4"/>'),
    "arrow":     _I.format('<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>'),
    "sparkle":   _I.format('<path d="M12 3v4M12 17v4M3 12h4M17 12h4"/>'
                           '<path d="M12 8a4 4 0 0 0 4 4 4 4 0 0 0-4 4 4 4 0 0 0-4-4 4 4 0 0 0 4-4z"/>'),
}


def inject_css() -> None:
    """Inject the global stylesheet. Call once, right after set_page_config."""
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root{
  --jb-accent:#4F46E5; --jb-accent-2:#7C3AED;
  --jb-ink:#15181D; --jb-muted:#6B7280; --jb-line:#ECEEF1; --jb-surface:#FAFBFC;
}

html,body,[class*="css"],.stApp,button,input,textarea,select,
[data-testid="stMarkdownContainer"]{
  font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif !important;
  -webkit-font-smoothing:antialiased;
}

/* Soft off-white canvas with an understated gradient glow */
.stApp{
  background:
    radial-gradient(900px 420px at 88% -8%, rgba(124,58,237,.07), transparent 60%),
    radial-gradient(760px 380px at 6% 2%, rgba(79,70,229,.06), transparent 55%),
    #F6F7F9;
  background-attachment:fixed;
}
.block-container{padding-top:2rem; padding-bottom:4rem; max-width:1240px;}

/* Type hierarchy */
h1,h2,h3,h4{letter-spacing:-.018em; color:var(--jb-ink);}
h1{font-weight:800; font-size:1.7rem !important;}
h2{font-weight:700; font-size:1.18rem !important;}
h3{font-weight:600; font-size:1rem !important;}
[data-testid="stMarkdownContainer"] h4{
  font-weight:600; font-size:.78rem !important; text-transform:uppercase;
  letter-spacing:.07em; color:var(--jb-muted); margin:.3rem 0 .2rem;
}
[data-testid="stCaptionContainer"]{color:var(--jb-muted);}

/* ---- Entrance motion (GPU-friendly, respects reduced-motion) ---- */
@keyframes jbUp{from{opacity:0; transform:translateY(8px);} to{opacity:1; transform:none;}}
.jb-anim{animation:jbUp .42s cubic-bezier(.22,.61,.36,1) both;}

/* ---- Hero ---- */
.jb-hero{position:relative; overflow:hidden; border:1px solid var(--jb-line);
  border-radius:20px; padding:1.6rem 1.8rem;
  background:linear-gradient(135deg,#fff 0%,#FCFBFF 100%);
  box-shadow:0 1px 2px rgba(16,24,40,.04);}
.jb-hero-glow{position:absolute; inset:-40% -10% auto auto; width:380px; height:380px;
  background:radial-gradient(circle,rgba(124,58,237,.18),transparent 62%); pointer-events:none;}
.jb-hero-row{position:relative; display:flex; justify-content:space-between;
  align-items:center; gap:1rem; flex-wrap:wrap;}
.jb-hero-title{font-size:1.55rem; font-weight:800; letter-spacing:-.02em; color:var(--jb-ink);}
.jb-hero-sub{color:var(--jb-muted); margin-top:.25rem; font-size:.96rem;}
.jb-hero-stats{display:flex; gap:.6rem; flex-wrap:wrap;}
.jb-pill{background:#fff; border:1px solid var(--jb-line); border-radius:12px;
  padding:.5rem .85rem; text-align:center; min-width:92px;}
.jb-pill b{display:block; font-size:1.15rem; font-weight:800; color:var(--jb-ink);
  font-variant-numeric:tabular-nums;}
.jb-pill span{font-size:.72rem; color:var(--jb-muted); text-transform:uppercase; letter-spacing:.04em;}

/* ---- KPI cards ---- */
.jb-kpi-grid{display:grid; grid-template-columns:repeat(5,1fr); gap:.85rem; margin:.2rem 0 .4rem;}
.jb-kpi{background:#fff; border:1px solid var(--jb-line); border-radius:16px; padding:1rem 1.05rem;
  box-shadow:0 1px 2px rgba(16,24,40,.04); transition:transform .18s ease, box-shadow .18s ease;}
.jb-kpi:hover{transform:translateY(-3px); box-shadow:0 12px 26px rgba(16,24,40,.10);}
.jb-kpi-top{display:flex; align-items:center; justify-content:space-between; margin-bottom:.7rem;}
.jb-chip{width:38px; height:38px; border-radius:11px; display:flex; align-items:center; justify-content:center;}
.jb-delta{font-size:.74rem; font-weight:600; padding:.12rem .45rem; border-radius:8px;}
.jb-kpi-val{font-size:1.85rem; font-weight:800; color:var(--jb-ink); line-height:1;
  font-variant-numeric:tabular-nums;}
.jb-kpi-lbl{font-size:.78rem; color:var(--jb-muted); margin-top:.35rem; font-weight:500;}
.jb-kpi-sub{font-size:.72rem; color:var(--jb-muted); margin-top:.2rem;}

/* ---- Section header ---- */
.jb-sec{display:flex; align-items:center; gap:.55rem; margin:1.4rem 0 .7rem;}
.jb-sec .jb-ic{color:var(--jb-accent); display:flex;}
.jb-sec h3{margin:0; font-size:.98rem; font-weight:700; color:var(--jb-ink);}
.jb-sec .jb-count{font-size:.72rem; color:var(--jb-muted); background:var(--jb-surface);
  border:1px solid var(--jb-line); border-radius:999px; padding:.1rem .5rem;}

/* ---- Pipeline funnel ---- */
.jb-funnel{display:flex; align-items:stretch; gap:.5rem; flex-wrap:wrap;
  background:#fff; border:1px solid var(--jb-line); border-radius:16px; padding:1.1rem 1.2rem;
  box-shadow:0 1px 2px rgba(16,24,40,.04);}
.jb-stage{flex:1; min-width:120px; text-align:center; padding:.4rem .2rem;}
.jb-stage-bar{height:6px; border-radius:999px; margin:0 auto .6rem; background:var(--jb-line);}
.jb-stage-n{font-size:1.5rem; font-weight:800; color:var(--jb-ink); font-variant-numeric:tabular-nums;}
.jb-stage-l{font-size:.76rem; color:var(--jb-muted); margin-top:.1rem; text-transform:uppercase; letter-spacing:.04em;}
.jb-conv{display:flex; flex-direction:column; align-items:center; justify-content:center;
  color:var(--jb-muted); font-size:.72rem; min-width:46px;}
.jb-conv b{color:var(--jb-ink); font-size:.86rem; font-weight:700;}

/* ---- Notification / list cards ---- */
.jb-card{background:#fff; border:1px solid var(--jb-line); border-radius:14px; padding:.85rem 1rem;
  margin-bottom:.6rem; box-shadow:0 1px 2px rgba(16,24,40,.04);
  transition:transform .16s ease, box-shadow .16s ease, border-color .16s ease;}
.jb-card:hover{transform:translateY(-2px); box-shadow:0 10px 22px rgba(16,24,40,.09); border-color:#E0E2E8;}
.jb-card-row{display:flex; align-items:center; gap:.75rem;}
.jb-avatar{width:40px; height:40px; border-radius:11px; flex:none; display:flex; align-items:center;
  justify-content:center; font-weight:700; font-size:.9rem; color:#fff; letter-spacing:-.01em;}
.jb-card-main{flex:1; min-width:0;}
.jb-card-title{font-weight:600; color:var(--jb-ink); font-size:.92rem; display:flex;
  align-items:center; gap:.5rem;}
.jb-card-sub{color:var(--jb-muted); font-size:.8rem; margin-top:.15rem; overflow:hidden;
  text-overflow:ellipsis; white-space:nowrap;}
.jb-badge{font-size:.68rem; font-weight:600; padding:.12rem .5rem; border-radius:999px; white-space:nowrap;}
.jb-date{font-size:.74rem; color:var(--jb-muted); white-space:nowrap;}

/* ---- Empty state ---- */
.jb-empty{background:#fff; border:1px dashed #DfE2E8; border-radius:14px; padding:1.6rem 1rem;
  text-align:center;}
.jb-empty-ic{width:44px; height:44px; border-radius:12px; margin:0 auto .6rem; display:flex;
  align-items:center; justify-content:center; background:var(--jb-surface); color:var(--jb-muted);}
.jb-empty-t{font-weight:600; color:var(--jb-ink); font-size:.92rem;}
.jb-empty-b{color:var(--jb-muted); font-size:.82rem; margin-top:.25rem;}

/* ---- Tabs ---- */
.stTabs [data-baseweb="tab-list"]{gap:.3rem; border-bottom:1px solid var(--jb-line);}
.stTabs [data-baseweb="tab"]{height:42px; padding:0 .8rem; color:var(--jb-muted);
  font-size:.86rem; font-weight:500; border-radius:9px 9px 0 0; transition:color .15s, background .15s;}
.stTabs [data-baseweb="tab"]:hover{color:var(--jb-ink); background:var(--jb-surface);}
.stTabs [aria-selected="true"]{color:var(--jb-accent) !important;}
.stTabs [data-baseweb="tab-highlight"]{background:var(--jb-accent);}

/* ---- Buttons / inputs / tables ---- */
.stButton button[kind="primary"]{border-radius:10px; font-weight:600; border:none;
  background:linear-gradient(135deg,#4F46E5,#6D5BF0); box-shadow:0 1px 2px rgba(79,70,229,.25);
  transition:filter .16s ease, transform .12s ease;}
.stButton button[kind="primary"]:hover{filter:brightness(1.06); transform:translateY(-1px);}
.stButton button[kind="primary"]:active{transform:translateY(0);}
.stButton button[kind="secondary"]{border-radius:10px; border-color:var(--jb-line);}
[data-testid="stDataFrame"]{border:1px solid var(--jb-line); border-radius:12px; overflow:hidden;}
.stTextInput input,.stTextArea textarea,.stNumberInput input{border-radius:9px !important;}
[data-testid="stExpander"]{border:1px solid var(--jb-line); border-radius:12px;}
hr{margin:1.5rem 0; border-color:var(--jb-line);}

/* ---- Sidebar ---- */
[data-testid="stSidebar"]{background:#fff; border-right:1px solid var(--jb-line);}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"]{font-size:.82rem;}

/* ---- Avatar ---- */
.jb-av{border-radius:50%; display:flex; align-items:center; justify-content:center;
  color:#fff; font-weight:700; flex:none; letter-spacing:-.01em; background-size:cover;
  background-position:center; box-shadow:0 2px 8px rgba(16,24,40,.18); border:2px solid #fff;}
.jb-av-initials{background:linear-gradient(135deg,var(--jb-accent),var(--jb-accent-2));}

/* ---- App header bar (persistent title + corner avatar) ---- */
.jb-appbar{display:flex; align-items:center; justify-content:space-between; gap:1rem; margin:0 0 .1rem;}
.jb-appbar-title{font-size:1.7rem; font-weight:800; letter-spacing:-.02em; color:var(--jb-ink); line-height:1.1;}
.jb-appbar-sub{color:var(--jb-muted); font-size:.9rem; margin-top:.25rem;}
.jb-appbar-sub a{color:var(--jb-muted); text-decoration:none; border-bottom:1px solid var(--jb-line);}
.jb-appbar-sub a:hover{color:var(--jb-accent);}
.jb-appbar-r{flex:none; transition:transform .18s ease;}
.jb-appbar-r:hover{transform:translateY(-2px) scale(1.03);}

/* ---- Personal card (Overview) ---- */
.jb-person{display:flex; align-items:center; gap:1.1rem; padding:1.15rem 1.25rem;}
.jb-person-name{font-size:1.2rem; font-weight:700; color:var(--jb-ink); letter-spacing:-.01em;}
.jb-person-role{color:var(--jb-accent); font-weight:600; font-size:.86rem; margin-top:.12rem;}
.jb-person-meta{color:var(--jb-muted); font-size:.82rem; margin-top:.5rem; display:flex;
  flex-wrap:wrap; gap:.35rem .55rem; align-items:center;}
.jb-person-meta a{color:var(--jb-muted); text-decoration:none; border-bottom:1px solid var(--jb-line);}
.jb-person-meta a:hover{color:var(--jb-accent);}
.jb-person-sep{color:#CDD2DA;}

/* ---- Job listing cards (Pipeline) ---- */
.jb-job{display:flex; align-items:center; gap:.85rem; padding:.75rem 1rem;}
.jb-job-body{flex:1; min-width:0;}
.jb-job-title{font-weight:650; color:var(--jb-ink); font-size:.92rem; white-space:nowrap;
  overflow:hidden; text-overflow:ellipsis;}
.jb-job-meta{color:var(--jb-muted); font-size:.79rem; margin-top:.18rem; display:flex;
  flex-wrap:wrap; gap:.25rem .5rem; align-items:center;}
.jb-job-meta .dot{color:#CDD2DA;}
.jb-job-stats{font-size:.73rem; color:var(--jb-muted); margin-top:.22rem;
  font-variant-numeric:tabular-nums;}
.jb-job-aside{flex:none; display:flex; flex-direction:column; align-items:flex-end; gap:.32rem;}
.jb-job-flag{margin-top:.55rem; font-size:.76rem; color:#B45309; background:#FCF1E2;
  border:1px solid #F6E2C4; border-radius:8px; padding:.35rem .6rem;}
.jb-link{font-size:.74rem; font-weight:600; color:var(--jb-accent); text-decoration:none;
  border:1px solid var(--jb-line); border-radius:8px; padding:.18rem .55rem; white-space:nowrap;}
.jb-link:hover{background:var(--jb-surface); border-color:#E0E2E8;}
@media (max-width:720px){
  .jb-job{flex-wrap:wrap;}
  .jb-job-aside{flex-direction:row; align-items:center; width:100%; justify-content:flex-start;}
}

/* ---- Responsive ---- */
@media (max-width:1024px){.jb-kpi-grid{grid-template-columns:repeat(2,1fr);}}
@media (max-width:640px){.jb-kpi-grid{grid-template-columns:1fr;} .jb-hero-title{font-size:1.3rem;}}
@media (prefers-reduced-motion:reduce){*{animation:none !important; transition:none !important;}}
</style>
""",
        unsafe_allow_html=True,
    )


# --- Component builders (return HTML) -----------------------------------------
def greeting(now: datetime | None = None) -> str:
    h = (now or datetime.now()).hour
    return "Good morning" if h < 12 else "Good afternoon" if h < 18 else "Good evening"


def hero(name: str, subtitle: str, stats: list[tuple[str, str]]) -> str:
    pills = "".join(
        f'<div class="jb-pill"><b>{escape(v)}</b><span>{escape(l)}</span></div>'
        for v, l in stats
    )
    return (
        f'<div class="jb-hero jb-anim"><div class="jb-hero-glow"></div>'
        f'<div class="jb-hero-row"><div>'
        f'<div class="jb-hero-title">{escape(name)}</div>'
        f'<div class="jb-hero-sub">{escape(subtitle)}</div></div>'
        f'<div class="jb-hero-stats">{pills}</div></div></div>'
    )


def kpi_grid(cards: list[dict]) -> str:
    """cards: list of {label, value, icon, color, sub?, delta?, delta_color?}.

    The grid column count follows the number of cards (2-6) and collapses to
    2-up / 1-up on smaller screens via the stylesheet's media queries.
    """
    n = max(1, min(len(cards), 6))
    out = []
    for i, c in enumerate(cards):
        fg, bg = STATUS_COLORS.get(c.get("color", "slate"), STATUS_COLORS["slate"])
        icon = ICONS.get(c.get("icon", "briefcase"), ICONS["briefcase"])
        chip = (f'<span class="jb-chip" style="color:{fg};background:{bg}">{icon}</span>')
        delta = ""
        if c.get("delta"):
            dfg, dbg = STATUS_COLORS.get(c.get("delta_color", "green"), STATUS_COLORS["green"])
            delta = f'<span class="jb-delta" style="color:{dfg};background:{dbg}">{escape(c["delta"])}</span>'
        sub = f'<div class="jb-kpi-sub">{escape(c["sub"])}</div>' if c.get("sub") else ""
        out.append(
            f'<div class="jb-kpi jb-anim" style="animation-delay:{i*45}ms">'
            f'<div class="jb-kpi-top">{chip}{delta}</div>'
            f'<div class="jb-kpi-val">{escape(str(c["value"]))}</div>'
            f'<div class="jb-kpi-lbl">{escape(c["label"])}</div>{sub}</div>'
        )
    return (f'<div class="jb-kpi-grid" style="grid-template-columns:repeat({n},1fr)">'
            f'{"".join(out)}</div>')


def section(title: str, icon: str = "sparkle", count: int | None = None) -> str:
    ic = ICONS.get(icon, ICONS["sparkle"])
    cnt = f'<span class="jb-count">{count}</span>' if count is not None else ""
    return (f'<div class="jb-sec"><span class="jb-ic">{ic}</span>'
            f'<h3>{escape(title)}</h3>{cnt}</div>')


def funnel(stages: list[tuple[str, int]]) -> str:
    """stages: ordered [(label, count)]; shows counts + conversion between them."""
    if not stages:
        return ""
    top = max((n for _, n in stages), default=1) or 1
    grad = ["#4F46E5", "#6D5BF0", "#7C3AED", "#9333EA", "#0F9D6E"]
    parts = []
    for i, (label, n) in enumerate(stages):
        if i:
            prev = stages[i - 1][1] or 1
            conv = round(100 * n / prev)
            parts.append(f'<div class="jb-conv"><b>{conv}%</b>→</div>')
        w = max(18, round(100 * n / top))
        col = grad[min(i, len(grad) - 1)]
        parts.append(
            f'<div class="jb-stage"><div class="jb-stage-bar" '
            f'style="width:{w}%;background:{col}"></div>'
            f'<div class="jb-stage-n">{n}</div>'
            f'<div class="jb-stage-l">{escape(label)}</div></div>'
        )
    return f'<div class="jb-funnel jb-anim">{"".join(parts)}</div>'


def _avatar_color(seed: str) -> str:
    palette = ["#4F46E5", "#7C3AED", "#2563EB", "#0F9D6E", "#C2710C", "#D9536A", "#0E7490"]
    return palette[sum(map(ord, seed)) % len(palette)]


def initials(name: str) -> str:
    parts = [w for w in name.replace("&", " ").split() if w[:1].isalnum()]
    if not parts:
        return "?"
    return (parts[0][0] + (parts[1][0] if len(parts) > 1 else "")).upper()


def avatar(name: str, image_url: str | None = None, size: int = 40) -> str:
    """Circular avatar. Renders the photo when ``image_url`` is given (an http(s)
    URL or a ``data:`` URI), otherwise falls back to initials on an accent
    gradient. No broken-image icon or layout shift when a photo is added later —
    the container size is identical in both states."""
    dim = f"width:{size}px;height:{size}px;"
    if image_url:
        safe = image_url.replace("'", "%27")
        style = dim + f"background-image:url('{safe}');"
        return f'<div class="jb-av" title="{escape(name)}" style="{style}"></div>'
    fs = max(11, round(size * 0.4))
    style = dim + f"font-size:{fs}px;"
    return (f'<div class="jb-av jb-av-initials" title="{escape(name)}" '
            f'style="{style}">{escape(initials(name or "?"))}</div>')


def app_header(title: str, subtitle_html: str, avatar_html: str) -> str:
    """Persistent top bar: title + caption on the left, avatar pinned top-right.
    ``subtitle_html`` is trusted HTML (build it with escaped parts)."""
    return (
        f'<div class="jb-appbar jb-anim"><div>'
        f'<div class="jb-appbar-title">{escape(title)}</div>'
        f'<div class="jb-appbar-sub">{subtitle_html}</div></div>'
        f'<div class="jb-appbar-r">{avatar_html}</div></div>'
    )


def personal_card(name: str, headline: str | None = None, location: str | None = None,
                  email: str | None = None, linkedin: str | None = None,
                  phone: str | None = None, avatar_html: str = "") -> str:
    """A personal-info card for the Overview tab. Missing fields are dropped
    cleanly rather than shown as blanks."""
    meta = []
    if location:
        meta.append(f'<span>{escape(location)}</span>')
    if email:
        meta.append(f'<a href="mailto:{escape(email)}">{escape(email)}</a>')
    if phone:
        meta.append(f'<span>{escape(phone)}</span>')
    if linkedin:
        meta.append(f'<a href="{escape(linkedin)}" target="_blank" rel="noopener">LinkedIn</a>')
    meta_html = '<span class="jb-person-sep">·</span>'.join(meta)
    role = f'<div class="jb-person-role">{escape(headline)}</div>' if headline else ""
    return (
        f'<div class="jb-card jb-person jb-anim"><div>{avatar_html}</div>'
        f'<div class="jb-person-body">'
        f'<div class="jb-person-name">{escape(name)}</div>{role}'
        f'<div class="jb-person-meta">{meta_html}</div></div></div>'
    )


def notif_card(title: str, sub: str, badge: tuple[str, str] | None = None,
               date: str = "", company: str | None = None, delay: int = 0) -> str:
    """A clean notification/list card with initials avatar + optional badge."""
    av_seed = company or title
    avatar = (f'<div class="jb-avatar" style="background:{_avatar_color(av_seed)}">'
              f'{escape(initials(av_seed))}</div>')
    bd = ""
    if badge:
        text, color = badge
        fg, bg = STATUS_COLORS.get(color, STATUS_COLORS["slate"])
        bd = f'<span class="jb-badge" style="color:{fg};background:{bg}">{escape(text)}</span>'
    dt = f'<span class="jb-date">{escape(date)}</span>' if date else ""
    return (
        f'<div class="jb-card jb-anim" style="animation-delay:{delay}ms"><div class="jb-card-row">'
        f'{avatar}<div class="jb-card-main">'
        f'<div class="jb-card-title">{escape(title)}{bd}</div>'
        f'<div class="jb-card-sub">{escape(sub)}</div></div>{dt}</div></div>'
    )


def _badge_color(text: str) -> str:
    """Pick a status color from a recommendation / legitimacy label."""
    t = (text or "").lower()
    if "apply" in t or "likely legit" in t:
        return "green"
    if "maybe" in t:
        return "amber"
    if "verify" in t:
        return "amber" if "verify first" in t else "red"
    if "risk" in t or "high risk" in t:
        return "red"
    if "skip" in t:
        return "slate"
    return "slate"


def _badge(text: str, color: str | None = None) -> str:
    if not text:
        return ""
    fg, bg = STATUS_COLORS.get(color or _badge_color(text), STATUS_COLORS["slate"])
    return f'<span class="jb-badge" style="color:{fg};background:{bg}">{escape(text)}</span>'


def job_card(*, title: str, company: str = "", field: str | None = None,
             tier: str | None = None, location: str | None = None, date: str | None = None,
             priority=None, ats=None, recommendation: str | None = None,
             legit: str | None = None, url: str | None = None, flag: str | None = None,
             level: str | None = None, delay: int = 0) -> str:
    """One full-width job listing — everything visible, no horizontal scroll.

    Left: company-initials avatar. Middle: title, a meta line (company · field ·
    tier · location) and a stats line (priority · ATS · posted). Right: the apply
    gate + legitimacy badges and a View link. A flag line appears only when the
    posting was flagged.
    """
    seed = company or title or "?"
    av = (f'<div class="jb-avatar" style="background:{_avatar_color(seed)}">'
          f'{escape(initials(seed))}</div>')

    meta_bits = [escape(x) for x in (level, company, field, tier, location) if x]
    meta = '<span class="dot">·</span>'.join(meta_bits)

    stats = []
    if priority not in (None, ""):
        stats.append(f'priority <b style="color:var(--jb-ink)">{priority}</b>')
    if ats not in (None, ""):
        stats.append(f'ATS {ats}')
    if date:
        stats.append(f'posted {escape(str(date))}')
    stats_html = '  ·  '.join(stats)

    badges = _badge(recommendation) + _badge(legit)
    link = (f'<a class="jb-link" href="{escape(url)}" target="_blank" rel="noopener">View ↗</a>'
            if url else "")
    aside = f'<div class="jb-job-aside">{badges}{link}</div>' if (badges or link) else ""

    flag_html = (f'<div class="jb-job-flag">⚠️ {escape(flag)}</div>'
                 if flag and flag.lower() not in ("", "no scam or ghost-job signals found.") else "")

    return (
        f'<div class="jb-card jb-anim" style="animation-delay:{delay}ms">'
        f'<div class="jb-job">{av}'
        f'<div class="jb-job-body">'
        f'<div class="jb-job-title">{escape(title or "Untitled role")}</div>'
        f'<div class="jb-job-meta">{meta}</div>'
        f'<div class="jb-job-stats">{stats_html}</div></div>'
        f'{aside}</div>{flag_html}</div>'
    )


def empty_state(title: str, body: str, icon: str = "inbox") -> str:
    ic = ICONS.get(icon, ICONS["inbox"])
    return (f'<div class="jb-empty jb-anim"><div class="jb-empty-ic">{ic}</div>'
            f'<div class="jb-empty-t">{escape(title)}</div>'
            f'<div class="jb-empty-b">{escape(body)}</div></div>')


def html(markup: str) -> None:
    """Render a component HTML string."""
    st.markdown(markup, unsafe_allow_html=True)
