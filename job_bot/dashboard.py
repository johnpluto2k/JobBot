"""Phase 9: Streamlit control-center dashboard.

Run with:
    streamlit run job_bot/dashboard.py
    (or)  python -m streamlit run job_bot/dashboard.py

Surfaces everything the system tracks: profile, job pipeline (ranked by
priority), network/connections, outreach follow-ups, decision log, and an
interactive "score a JD" tool that runs Phases 2–3 live.
"""

from __future__ import annotations

import base64
import html
import json
import mimetypes
import sqlite3
import sys
from pathlib import Path

# `streamlit run job_bot/dashboard.py` puts this file's own folder (job_bot/) on
# sys.path, not the project root — so `import job_bot` fails. Add the project
# root (this file's parent's parent) so the package is importable either way.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pandas as pd
import streamlit as st

from job_bot import config, ui
from job_bot.db import DB_PATH, connect

st.set_page_config(
    page_title="Job Bot — Career OS",
    layout="wide",
    page_icon=":material/dashboard:",
    initial_sidebar_state="expanded",
)

# Global design system (Inter, soft canvas, cards, funnel, refined widgets).
ui.inject_css()


@st.cache_data(show_spinner=False)
def _load_profile() -> dict | None:
    if config.PROFILE_JSON.exists():
        return json.loads(config.PROFILE_JSON.read_text(encoding="utf-8"))
    return None


def _df(query: str) -> pd.DataFrame:
    if not DB_PATH.exists():
        return pd.DataFrame()
    con = connect()
    try:
        return pd.read_sql_query(query, con)
    except Exception:
        return pd.DataFrame()
    finally:
        con.close()


@st.cache_data(show_spinner=False)
def _avatar_src(personal: dict) -> str | None:
    """Resolve a profile photo to a value <img>/CSS can use, or None.

    Swap-in points, in priority order:
      1. personal["photo_url"] / personal["photo"] as an http(s) or data URI
      2. a local file path in that same field
      3. a conventional file at data/profile_photo.{png,jpg,jpeg,webp}
    Local files are inlined as base64 data URIs so Streamlit can serve them.
    Drop a photo at data/profile_photo.jpg (or add personal.photo_url to the
    profile JSON) and it appears automatically — no code change needed.
    """
    ref = str(personal.get("photo_url") or personal.get("photo") or "").strip()
    if ref.startswith(("http://", "https://", "data:")):
        return ref
    candidates = []
    if ref:
        candidates += [Path(ref), config.OUTPUT_DIR / ref]
    for ext in ("png", "jpg", "jpeg", "webp"):
        candidates.append(config.OUTPUT_DIR / f"profile_photo.{ext}")
    for path in candidates:
        try:
            if path and path.is_file():
                mime = mimetypes.guess_type(str(path))[0] or "image/jpeg"
                data = base64.b64encode(path.read_bytes()).decode("ascii")
                return f"data:{mime};base64,{data}"
        except Exception:
            continue
    return None


profile = _load_profile()

if profile is None:
    st.title("Job Bot")
    st.warning("No master profile found. Run `python -m job_bot.build_profile` first.")
    st.stop()

p = profile.get("personal", {})
_photo = _avatar_src(p)
_bits = ["Career Operating System"]
if p.get("name"):
    _bits.append(html.escape(str(p["name"])))
if p.get("email"):
    _e = html.escape(str(p["email"]))
    _bits.append(f'<a href="mailto:{_e}">{_e}</a>')
if p.get("location"):
    _bits.append(html.escape(str(p["location"])))
ui.html(ui.app_header("Job Bot", "  ·  ".join(_bits),
                      ui.avatar(str(p.get("name") or "?"), _photo, size=46)))
st.write("")

(tab_home, tab_apps, tab_over, tab_growth, tab_find, tab_pipe, tab_net, tab_offers,
 tab_tool, tab_brief, tab_li, tab_lab, tab_resume) = st.tabs(
    [":material/bolt: Action Center", ":material/fact_check: Applications",
     ":material/person: Overview", ":material/trending_up: Growth Plan",
     ":material/travel_explore: Find Jobs",
     ":material/view_list: Pipeline", ":material/group: Network",
     ":material/payments: Offers", ":material/insights: Score a JD",
     ":material/business_center: Company Brief", ":material/badge: LinkedIn",
     ":material/mic: Interview Lab", ":material/description: Resume Studio"]
)

# ----------------------------------------------------------------------------- Action Center
from datetime import date as _date, timedelta as _td

with tab_home:
    today = _date.today().isoformat()
    # Only mail from the last few weeks counts as "needs attention" — the backfilled
    # 2025 recruiting history shouldn't nag as if it were live.
    recent_cut = (_date.today() - _td(days=21)).isoformat()

    from job_bot.applications import summary as app_summary
    appsum = app_summary()  # single source of truth for the funnel numbers

    def _txt(v):  # NULL/NaN-safe string for values out of SQLite/pandas
        return "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)

    interviews = _df("SELECT scheduled_at, company, role_title, round_name, status "
                     "FROM interviews WHERE status IN ('scheduled','prepped') ORDER BY scheduled_at")
    followups = _df("SELECT followup_date, contact_name, company, kind FROM outreach "
                    f"WHERE status='drafted' AND followup_date<='{today}' ORDER BY followup_date")
    emails = _df("SELECT received_at, company, category, action FROM tracked_emails "
                 "WHERE handled=0 AND category IN "
                 "('interview_invite','assessment','offer','rejection','recruiter_reply') "
                 "ORDER BY received_at DESC")
    offers_open = _df("SELECT company, role_title, base, deadline FROM offers "
                      "WHERE status='open' ORDER BY deadline")
    hot = _df("SELECT priority, company, title FROM jobs WHERE status='new' "
              "ORDER BY priority DESC LIMIT 6")

    # --- Hero greeting -------------------------------------------------------
    n_open_offers = 0 if offers_open.empty else len(offers_open)
    # Actionable, recent recruiter mail only (interview/assessment/offer in the
    # last ~3 weeks) — not the whole backfilled history.
    fresh_actionable = 0
    if not emails.empty:
        m = (emails["category"].isin(["interview_invite", "assessment", "offer"])
             & (emails["received_at"] >= recent_cut))
        fresh_actionable = int(m.sum())
    attention = (
        (0 if interviews.empty else len(interviews))
        + (0 if followups.empty else len(followups))
        + n_open_offers
        + fresh_actionable
    )
    first = (p.get("name") or "there").split()[0]
    sub = (f"You have {attention} item{'s' if attention != 1 else ''} that need attention today."
           if attention else "You are all caught up - nothing needs attention right now.")
    ui.html(ui.hero(f"{ui.greeting()}, {first}", sub, [
        (f"{appsum['interview_rate']}%", "interview rate"),
        (f"{appsum['response_rate']}%", "response rate"),
        (str(appsum["active"]), "active"),
    ]))

    # --- KPI cards -----------------------------------------------------------
    ui.html(ui.kpi_grid([
        {"label": "Positions applied", "value": appsum["positions"], "icon": "briefcase",
         "color": "blue", "sub": f"across {appsum['total']} companies"},
        {"label": "Interviewed", "value": appsum["reached_interview"], "icon": "video",
         "color": "violet", "sub": f"{appsum['interview_rate']}% of companies"},
        {"label": "Rejected", "value": appsum["rejected"], "icon": "x-circle",
         "color": "red", "sub": "companies"},
        {"label": "Active / pending", "value": appsum["active"], "icon": "clock",
         "color": "amber", "sub": "in review or interviewing"},
        {"label": "Open offers", "value": n_open_offers, "icon": "gift", "color": "green"},
    ]))

    # --- Pipeline funnel -----------------------------------------------------
    ui.html(ui.section("Application funnel", "trending"))
    ui.html(ui.funnel([
        ("Applied", appsum["total"]),
        ("Interviewed", appsum["reached_interview"]),
        ("Offers", appsum["offers"]),
    ]))

    # --- Two-column work surface --------------------------------------------
    cL, cR = st.columns([1.05, 1], gap="large")
    with cL:
        ui.html(ui.section("Upcoming interviews", "calendar",
                           None if interviews.empty else len(interviews)))
        if interviews.empty:
            ui.html(ui.empty_state(
                "No interviews scheduled yet",
                "When you receive an invitation, add it via the prep plan to start preparing.",
                "calendar"))
        else:
            for i, (_, r) in enumerate(interviews.iterrows()):
                when = _txt(r.get("scheduled_at"))[:16].replace("T", " ")
                detail = " - ".join(x for x in [_txt(r.get("role_title")) or "Interview",
                                                _txt(r.get("round_name"))] if x)
                ui.html(ui.notif_card(_txt(r.get("company")) or "-", detail,
                        badge=(_txt(r.get("status")) or "scheduled", "violet"),
                        date=when, company=_txt(r.get("company")), delay=i * 40))

        ui.html(ui.section("Follow-ups due", "mail",
                           None if followups.empty else len(followups)))
        if followups.empty:
            ui.html(ui.empty_state("Nothing due today",
                    "Outreach follow-ups appear here on their due date.", "check"))
        else:
            for i, (_, r) in enumerate(followups.iterrows()):
                who = _txt(r.get("contact_name")) or _txt(r.get("company")) or "-"
                detail = " - ".join(x for x in [_txt(r.get("kind")) or "Follow-up",
                                                _txt(r.get("company"))] if x)
                ui.html(ui.notif_card(who, detail, badge=("due", "amber"),
                        date=_txt(r.get("followup_date")),
                        company=_txt(r.get("company")) or who, delay=i * 40))

        ui.html(ui.section("Open offers to decide", "gift",
                           None if offers_open.empty else n_open_offers))
        if offers_open.empty:
            ui.html(ui.empty_state("No open offers",
                    "Log an offer in the Offers tab to compare and decide.", "gift"))
        else:
            for i, (_, r) in enumerate(offers_open.iterrows()):
                base = r.get("base")
                detail = f"${base:,.0f} base" if pd.notna(base) and base else "Compensation TBD"
                if _txt(r.get("deadline")):
                    detail += f" - decide by {_txt(r.get('deadline'))}"
                ui.html(ui.notif_card(_txt(r.get("company")) or "-", detail,
                        badge=("offer", "green"), company=_txt(r.get("company")), delay=i * 40))

    with cR:
        cat_label = {"interview_invite": "Interview", "assessment": "Assessment",
                     "offer": "Offer", "rejection": "Rejection", "recruiter_reply": "Reply"}
        cat_color = {"interview_invite": "violet", "assessment": "blue", "offer": "green",
                     "rejection": "red", "recruiter_reply": "slate"}
        if emails.empty:
            ui.html(ui.section("Recruiter emails", "inbox"))
            ui.html(ui.empty_state("Inbox clear",
                    "Unhandled recruiter messages will show up here, grouped by company.", "inbox"))
        else:
            ui.html(ui.section("Recruiter emails", "inbox", len(emails)))
            present = [c for c in cat_label if (emails["category"] == c).any()]
            choice = st.segmented_control(
                "Filter", ["All"] + [cat_label[c] for c in present],
                default="All", label_visibility="collapsed", key="email_filter")
            label_to_cat = {v: k for k, v in cat_label.items()}
            view = (emails if choice in (None, "All")
                    else emails[emails["category"] == label_to_cat.get(choice)])
            for i, (comp, grp) in enumerate(
                    view.groupby(view["company"].fillna("Unknown"), sort=False)):
                latest = grp.iloc[0]
                n = len(grp)
                title = f"{comp}" + (f"   -   {n} messages" if n > 1 else "")
                cat = _txt(latest.get("category"))
                badge = (cat_label.get(cat, cat or "email"), cat_color.get(cat, "slate"))
                detail = _txt(latest.get("action")) or cat
                ui.html(ui.notif_card(title, detail, badge=badge,
                        date=_txt(latest.get("received_at"))[:10],
                        company=str(comp), delay=i * 40))

        ui.html(ui.section("Top new postings", "flame",
                           None if hot.empty else len(hot)))
        if hot.empty:
            ui.html(ui.empty_state("No new postings",
                    "Run a job search to surface fresh, ranked roles here.", "flame"))
        else:
            for i, (_, r) in enumerate(hot.iterrows()):
                pr = r.get("priority")
                badge = (f"priority {int(pr)}" if pd.notna(pr) else "new", "slate")
                ui.html(ui.notif_card(_txt(r.get("company")) or "-",
                        _txt(r.get("title")) or "-", badge=badge,
                        company=_txt(r.get("company")), delay=i * 30))
# ----------------------------------------------------------------------------- Applications
with tab_apps:
    from job_bot.applications import STATUS_LABEL, build_applications
    from job_bot.applications import summary as app_summary

    ui.html(ui.section("Applications tracker", "briefcase"))
    apps = build_applications()
    s = app_summary(apps)

    if not apps:
        ui.html(ui.empty_state("No applications yet", "Run the Gmail sync or import your tracker to populate this.", "briefcase"))
    else:
        ui.html(ui.kpi_grid([
            {"label": "Positions applied", "value": s["positions"], "icon": "briefcase",
             "color": "blue", "sub": f"across {s['total']} companies"},
            {"label": "Interviewed", "value": s["reached_interview"], "icon": "video",
             "color": "violet", "sub": f"{s['reached_interview']} of {s['total']} companies"},
            {"label": "Rejected", "value": s["by_status"]["rejected"], "icon": "x-circle",
             "color": "red"},
            {"label": "Ghosted", "value": s["by_status"]["ghosted"], "icon": "inbox",
             "color": "slate", "sub": "no reply in 45 days"},
            {"label": "Active / pending", "value": s["active"], "icon": "clock",
             "color": "amber", "sub": "in review or interviewing"},
            {"label": "Offers", "value": s["by_status"]["offer"], "icon": "gift", "color": "green"},
        ]))

        st.caption(f"Response rate (heard back vs ghosted): **{s['response_rate']}%**  ·  "
                   f"Interview rate: **{s['interview_rate']}%**  ·  "
                   "A company may have several role applications; status is its furthest outcome.")

        # Status breakdown chart (ordered, labelled).
        order = ["offer", "interviewing", "in_review", "ghosted", "rejected"]
        gc1, gc2 = st.columns(2)
        with gc1:
            st.markdown("**By status**")
            st.bar_chart(pd.DataFrame(
                {"Applications": [s["by_status"][k] for k in order]},
                index=[STATUS_LABEL[k] for k in order]))
        with gc2:
            st.markdown("**By career field**")
            st.bar_chart(pd.DataFrame(
                {"Companies": [v["companies"] for v in s["by_field"].values()]},
                index=list(s["by_field"].keys())))

        # Filters + table.
        f1, f2, f3 = st.columns([2, 2, 1])
        opts = ["(all)"] + [STATUS_LABEL[k] for k in order if s["by_status"][k]]
        fsel = f1.selectbox("Filter by status", opts)
        fields = ["(all)"] + list(s["by_field"].keys())
        fldsel = f2.selectbox("Filter by field", fields)
        itv_only = f3.checkbox("Interviewed only")

        rows = []
        for a in apps:
            if itv_only and not a["reached_interview"]:
                continue
            if fsel != "(all)" and STATUS_LABEL[a["status"]] != fsel:
                continue
            if fldsel != "(all)" and a["field"] != fldsel:
                continue
            rows.append({
                "Company": a["company"],
                "Field": a["field"],
                "Status": STATUS_LABEL[a["status"]],
                "Interviewed": "★" if a["reached_interview"] else "",
                "Positions": a["positions"],
                "First applied": a["first_seen"] or "—",
                "Last update": a["last_seen"] or "—",
                "Roles": "; ".join(a["roles"][:6]) + ("…" if len(a["roles"]) > 6 else ""),
            })
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        st.caption(f"{len(rows)} of {len(apps)} companies shown")

# ----------------------------------------------------------------------------- Overview
with tab_over:
    from job_bot.applications import summary as _appsum
    from job_bot.ats_engine import candidate_skills, profile_text
    edu = (profile.get("education") or [{}])[0]
    s = _appsum()
    n_skills = len(candidate_skills(profile_text(profile)))
    tgt = profile.get("targets", {}).get("target_roles", [])

    _per = profile.get("personal", {})
    _headline = next(iter(profile.get("targets", {}).get("target_roles", []) or []), None)
    ui.html(ui.personal_card(
        _per.get("name") or "—", headline=_headline, location=_per.get("location"),
        email=_per.get("email"), linkedin=_per.get("linkedin"), phone=_per.get("phone"),
        avatar_html=ui.avatar(str(_per.get("name") or "?"), _avatar_src(_per), size=64)))
    st.write("")
    ui.html(ui.section("Profile", "sparkle"))
    ui.html(ui.kpi_grid([
        {"label": "GPA", "value": edu.get("gpa") or "—", "icon": "sparkle", "color": "violet"},
        {"label": "Graduation", "value": edu.get("graduation_date") or "—", "icon": "calendar",
         "color": "blue"},
        {"label": "Skills tracked", "value": n_skills, "icon": "check", "color": "green"},
        {"label": "Certifications", "value": len(profile.get("certifications", [])) or "—",
         "icon": "briefcase", "color": "amber"},
    ]))

    ui.html(ui.section("Search performance", "trending"))
    ui.html(ui.kpi_grid([
        {"label": "Positions applied", "value": s["positions"], "icon": "briefcase", "color": "blue",
         "sub": f"across {s['total']} companies"},
        {"label": "Interviewed", "value": s["reached_interview"], "icon": "video", "color": "violet",
         "sub": f"{s['interview_rate']}% interview rate"},
        {"label": "Response rate", "value": f"{s['response_rate']}%", "icon": "trending",
         "color": "green", "sub": "heard back vs ghosted"},
        {"label": "Active / pending", "value": s["active"], "icon": "clock", "color": "amber"},
    ]))
    if tgt:
        st.caption("**Targeting:** " + "  ·  ".join(tgt))

    if s["by_field"]:
        st.markdown("#### Where you're applying (by field)")
        fld = pd.DataFrame(
            {"Companies": [v["companies"] for v in s["by_field"].values()],
             "Interviewed": [v["interviewed"] for v in s["by_field"].values()]},
            index=list(s["by_field"].keys()))
        cc1, cc2 = st.columns([3, 2])
        cc1.bar_chart(fld["Companies"])
        cc2.dataframe(fld, width="stretch")
        st.caption("See the **Growth Plan** tab for how to strengthen your candidacy in each field.")

    ui.html(ui.section("Education", "check"))
    st.write(f"**{edu.get('school','')}** — {edu.get('degree','')}"
             + (f" / {edu.get('secondary_major')}" if edu.get("secondary_major") else ""))
    if edu.get("relevant_coursework"):
        st.caption("Coursework: " + ", ".join(edu["relevant_coursework"]))

    ui.html(ui.section("Experience", "briefcase"))
    for e in profile.get("experience", []):
        with st.expander(f"{e.get('role','')} — {e.get('organization','')}  "
                         f"({e.get('start_date','')}–{e.get('end_date','')})"):
            for b in e.get("bullets", []):
                st.markdown(f"- {b.get('text','')}"
                            + ("  `quantified`" if b.get("quantified") else ""))

    ui.html(ui.section("Skills", "sparkle"))
    for grp in profile.get("skills", []):
        st.markdown(f"**{grp.get('category','')}:** " + ", ".join(grp.get("skills", [])))
    if profile.get("certifications"):
        st.markdown("**Certifications:** " + ", ".join(profile["certifications"]))

# ----------------------------------------------------------------------------- Growth Plan
with tab_growth:
    from job_bot.growth import build_plan

    ui.html(ui.section("Growth plan", "trending"))
    st.caption("Auto-generated from your skills vs the fields you target & apply to. "
               "Recomputes as your résumé and applications change.")
    plan = build_plan(profile)

    for i in plan["insights"]:
        st.warning(i)

    st.markdown("#### Do these first")
    for n, a in enumerate(plan["top_actions"], 1):
        st.markdown(f"{n}. {a}")

    st.markdown("#### By field")
    for pf in plan["per_field"]:
        tag = " · stated target" if pf["is_stated_target"] else ""
        n_app = pf["applied_count"]
        with st.expander(f"{pf['field']} — {n_app} application{'' if n_app == 1 else 's'}{tag}",
                         expanded=pf["is_stated_target"]):
            cc1, cc2 = st.columns(2)
            with cc1:
                st.markdown("**You already have**")
                st.write(", ".join(pf["strengths"]) or "—")
                st.markdown("**Gaps to close**")
                st.write(", ".join(pf["gaps"]) or "none — you're strong here")
            with cc2:
                rv = pf["resume_variant"]
                st.markdown(f"**Résumé variant — _{rv['name']}_**")
                st.markdown("Lead with: " + (", ".join(rv["lead_with"]) or "—"))
                if rv["add_keywords"]:
                    st.markdown("Add once earned: " + ", ".join(rv["add_keywords"]))
            if pf["projects"]:
                st.markdown("**Projects to build** (portfolio-able, close the gaps above)")
                for pr in pf["projects"]:
                    st.markdown(f"- {pr}")
            st.markdown("**Certifications**")
            for name, why, effort in pf["certifications"]:
                st.markdown(f"- **{name}** _({effort})_ — {why}")
    st.caption("Tailor a résumé to a specific posting with "
               "`python -m job_bot.generate --file <jd>.txt`.")

# ----------------------------------------------------------------------------- Find Jobs
with tab_find:
    from datetime import date as _date

    from job_bot import newgrad
    from job_bot.applications import classify_field as _cf

    ui.html(ui.section("Find jobs by cycle & track", "sparkle"))

    # --- Graduation date (persisted to master_profile.json) ------------------
    edu_list = profile.get("education") or [{}]
    grad_d = newgrad.parse_grad_date(edu_list[0].get("graduation_date") or "May 2027")
    gc1, gc2 = st.columns([1, 2])
    picked = gc1.date_input("Graduation date", value=grad_d,
                            min_value=_date(2024, 1, 1), max_value=_date(2032, 12, 31),
                            help="Sets which hiring cycles appear below.")
    if picked and picked.replace(day=1) != grad_d:
        try:
            edu_list[0]["graduation_date"] = picked.strftime("%B %Y")
            profile["education"] = edu_list
            config.PROFILE_JSON.write_text(json.dumps(profile, indent=2), encoding="utf-8")
            grad_d = picked.replace(day=1)
            gc2.success(f"Saved graduation date: {picked.strftime('%B %Y')}")
        except Exception as exc:
            gc2.error(f"Could not save: {exc}")
    gc2.caption(f"Graduating **{grad_d.strftime('%B %Y')}** — cycles below update automatically.")

    cycles = newgrad.available_cycles(grad_d)
    if not cycles:
        st.info("No upcoming hiring cycles for that graduation date.")
    else:
        chosen = st.radio("Which hiring cycle?", [c["label"] for c in cycles],
                          horizontal=True)
        cycle = next(c for c in cycles if c["label"] == chosen)

        tracks = st.multiselect(
            "Career tracks to search", list(newgrad.TRACKS.keys()),
            default=newgrad.DEFAULT_TRACKS,
            help="Add **Software & Engineering** or **IT & Cybersecurity** to include tech roles.")
        s1, s2, s3, s4, s5 = st.columns([1.1, 0.8, 1, 1, 1.3])
        loc = s1.text_input("Location", value="Washington, DC", key="find_loc")
        remote_ok = s2.checkbox("Remote-friendly", value=True,
                                help="Internships search remote-first; uncheck to include in-person.")
        per = s3.slider("Results per role", 5, 50, 20)
        fresh = s4.slider("Posted within (hours)", 24, 336, 168, step=24)
        sites = s5.multiselect(
            "Job boards", ["indeed", "linkedin", "glassdoor", "google", "zip_recruiter"],
            default=["indeed"], key="find_sites",
            help="Indeed tolerates scraping well and is the safe default. LinkedIn "
                 "throttles per-IP fairly quickly — turn it on deliberately, not "
                 "on every search.")

        queries = newgrad.build_track_queries(tracks, cycle["kind"], remote_internships=remote_ok)
        preview = " · ".join(q for q, _ in queries[:8]) + (" …" if len(queries) > 8 else "")
        st.caption(f"**{len(queries)}** role searches queued for **{cycle['label']}** — {preview}")
        st.caption(f"≈ **{len(queries) * len(sites) if sites else 0}** board requests this search "
                   f"({len(queries)} roles × {len(sites)} site{'s' if len(sites) != 1 else ''}, "
                   f"{per}/role). High results-per-role across many tracks/sites means more "
                   "requests — searches back off between sites and warn on repeats within an hour.")

        if st.button("🔎 Search job boards", type="primary", disabled=not (queries and sites)):
            with st.spinner(f"Searching {len(queries)} roles on {', '.join(sites)}…"):
                res = newgrad.run(location=loc, hours_old=fresh, results_per=per,
                                  sites=sites, queries=queries)
            scored = res.get("scored", [])
            for r in scored:
                r["field"] = _cf(r.get("title") or "")
            # Persist across reruns so the on-target toggle below keeps working.
            st.session_state["find_res"] = {"scored": scored, "res": res, "cycle": cycle["label"]}
            st.cache_data.clear()

        fr = st.session_state.get("find_res")
        if fr is not None:
            scored, res = fr["scored"], fr["res"]
            if not scored:
                st.warning("No postings came back — JobSpy may be rate-limited, or nothing matched "
                           "these filters. Try fewer tracks, a wider hours window, or search again.")
            else:
                # A broad multi-track scrape pulls in loosely-matched roles; roles that
                # don't map to any target track land in "Other" and are hidden by default.
                on_target = [r for r in scored if r.get("field") != "Other"]
                n_other = len(scored) - len(on_target)
                include_other = st.checkbox(
                    f"Include off-target roles ({n_other} classified 'Other')", value=False,
                    help="Off-target roles are still saved to the pipeline — this only affects "
                         "what's shown here.")
                shown = scored if include_other else on_target
                napply = sum(1 for r in shown if "Apply" in (r.get("recommendation") or ""))
                senior_filtered = max(0, res.get("scraped", len(scored)) - len(scored))
                ui.html(ui.kpi_grid([
                    {"label": "Your-level matches", "value": len(scored), "icon": "briefcase",
                     "color": "blue", "sub": f"{senior_filtered} senior roles filtered out"},
                    {"label": "On-target", "value": len(on_target), "icon": "check",
                     "color": "green", "sub": f"{n_other} off-target ('Other') hidden"},
                    {"label": "New to pipeline", "value": res["saved"], "icon": "sparkle",
                     "color": "violet", "sub": "deduped"},
                    {"label": "Recommended apply", "value": napply, "icon": "trending",
                     "color": "amber", "sub": "entry-level, on-target"},
                ]))
                if shown:
                    d1, d2 = st.columns(2)
                    d1.markdown("**By career field**")
                    d1.bar_chart(pd.Series([r["field"] for r in shown]).value_counts())
                    d2.markdown("**By market tier**")
                    d2.bar_chart(pd.Series([r.get("market_tier", "?") for r in shown]).value_counts())
                with st.expander("Per-search breakdown (found / new per role term)"):
                    st.dataframe(pd.DataFrame(res["per_query"]), width="stretch", hide_index=True)

                ui.html(ui.section("Top matches", "trending"))
                top = sorted(shown, key=lambda x: x.get("priority", 0), reverse=True)[:20]
                if not top:
                    ui.html(ui.empty_state("No on-target roles in this batch",
                            "Tick 'Include off-target roles' above, or add more tracks.", "briefcase"))
                from job_bot.seniority import label as _sen_label
                fcards = []
                for i, r in enumerate(top):
                    grade = str(r.get("legit_grade") or "")
                    flag = r.get("legit_flags") if "legit" not in grade.lower() else None
                    fcards.append(ui.job_card(
                        title=r.get("title") or "Untitled role", company=r.get("company") or "",
                        field=r.get("field"), tier=r.get("market_tier"),
                        location=r.get("location"),
                        date=str(r.get("date_posted") or "")[:10] or None,
                        priority=f"{r.get('priority', 0):.0f}", ats=f"{r.get('ats_score', 0):.0f}",
                        recommendation=r.get("recommendation"), legit=grade or None,
                        url=r.get("url") or None, flag=flag,
                        level=(_sen_label(r["seniority"]) if r.get("seniority") else None),
                        delay=min(i, 12) * 30))
                ui.html("".join(fcards))
                st.caption("All results (including off-target) are saved to the Pipeline tab, deduped by URL.")

    st.divider()
    st.caption("Looking for company career-portals (Big 4 / Workday)? Use **Scan target-company "
               "portals** in the Pipeline tab.")


# ----------------------------------------------------------------------------- Pipeline
with tab_pipe:
    ui.html(ui.section("Job pipeline", "briefcase"))
    jobs = _df("SELECT recommendation, seniority, priority, market_tier, ats_score, legit_grade, "
               "legit_flags, status, site, company, title, location, date_posted, url "
               "FROM jobs ORDER BY priority DESC")
    if jobs.empty:
        ui.html(ui.empty_state("No jobs yet", "Run a job search to populate the pipeline.", "briefcase"))
    else:
        from job_bot.applications import classify_field
        jobs.insert(2, "field", jobs["title"].fillna("").map(classify_field))

        # Legitimacy summary (career-ops Block G): surface anything flagged.
        flagged = jobs[jobs["legit_grade"].fillna("").str.contains("risk|Verify", case=False)]
        rec_apply = jobs[jobs["recommendation"].fillna("").str.contains("Apply")]
        if not jobs["recommendation"].dropna().empty:
            ui.html(ui.kpi_grid([
                {"label": "Recommended: Apply", "value": len(rec_apply), "icon": "check",
                 "color": "green", "sub": "clear the apply gate"},
                {"label": "Flagged postings", "value": len(flagged), "icon": "flame",
                 "color": "red", "sub": "scam / ghost / stale"},
                {"label": "In pipeline", "value": len(jobs), "icon": "briefcase", "color": "slate"},
            ]))
        if not flagged.empty:
            names = ", ".join(f"{r.company} — {r.title}" for r in flagged.head(6).itertuples())
            st.warning(f"⚠️ **{len(flagged)} posting(s) flagged** by the legitimacy check "
                       f"(verify before applying): {names}")

        from job_bot.seniority import LEVELS as _SEN_LEVELS, label as _sen_label
        c1, c2, c3, c4, c5 = st.columns(5)
        tiers = ["(all)"] + sorted(x for x in jobs["market_tier"].dropna().unique())
        statuses = ["(all)"] + sorted(x for x in jobs["status"].dropna().unique())
        fieldlist = ["(all)"] + sorted(x for x in jobs["field"].dropna().unique())
        recs = ["(all)"] + sorted(x for x in jobs["recommendation"].dropna().unique())
        # Level filter, ordered intern→exec, defaulting to John's range (hides senior+).
        present_levels = [lv for lv in _SEN_LEVELS if lv in set(jobs["seniority"].dropna())]
        lvl_opts = ["My level (intern–mid)", "(all levels)"] + [_sen_label(lv) for lv in present_levels]
        lsel = c1.selectbox("Level", lvl_opts)
        tsel = c2.selectbox("Market tier", tiers)
        ssel = c3.selectbox("Status", statuses)
        fsel = c4.selectbox("Career field", fieldlist)
        rsel = c5.selectbox("Recommendation", recs)
        view = jobs.copy()
        if lsel == "My level (intern–mid)":
            view = view[view["seniority"].isin(["intern", "entry", "mid"]) | view["seniority"].isna()]
        elif lsel != "(all levels)":
            want = next((lv for lv in present_levels if _sen_label(lv) == lsel), None)
            if want:
                view = view[view["seniority"] == want]
        if tsel != "(all)":
            view = view[view["market_tier"] == tsel]
        if ssel != "(all)":
            view = view[view["status"] == ssel]
        if fsel != "(all)":
            view = view[view["field"] == fsel]
        if rsel != "(all)":
            view = view[view["recommendation"] == rsel]
        # Card listing — everything on one line per role, no horizontal scroll.
        sc1, sc2 = st.columns([1, 3])
        show_opts = {"Top 25": 25, "Top 50": 50, "Top 100": 100, "All": max(1, len(view))}
        show_key = sc1.selectbox("Show", list(show_opts.keys()), index=1)
        st.caption(f"{len(view)} of {len(jobs)} postings match · the **apply?** badge is the "
                   "career-ops apply gate, the second badge is the scam/ghost **legit** check "
                   "· sorted by priority")

        def _cv(x):
            return "" if x is None or (isinstance(x, float) and pd.isna(x)) else x

        cards = []
        for i, (_, r) in enumerate(view.head(show_opts[show_key]).iterrows()):
            pr = r.get("priority")
            at = r.get("ats_score")
            dt = str(_cv(r.get("date_posted")))[:10] or None
            grade = str(_cv(r.get("legit_grade")))
            # Only surface the flag strip when the posting is actually graded
            # caution/high-risk — keep "Likely legit" cards clean of minor signals.
            flag = str(_cv(r.get("legit_flags"))) if "legit" not in grade.lower() else None
            cards.append(ui.job_card(
                title=str(_cv(r.get("title"))) or "Untitled role",
                company=str(_cv(r.get("company"))),
                field=str(_cv(r.get("field"))) or None,
                tier=str(_cv(r.get("market_tier"))) or None,
                location=str(_cv(r.get("location"))) or None,
                date=dt,
                priority=("" if pd.isna(pr) else f"{pr:.0f}"),
                ats=("" if pd.isna(at) else f"{at:.0f}"),
                recommendation=str(_cv(r.get("recommendation"))) or None,
                legit=grade or None,
                url=str(_cv(r.get("url"))) or None,
                flag=flag,
                level=(_sen_label(r["seniority"]) if _cv(r.get("seniority")) else None),
                delay=min(i, 12) * 30))
        ui.html("".join(cards))

        with st.expander("View as a table (all columns · sortable · exportable)"):
            st.dataframe(view.drop(columns=["legit_flags"], errors="ignore"),
                         width="stretch", hide_index=True,
                         column_config={"url": st.column_config.LinkColumn("url"),
                                        "recommendation": "apply?", "legit_grade": "legit"})

    # --- Direct career-portal scan (career-ops portal scan) ------------------
    ui.html(ui.section("Scan target-company portals", "briefcase"))
    st.caption("Pulls fresh openings straight from company career portals (Greenhouse/Lever "
               "public feeds) — often fresher than LinkedIn/Indeed. Big-4/Workday portals "
               "have no public feed, so you get a direct link + strategy instead.")
    if st.button("Scan portals now"):
        from job_bot import portals
        with st.spinner("Scanning target-company portals…"):
            res = portals.scan_and_save()
        scanned = [s for s in res.get("scanned", []) if s["found"]]
        if res.get("saved"):
            st.success(f"Found and saved {res['saved']} new portal role(s) into the pipeline above.")
            st.cache_data.clear()
        elif scanned:
            st.info("Portals scanned, but no new matching roles right now.")
        else:
            st.info("No live-feed portals returned roles (network/`requests` may be unavailable). "
                    "The manual portals below are still worth checking.")
        manual = res.get("manual", [])
        if manual:
            st.markdown("**Check these portals directly** (no public feed):")
            for e in manual:
                st.markdown(f"- **{e['company']}** — [{e.get('url','portal')}]({e.get('url','')})")

    ui.html(ui.section("Decision log", "check"))
    dec = _df("SELECT created_at, company, title, verdict, ats_score, competition, connection "
              "FROM decisions ORDER BY created_at DESC")
    if dec.empty:
        ui.html(ui.empty_state("No decisions logged", "Score a JD to log network-vs-cold decisions.", "check"))
    else:
        st.dataframe(dec, width="stretch", hide_index=True)

    ui.html(ui.section("Rejection analysis", "x-circle"))
    st.caption("Per-role rejection **events** (one company may reject several roles). "
               "For company-level counts, see the Applications tab.")
    from job_bot.rejections import analyze
    rej = analyze()
    if rej.get("total", 0) == 0:
        ui.html(ui.empty_state("No rejections logged", "These auto-log from inbox triage.", "x-circle"))
    else:
        top_stage = max(rej["by_stage"], key=rej["by_stage"].get)
        ui.html(ui.kpi_grid([
            {"label": "Rejection events", "value": rej["total"], "icon": "x-circle", "color": "red"},
            {"label": "Avg ATS on rejected", "value": rej.get("avg_ats_score") or "—",
             "icon": "trending", "color": "slate"},
            {"label": "Most-rejected stage", "value": top_stage, "icon": "flame", "color": "amber"},
        ]))
        cc1, cc2 = st.columns(2)
        cc1.bar_chart(rej["by_stage"])
        cc2.bar_chart(rej["by_role_type"])
        for i in rej["insights"]:
            st.markdown(f"- {i}")
        for r in rej["recommendations"]:
            st.markdown(f"- {r}")

    ui.html(ui.section("Cover-letter A/B", "mail"))
    from job_bot.cover_ab import analyze as ab_analyze

    ab = ab_analyze()
    if ab["total"] == 0:
        st.info("No cover-letter variants logged yet "
                "(`python -m job_bot.cover_ab --file jd.txt --firm-type big4`).")
    else:
        rows = [{"Style": k, "Sent": v["sent"], "Responses": v["responses"],
                 "Rate %": v["rate"]} for k, v in ab["by_style"].items()]
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        for i in ab["insights"]:
            st.markdown(f"- {i}")

# ----------------------------------------------------------------------------- Network
with tab_net:
    ui.html(ui.section("Import contacts", "users"))
    with st.expander("Upload a CSV or Excel file of people", expanded=False):
        from job_bot.connections import RELATIONSHIP_WARMTH, import_linkedin_csv, import_records

        up = st.file_uploader("Drop a file — LinkedIn Connections.csv, a PSE alumni sheet, "
                              "or any roster with name/company columns",
                              type=["csv", "xlsx", "xls"])
        rel = st.selectbox(
            "Tag everyone in this file as…",
            list(RELATIONSHIP_WARMTH.keys()),
            index=list(RELATIONSHIP_WARMTH.keys()).index("pse"),
            help="Sets the default relationship/warmth. Use 'pse' for the PSE alumni database, "
                 "'first_degree' for a LinkedIn export. A 'Relationship' column in the file "
                 "overrides this per row.")
        cclr = st.checkbox("Replace existing connections from this same file first", value=True)
        if st.button("Import contacts", type="primary") and up is not None:
            updir = config.OUTPUT_DIR / "uploads"
            updir.mkdir(parents=True, exist_ok=True)
            dest = updir / up.name
            dest.write_bytes(up.getbuffer())
            try:
                con = connect()
                if cclr:
                    con.execute("DELETE FROM connections WHERE source=?", (up.name,))
                    con.commit()
                con.close()
                if up.name.lower().endswith(".csv"):
                    n = import_linkedin_csv(dest, default_relationship=rel)
                else:
                    df = pd.read_excel(dest)
                    n = import_records(df.to_dict("records"),
                                       default_relationship=rel, source=up.name)
                st.success(f"Imported {n} contacts from {up.name} (tagged '{rel}'). "
                           "Scroll down — the list and coverage map just updated.")
                st.cache_data.clear()
            except Exception as exc:
                st.error(f"Import failed: {exc}")

    ui.html(ui.section("Connections", "users"))
    conns = _df("SELECT company, name, relationship, warmth, title, source FROM connections "
                "ORDER BY company, warmth DESC")
    if conns.empty:
        ui.html(ui.empty_state("No connections yet", "Upload a LinkedIn or alumni file above to map your network.", "users"))
    else:
        st.dataframe(conns, width="stretch", hide_index=True)
        if (conns["source"] == "sample_connections.csv").any():
            st.caption("Some rows are bundled **sample** data (source = "
                       "sample_connections.csv) — replace them by uploading your real export.")

    ui.html(ui.section("Outreach follow-up queue", "mail"))
    out = _df("SELECT followup_date, status, contact_name, company, role_title, kind "
              "FROM outreach ORDER BY followup_date")
    if out.empty:
        ui.html(ui.empty_state("No outreach queued", "Draft outreach to start the follow-up queue.", "mail"))
    else:
        st.dataframe(out, width="stretch", hide_index=True)

    ui.html(ui.section("Network coverage map", "users"))
    from job_bot.network_map import build_map

    nm = build_map()
    if not nm["covered"]:
        ui.html(ui.empty_state("Coverage map is empty", "Import connections and the map fills in automatically.", "users"))
    else:
        cov = pd.DataFrame([
            {"Company": s["company"], "Coverage": s["coverage"], "Contacts": s["count"],
             "Ties": ", ".join(s["relationships"]), "Reach first": s["reach_first"]}
            for s in nm["covered"]])
        cc1, cc2 = st.columns([2, 3])
        cc1.bar_chart(cov.set_index("Company")["Coverage"])
        cc2.dataframe(cov, width="stretch", hide_index=True)
        if nm["gaps"]:
            st.warning("**Coverage gaps** (targets to build warmth at): "
                       + ", ".join(f"{g['company']} ({g['status']})" for g in nm["gaps"]))
        else:
            st.success("Every target company has warm coverage.")

# ----------------------------------------------------------------------------- Score a JD
with tab_tool:
    ui.html(ui.section("Score a job description", "sparkle"))
    jd = st.text_area("Paste a job description", height=220)
    url = st.text_input("Posting URL (optional, improves ATS detection)")
    company = st.text_input("Company override (optional)")
    if st.button("Analyze", type="primary") and jd.strip():
        from job_bot.ats_engine import score
        from job_bot.connections import matches_for_company
        from job_bot.decision_engine import decide
        from job_bot.jd_parser import parse_jd

        job = parse_jd(jd, url=url or None, use_llm=config.has_llm())
        if company:
            job.company = company
        report = score(job, profile)
        con = connect()
        matches = matches_for_company(con, job.company)
        con.close()
        decision = decide(job, report.overall_score, matches)

        ui.html(ui.kpi_grid([
            {"label": "ATS match", "value": f"{report.overall_score:.0f}/100", "icon": "check",
             "color": "blue"},
            {"label": "ATS platform", "value": report.ats_platform, "icon": "briefcase",
             "color": "slate"},
            {"label": "Network verdict", "value": decision.verdict_label.split("—")[0].strip(),
             "icon": "users", "color": "violet"},
        ]))

        st.markdown(f"**Role:** {job.title or '—'} @ {job.company or '—'}  ·  "
                    f"**Tier:** {job.market_tier or '—'}  ·  **Type:** {job.role_type or '—'}")
        st.progress(min(1.0, report.overall_score / 100), text="ATS match")

        cc1, cc2 = st.columns(2)
        with cc1:
            st.markdown("**Matched keywords**")
            st.write(", ".join(h.keyword for h in report.matched_keywords) or "—")
        with cc2:
            st.markdown("**Missing (required)**")
            st.write(", ".join(h.keyword for h in report.missing_keywords
                               if h.importance == "required") or "none")

        st.markdown("**Ranked gap analysis**")
        for g in report.gap_analysis[:8]:
            st.markdown(f"- `{g.importance}` **{g.keyword}** (+{g.impact*100:.1f}) — {g.action}")

        st.markdown(f"**Decision:** {decision.verdict_label}")
        st.caption(decision.rationale)
        for a in decision.recommended_actions:
            st.markdown(f"- {a}")

# ----------------------------------------------------------------------------- Offers
with tab_offers:
    ui.html(ui.section("Offer comparison", "gift"))
    from job_bot.offers import col_for, compare, log_offer

    with st.expander("Add / log an offer"):
        o1, o2, o3 = st.columns(3)
        oc = o1.text_input("Company", key="oc")
        orole = o2.text_input("Role", key="orole")
        oloc = o3.text_input("Location", key="oloc", placeholder="Washington, DC")
        b1, b2, b3, b4 = st.columns(4)
        obase = b1.number_input("Base", min_value=0.0, step=1000.0, value=0.0)
        obonus = b2.number_input("Bonus", min_value=0.0, step=1000.0, value=0.0)
        oequity = b3.number_input("Equity/yr", min_value=0.0, step=1000.0, value=0.0)
        obenefits = b4.number_input("Benefits $", min_value=0.0, step=1000.0, value=0.0)
        g1, g2, g3 = st.columns(3)
        ogrowth = g1.slider("Growth (1-5)", 1.0, 5.0, 3.0, 0.5)
        ofit = g2.slider("Fit (1-5)", 1.0, 5.0, 3.0, 0.5)
        odeadline = g3.text_input("Deadline (YYYY-MM-DD)", key="odeadline")
        if oloc:
            st.caption(f"Detected cost-of-living index for '{oloc}': {col_for(oloc):.0f} (100 = US avg)")
        if st.button("Save offer", type="primary") and oc.strip():
            log_offer(oc.strip(), orole.strip() or None, base=obase, bonus=obonus,
                      equity=oequity, benefits_value=obenefits, location=oloc.strip() or None,
                      growth=ogrowth, fit=ofit, deadline=odeadline.strip() or None)
            st.success(f"Logged offer from {oc}. Re-run the comparison below.")

    st.markdown("**Your priorities** (the weights driving the ranking)")
    w1, w2, w3 = st.columns(3)
    wm = w1.slider("Money", 0.0, 1.0, 0.5, 0.05)
    wg = w2.slider("Growth", 0.0, 1.0, 0.25, 0.05)
    wf = w3.slider("Fit", 0.0, 1.0, 0.25, 0.05)
    result = compare({"money": wm, "growth": wg, "fit": wf})
    if not result["offers"]:
        ui.html(ui.empty_state("No open offers", "Add an offer above to compare COL-adjusted comp.", "gift"))
    else:
        rows = [{"Rank": i, "Company": o["company"], "Role": o["role_title"],
                 "Total comp": o["total_comp"], "COL-adjusted": o["adjusted_comp"],
                 "Score": o["score"], "Deadline": o.get("deadline") or "—"}
                for i, o in enumerate(result["offers"], 1)]
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        win = result["winner"]
        st.success(f"Top pick under your priorities: **{win['company']}** "
                   f"(score {win['score']}, COL-adjusted ${win['adjusted_comp']:,.0f})")
        chart = pd.DataFrame({o["company"]: o["score"] for o in result["offers"]}, index=["Score"]).T
        st.bar_chart(chart)
        for ins in result["insights"]:
            st.markdown(f"- {ins}")

    st.divider()
    st.markdown("#### :material/trending_up: Is an offer at market? (salary intelligence)")
    from job_bot.salary import LEVELS, assess_offer, estimate

    s1, s2, s3 = st.columns(3)
    srole = s1.text_input("Role", value="technology risk", key="srole")
    sloc = s2.text_input("Location", value="Washington, DC", key="sloc")
    slevel = s3.selectbox("Level", LEVELS, index=1)
    s4, s5 = st.columns(2)
    soffer = s4.number_input("Your offer total comp (optional)", min_value=0.0, step=1000.0, value=0.0)
    smarket = s5.text_input("Live market points (comma-sep, optional)",
                            placeholder="104000, 91000, 122284")
    if st.button("Estimate market range"):
        pts = [float(x) for x in smarket.replace(" ", "").split(",") if x] or None
        est = estimate(srole, sloc, slevel, market_points=pts)
        ui.html(ui.kpi_grid([
            {"label": "25th pct", "value": f"${est['p25']:,.0f}", "icon": "trending", "color": "slate"},
            {"label": "Median", "value": f"${est['p50']:,.0f}", "icon": "trending", "color": "blue"},
            {"label": "75th pct", "value": f"${est['p75']:,.0f}", "icon": "trending", "color": "green"},
        ]))
        st.caption(f"{est['location']} · COL index {est['col_index']:.0f} · {est['source']}")
        if soffer > 0:
            a = assess_offer(soffer, est)
            (st.success if a["verdict"] in ("at market", "above market") else st.warning)(
                f"**{a['verdict'].upper()}** (~{a['approx_percentile']}th pct) — {a['advice']}")

    st.divider()
    st.markdown("#### :material/handshake: Negotiation prep (paste-ready scripts)")
    st.caption("Turns the market range into things you can actually say — a data-anchored "
               "counter, geographic-discount pushback, competing-offer leverage, and a counter email.")
    from job_bot.negotiation import build as build_negotiation

    n1, n2, n3 = st.columns(3)
    nrole = n1.text_input("Role", value="technology risk", key="nrole")
    nloc = n2.text_input("Location", value="Washington, DC", key="nloc")
    nlevel = n3.selectbox("Level", LEVELS, index=1, key="nlevel")
    n4, n5 = st.columns(2)
    noffer = n4.number_input("Your offer (total comp)", min_value=0.0, step=1000.0, value=0.0, key="noffer")
    ncompeting = n5.number_input("Competing offer (optional, only if real)", min_value=0.0,
                                 step=1000.0, value=0.0, key="ncompeting")
    if st.button("Generate negotiation scripts"):
        pack = build_negotiation(nrole, nloc, nlevel,
                                 offer=noffer or None, competing=ncompeting or None)
        m = pack["market"]
        # Streamlit markdown treats $...$ as LaTeX — escape $ so figures render literally.
        def _esc(s):
            return str(s).replace("$", "\\$")
        ask_s = _esc(f"${pack['target']:,.0f}")
        med_s = _esc(f"${m['p50']:,.0f}")
        p75_s = _esc(f"${m['p75']:,.0f}")
        st.markdown(f"**Recommended ask: {ask_s}**  ·  market median "
                    f"{med_s}, 75th {p75_s}  ·  {pack['location']}")
        if pack.get("assessment"):
            st.caption(f"Your offer reads as **{pack['assessment']['verdict']}** "
                       f"(~{pack['assessment']['approx_percentile']}th pct).")
        labels = {"counter": "Counter", "geo_pushback": "Geographic-discount pushback",
                  "competing": "Competing-offer leverage", "non_cash": "If base is capped"}
        for key, label in labels.items():
            st.markdown(f"**{label}**")
            st.markdown(f"> {_esc(pack['scripts'][key])}")
        st.markdown("**Counter email**")
        st.code(pack["scripts"]["email"], language="text")

# ----------------------------------------------------------------------------- Company Brief
with tab_brief:
    ui.html(ui.section("Company research brief", "briefcase"))
    bc1, bc2 = st.columns([2, 2])
    bcompany = bc1.text_input("Company", placeholder="Deloitte")
    brole = bc2.text_input("Role", value="this role")
    bnews = st.text_area("Recent news (one headline per line, optional)",
                         height=90, placeholder="Paste headlines from web search / news here…")
    if st.button("Build brief", type="primary") and bcompany.strip():
        from job_bot.company_research import build_brief

        news = [n.strip() for n in bnews.splitlines() if n.strip()]
        b = build_brief(bcompany.strip(), brole.strip() or "this role",
                        news=news or None, use_llm=config.has_llm())
        ui.html(ui.kpi_grid([
            {"label": "Firm type", "value": b["type"].split("—")[0].strip(), "icon": "briefcase",
             "color": "blue"},
            {"label": "ATS platform", "value": b["ats_platform"] or "—", "icon": "check",
             "color": "slate"},
            {"label": "Warm contacts", "value": len(b["warm_contacts"]), "icon": "users",
             "color": "green"},
        ]))

        if b.get("narrative"):
            st.info(b["narrative"])

        cc1, cc2 = st.columns(2)
        with cc1:
            st.markdown("**Hiring process**")
            for i, s in enumerate(b["hiring_process"], 1):
                st.markdown(f"{i}. {s}")
            st.markdown("**Firm values**")
            st.write(" · ".join(b["values"]))
            st.markdown("**Why this firm — your angles**")
            for a in b["why_this_firm"]:
                st.markdown(f"- {a}")
        with cc2:
            st.markdown("**Likely interview topics**")
            for t in b["likely_topics"]:
                st.markdown(f"- {t}")
            st.markdown("**Smart questions to ask them**")
            for q in b["smart_questions"]:
                st.markdown(f"- {q}")

        if b["recent_news"]:
            st.markdown("**Recent news** (work one into 'why this firm')")
            for n in b["recent_news"]:
                st.markdown(f"- {n}")
        if b["warm_contacts"]:
            st.markdown("**Warm contacts here**")
            st.dataframe(pd.DataFrame(b["warm_contacts"]), width="stretch", hide_index=True)
        if b["prior_rejections"]:
            st.warning("Prior history here: "
                       + ", ".join(f"rejected at {r['stage']}" for r in b["prior_rejections"]))

# ----------------------------------------------------------------------------- LinkedIn
with tab_li:
    ui.html(ui.section("LinkedIn profile optimizer", "check"))
    st.caption("Audits your profile against the ATS keyword logic and proposes paste-ready edits.")
    li_role = st.text_input("Target role (blank = profile default)", key="li_role")
    li_jd = st.text_area("Optional: paste a target JD to find keyword gaps", height=140, key="li_jd")
    if st.button("Optimize profile", type="primary"):
        from job_bot.linkedin_optimizer import audit

        a = audit(profile, jd_text=li_jd or None, target_role=li_role or None, use_llm=config.has_llm())
        st.markdown(f"**Target role:** {a['target_role']}")
        st.markdown("**Headline** (paste into LinkedIn — max 220 chars)")
        st.code(a["headline"], language=None)
        st.caption(f"{len(a['headline'])} chars")
        st.markdown("**About**")
        st.code(a["about"], language=None)
        if a["keyword_gaps"]:
            st.markdown("**Keyword gaps vs the JD** (add these first)")
            st.warning(", ".join(a["keyword_gaps"]))
        st.markdown("**Skills (priority order)**")
        st.write(", ".join(a["skills"]))
        st.markdown("**Experience bullets to mirror**")
        for e in a["experience"]:
            with st.expander(f"{e['role']} @ {e['organization']}"):
                for b in e["top_bullets"]:
                    st.markdown(f"- {b}")
                st.caption(e["note"])
        st.markdown("**Recommendations**")
        for r in a["recommendations"]:
            st.markdown(f"- {r}")

# ----------------------------------------------------------------------------- Interview Lab
with tab_lab:
    ui.html(ui.section("Interview recording analysis", "video"))
    st.caption("Paste a transcript of a recorded practice answer; get pacing, fillers, "
               "STAR compliance, and phrases to cut.")
    lab_q = st.text_input("Question", value="Tell me about a time you improved a process")
    lab_t = st.text_area("Answer transcript", height=160,
                         placeholder="Paste the transcript of your recorded answer…")
    lab_dur = st.number_input("Spoken duration (seconds, optional — enables pacing)",
                              min_value=0.0, step=5.0, value=0.0)
    if st.button("Analyze recording", type="primary") and lab_t.strip():
        from job_bot.recording import analyze_recording

        a = analyze_recording(lab_t, lab_dur or None, lab_q, use_llm=config.has_llm())
        ui.html(ui.kpi_grid([
            {"label": "Score", "value": f"{a['score']}/100", "icon": "sparkle", "color": "violet",
             "sub": a["band"]},
            {"label": "Words", "value": a["word_count"], "icon": "check", "color": "slate"},
            {"label": "Fillers", "value": a["filler_count"], "icon": "x-circle", "color": "amber"},
            {"label": "Pace", "value": f"{a['pacing']['wpm']} wpm" if a["pacing"] else "—",
             "icon": "clock", "color": "blue"},
        ]))
        st.markdown("**STAR:** " + (", ".join(k for k, v in a["star"].items() if v) or "none")
                    + f"  ·  **Quantified:** {'yes' if a['quantified'] else 'no'}"
                    + f"  ·  **Ownership:** {a['ownership']:.0%}")
        for d in a["delivery_notes"]:
            st.markdown(f"- {d}")
        for c in a["phrases_to_cut"]:
            st.markdown(f"- Cut: {c}")
        if a["improvements"]:
            st.markdown("**Improve:**")
            for i in a["improvements"]:
                st.markdown(f"- {i}")

# ----------------------------------------------------------------------------- Resume Studio
with tab_resume:
    import base64 as _b64
    from pathlib import Path as _Path

    ui.html(ui.section("Resume Studio — resume as code", "briefcase"))
    st.caption(
        "The resume is a RenderCV YAML file you edit **as text** below, then typeset to PDF. "
        "Heads-up on the online round-trip: RenderCV 2.x typesets via **Typst** (v2 dropped "
        "LaTeX), so the intermediate source is a `.typ` file — Overleaf is LaTeX-only and "
        "can't open it. To edit online, download the `.typ` and paste it into "
        "[typst.app](https://typst.app); that trip is one-way — copy changes back over the "
        "local file yourself. (A LaTeX/Overleaf flow would mean pinning `rendercv<2`; a "
        "scripted Overleaf sync via the unofficial `pyoverleaf` package is a stretch goal "
        "only — unofficial, could break without notice.)")

    _studio_dir = config.OUTPUT_DIR / "resume_studio"
    _apps_root = config.OUTPUT_DIR / "applications"
    _app_yamls = sorted(_apps_root.glob("*/resume.yaml")) if _apps_root.exists() else []
    _FROM_PROFILE = "— build fresh from master profile (no target JD) —"
    studio_src = st.selectbox(
        "Start from", [_FROM_PROFILE] + [p.parent.name for p in _app_yamls],
        help="Application folders appear here once generated with "
             "`python -m job_bot.generate --renderer rendercv` — that run writes "
             "the editable resume.yaml next to the PDF.")

    # Download/save-as name: Lastname_Firstname_Company_Date (files on disk keep
    # their canonical names; only what the browser saves changes).
    from job_bot.tailor import resume_basename as _resume_basename
    _studio_name = (profile.get("personal") or {}).get("name")
    _studio_company = None if studio_src == _FROM_PROFILE else studio_src.split("_", 1)[0]

    def _studio_dl_name(ext: str) -> str:
        return _resume_basename(_studio_name, _studio_company) + ext

    def _studio_build_resume():
        """TailoredResume straight from the master profile (no target JD)."""
        from job_bot.jd_parser import parse_jd
        from job_bot.tailor import tailor_resume
        targets = (profile.get("targets") or {}).get("target_roles") or ["Analyst"]
        skills = ", ".join(s for g in profile.get("skills", [])
                           for s in g.get("skills", []))
        jd = parse_jd(f"{targets[0]}. Skills: {skills}", use_llm=False)
        return tailor_resume(profile, jd, use_llm=False)

    def _studio_load_yaml() -> str:
        if studio_src == _FROM_PROFILE:
            from job_bot.render_rendercv import resume_to_rendercv_dict
            return json.dumps(resume_to_rendercv_dict(_studio_build_resume()),
                              indent=2, ensure_ascii=False)
        return next(p for p in _app_yamls
                    if p.parent.name == studio_src).read_text(encoding="utf-8")

    if st.session_state.get("studio_src") != studio_src:
        st.session_state["studio_src"] = studio_src
        st.session_state["studio_yaml"] = _studio_load_yaml()
        st.session_state.pop("studio_out", None)

    studio_yaml = st.text_area(
        "RenderCV YAML — this *is* the resume: reorder bullets, rewrite wording, "
        "add/remove sections directly (the file is JSON, which is valid YAML)",
        height=460, key="studio_yaml")

    def _studio_default_renderer() -> str:
        """'rendercv' or 'docx', auto-picked from the source's career field: an
        application folder's meta.json if present, else the first target role."""
        from job_bot.applications import classify_field
        from job_bot.template_select import renderer_for_field
        if studio_src != _FROM_PROFILE:
            _meta = _apps_root / studio_src / "meta.json"
            if _meta.exists():
                try:
                    _m = json.loads(_meta.read_text(encoding="utf-8"))
                    if _m.get("renderer") in ("rendercv", "docx"):
                        return _m["renderer"]
                    if _m.get("field"):
                        return renderer_for_field(_m["field"])
                except Exception:
                    pass
        targets = (profile.get("targets") or {}).get("target_roles") or ["Analyst"]
        return renderer_for_field(classify_field(targets[0]))

    _rlabels = ["Typst PDF (RenderCV)", "Word (.docx)"]
    _rdefault = 0 if _studio_default_renderer() == "rendercv" else 1
    # Source-scoped key so switching sources re-defaults to that source's field,
    # while a manual override still sticks per source.
    studio_renderer = st.radio("Renderer", _rlabels, horizontal=True,
                               index=_rdefault, key=f"studio_renderer_{studio_src}",
                               help="Defaults to the template for this application's "
                                    "career field (tech → Typst/CS, business → "
                                    ".docx/VMH). Override anytime.")

    if studio_renderer.startswith("Typst"):
        if st.button("🖨️ Render PDF", type="primary", disabled=not studio_yaml.strip()):
            _studio_dir.mkdir(parents=True, exist_ok=True)
            _ypath = _studio_dir / "resume.yaml"
            _ypath.write_text(studio_yaml, encoding="utf-8")
            try:
                from job_bot.render_rendercv import render_yaml_file
                with st.spinner("Typesetting via RenderCV/Typst…"):
                    _outs = render_yaml_file(_ypath, _studio_dir / "out")
                st.session_state["studio_out"] = {k: str(v) for k, v in _outs.items() if v}
            except Exception as exc:
                st.error(f"Render failed: {exc}")
        _outs = st.session_state.get("studio_out")
        if _outs:
            _pdf_bytes = _Path(_outs["pdf"]).read_bytes()
            dl1, dl2, dl3, dl4 = st.columns(4)
            dl1.download_button("⬇️ resume.pdf", _pdf_bytes,
                                file_name=_studio_dl_name(".pdf"),
                                mime="application/pdf")
            dl2.download_button("⬇️ resume.yaml",
                                _Path(_outs["yaml"]).read_text(encoding="utf-8"),
                                file_name="resume.yaml")
            if _outs.get("typ"):
                dl3.download_button("⬇️ resume.typ",
                                    _Path(_outs["typ"]).read_text(encoding="utf-8"),
                                    file_name="resume.typ")
            dl4.link_button("Open typst.app ↗", "https://typst.app",
                            help="Paste the downloaded .typ into a new typst.app "
                                 "project to edit online.")
            if hasattr(st, "pdf"):
                st.pdf(_outs["pdf"], height=760)
            else:
                _b = _b64.b64encode(_pdf_bytes).decode()
                st.markdown(f'<iframe src="data:application/pdf;base64,{_b}" '
                            'width="100%" height="760" style="border:none;"></iframe>',
                            unsafe_allow_html=True)
    else:
        if studio_src == _FROM_PROFILE:
            if st.button("🖨️ Render .docx", type="primary"):
                from job_bot.render_docx import render_docx
                _studio_dir.mkdir(parents=True, exist_ok=True)
                _dpath = render_docx(_studio_build_resume(), _studio_dir / "resume.docx")
                st.session_state["studio_docx"] = str(_dpath)
            if st.session_state.get("studio_docx"):
                st.download_button(
                    "⬇️ resume.docx", _Path(st.session_state["studio_docx"]).read_bytes(),
                    file_name=_studio_dl_name(".docx"),
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            st.caption("Note: the .docx renders from the master profile directly — "
                       "YAML edits above only affect the Typst/RenderCV output.")
        else:
            _docx = _apps_root / studio_src / "resume.docx"
            if _docx.exists():
                st.download_button(
                    "⬇️ resume.docx (from this application's generate run)",
                    _docx.read_bytes(), file_name=_studio_dl_name(".docx"),
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            else:
                st.info("No resume.docx in this application folder — re-run "
                        "`python -m job_bot.generate` for it.")

st.sidebar.markdown("### Job Bot")
st.sidebar.caption("Personal AI career platform")
st.sidebar.divider()
st.sidebar.markdown("**Command-line modules**")
st.sidebar.markdown(
    "- `build_profile` — ingest docs\n"
    "- `score_job` — reverse ATS\n"
    "- `decide` — network vs cold\n"
    "- `applications` — application tracker\n"
    "- `growth` — skills/certs/projects plan\n"
    "- `newgrad` — remote interns + S27 FT\n"
    "- `search_jobs` — find + route\n"
    "- `generate` — tailored resume\n"
    "- `network` — outreach drafts\n"
    "- `interview` — mock prep\n"
    "- `apply` — autofill\n"
    "- `pipeline` — inbox/prep/thank-you/brief/queue\n"
    "- `offers` — offer comparison\n"
    "- `salary` — market range\n"
    "- `linkedin_optimizer` — profile audit\n"
    "- `cover_ab` — A/B cover letters\n"
    "- `notify` — fresh-job alerts\n"
    "- `recording` — answer analysis\n"
    "- `network_map` — coverage map"
)
st.sidebar.divider()
st.sidebar.caption(f"DB: {DB_PATH}")
