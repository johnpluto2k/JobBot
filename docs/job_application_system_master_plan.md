# Agentic Job Application System â€” Master Plan

John's personal AI-powered career intelligence platform Last updated: June 2026

> **Build status: ALL 9 PHASES + ALL 15 RECOMMENDATIONS COMPLETE âœ…** â€” knowledge
> base, reverse ATS scorer, network-vs-cold-apply, tailored resume/cover-letter
> generator, job search + routing, networking/outreach, interview prep + mock,
> application autofill, and a 9-tab Streamlit control center; plus the full
> recommendations layer (tracking, email/calendar, thank-you, salary, LinkedIn
> optimizer, referral packs, company brief, rejection + cover-letter analytics,
> notifications, recording analysis, offer comparison, alumni map, ATS
> auto-detect). 52 modules, all importing clean. See [`README.md`](README.md).
>
> Quick tour: `build_profile` â†’ `score_job` â†’ `decide` â†’ `generate` â†’
> `search_jobs` â†’ `network` â†’ `interview` â†’ `apply` â†’ `streamlit run job_bot/dashboard.py`.

---

## Table of Contents

1. [Project Overview](#project-overview)  
2. [The Six Core Modules](#the-six-core-modules)  
3. [System Architecture](#system-architecture)  
4. [Build Phases](#build-phases)  
5. [Tech Stack](#tech-stack)  
6. [GitHub Repos to Reference](#github-repos-to-reference)  
7. [Python Libraries](#python-libraries)  
8. [Skills to Learn](#skills-to-learn)  
9. [Geographic & Platform Targeting](#geographic--platform-targeting)  
10. [Hiring Process Intelligence](#hiring-process-intelligence)  
11. [Interview Prep Agent](#interview-prep-agent)  
12. [Master Resume System](#master-resume-system)  
13. [Career Manager Agent](#career-manager-agent)  
14. [Recommendations & Additions](#recommendations--additions)  
15. [Claude Code Kickoff Prompt](#claude-code-kickoff-prompt)

---

## Project Overview

A personal AI-powered job search system that handles everything from finding a job posting to walking out of an interview with an offer. It knows your full background deeply, scores and tailors your resume per job, decides whether to network or cold apply, maps the hiring process for every firm type, and runs full mock interview sessions â€” all automatically.

**The system is not just a tool. It is a career operating system.**

---

## The Six Core Modules

### 1\. Personal Knowledge Base

Reads all your documents â€” resume, transcript, cover letters, project writeups â€” and builds a structured JSON profile of everything you've done. This is the source of truth every other module references. It knows which version of you to present: audit John, analytics John, or tech/FinTech John.

### 2\. Reverse ATS Scoring Engine

You paste a job description, the system tells you:

- Your match score against that specific JD  
- Which keywords are missing and where to add them  
- Whether your bullet points are quantified enough  
- Which ATS platform the company uses (Workday, Taleo, iCIMS, Greenhouse, Lever, SuccessFactors) and scores accordingly  
- A ranked gap analysis: exactly what to fix, in order of impact

### 3\. Network vs. Cold Apply Decision Engine

Calculates whether cold applying is good enough or whether you need a referral first. Scores based on:

- Estimated applicant volume  
- Role seniority and specificity  
- Your connection strength (UMD alum, Pi Sigma Epsilon, IEFS, 1st/2nd degree LinkedIn)  
- Recruiter contact availability  
- Time since posting

**Verdicts:**

- ðŸŸ¢ Cold apply â€” strong enough resume, manageable competition  
- ðŸŸ¡ Apply \+ network in parallel â€” submit now, reach out simultaneously  
- ðŸ”´ Network first â€” high competition, strong connections exist; secure a referral before applying

### 4\. Tailored Application Generator

For every job, generates:

- A rewritten, one-page resume pulling from the master resume database  
- A tailored cover letter mirroring JD language  
- An application checklist for any extra materials  
- Never fabricates â€” only repositions and rewords real experience

### 5\. Hiring Process Intelligence Layer

For every company type, maps:

- Number of rounds and formats  
- What each round actually evaluates (not just what they say)  
- Average timeline from application to offer  
- Prep checklist per stage  
- Red flags to watch (exploding offers, internally-decided roles, etc.)  
- Post-application follow-up cadence

### 6\. Interview Prep & Mock Interview Agent

- Builds a personal story bank from your actual documents in STAR+ format  
- Trains all question types: behavioral, fit, technical, case, HireVue, curveball  
- Runs full mock interviews in character as specific interviewers (Deloitte manager, Goldman analyst, Google PM)  
- Scores every answer with a rubric  
- Tracks weak spots and drills those specifically  
- Three mock modes: Drill, Full Round Simulation, Stress Test

---

## System Architecture

â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”

â”‚           PERSONAL KNOWLEDGE BASE        â”‚

â”‚  Resume Â· Transcript Â· Cover Letters     â”‚

â”‚  Skills Â· Orgs Â· Target Firms Â· Goals   â”‚

â”‚  (Structured JSON profile of "you")      â”‚

â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

                 â”‚

     â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”

     â”‚   JOB INGESTION LAYER  â”‚

     â”‚  LinkedIn Â· Indeed     â”‚

     â”‚  Handshake Â· Workday   â”‚

     â”‚  (monitor \+ scrape)    â”‚

     â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

                 â”‚

     â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”

     â”‚      JD INTELLIGENCE ENGINE        â”‚

     â”‚  Parse role Â· Extract keywords     â”‚

     â”‚  Classify type Â· Identify ATS used â”‚

     â”‚  Flag geographic tier              â”‚

     â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

                 â”‚

     â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”

     â”‚    REVERSE ATS SCORING ENGINE      â”‚

     â”‚  (integrate ats-screener logic)    â”‚

     â”‚  Platform-specific scores          â”‚

     â”‚  Keyword gap Â· Format check        â”‚

     â”‚  Quantification Â· Alignment        â”‚

     â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

            â”‚                  â”‚

  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”

  â”‚  TAILORING     â”‚  â”‚  NETWORK vs COLD      â”‚

  â”‚  ENGINE        â”‚  â”‚  APPLY DECISION       â”‚

  â”‚  Resume rewriteâ”‚  â”‚  ENGINE               â”‚

  â”‚  Cover letter  â”‚  â”‚  Score matrix â†’       â”‚

  â”‚  Per-role      â”‚  â”‚  ðŸŸ¢ ðŸŸ¡ ðŸ”´ verdict     â”‚

  â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

           â”‚                  â”‚

  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”

  â”‚         NETWORKING INTELLIGENCE          â”‚

  â”‚  Find UMD alums Â· PSE connections        â”‚

  â”‚  Score warmth Â· Draft outreach           â”‚

  â”‚  Track follow-up cadence                 â”‚

  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

                   â”‚

  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”

  â”‚      APPLICATION AUTOMATION (Phase 7\)    â”‚

  â”‚  Browser agent â†’ form fill               â”‚

  â”‚  Easy Apply Â· Workday portals            â”‚

  â”‚  Track status per platform               â”‚

  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

---

## Build Phases

| Phase | What Gets Built | Key Dependency |
| :---- | :---- | :---- |
| **1** | Document ingestion \+ personal knowledge base (structured JSON from your documents) | PyMuPDF \+ python-docx \+ Claude API |
| **2** | JD parser \+ reverse ATS scorer (integrate ats-screener platform logic) | spaCy \+ sentence-transformers \+ ats-screener repo |
| **3** | Network vs. cold apply decision engine | SQLite scoring matrix \+ LinkedIn connection data |
| **4** | Master resume database \+ tailored resume/cover letter generator | Pydantic schema \+ python-docx \+ jinja2 |
| **5** | Geographic \+ platform routing layer | JobSpy \+ custom tier logic |
| **6** | Networking intelligence \+ outreach drafter | Claude API \+ LinkedIn data |
| **7** | Interview prep agent (story bank \+ mock interviews) | Claude API \+ LangGraph |
| **8** | Application automation â€” browser agent for form filling | Playwright \+ Claude browser tool |
| **9** | Dashboard UI | Streamlit |

---

## Tech Stack

Language:          Python 3.11+

AI Brain:          Claude API (claude-sonnet-5) via langchain-anthropic

Agent Framework:   LangChain \+ LangGraph

Knowledge Base:    ChromaDB (local vector store)

Document Parsing:  pymupdf4llm (PDF) \+ python-docx (DOCX)

NLP Layer:         spaCy \+ sentence-transformers

Job Scraping:      JobSpy (primary) \+ Playwright (fallback/automation)

ATS Reference:     sunnypatell/ats-screener logic

Resume Output:     python-docx \+ reportlab

Data Schema:       Pydantic models

Job Tracking DB:   SQLite

UI:                Streamlit

Environment:       python-dotenv

Version Control:   Git

---

## GitHub Repos to Reference

| Repo | Purpose | URL |
| :---- | :---- | :---- |
| **sunnypatell/ats-screener** | Simulates Workday, Taleo, iCIMS, Greenhouse, Lever, SuccessFactors scoring â€” primary ATS engine | `https://github.com/sunnypatell/ats-screener` |
| **srbhr/Resume-Matcher** | Semantic resume-to-JD matching, reverse ATS logic, keyword extraction | `https://github.com/srbhr/Resume-Matcher` |
| **xitanggg/open-resume** | ATS-friendly resume builder and parser â€” study its formatting rules | `https://github.com/xitanggg/open-resume` |
| **olyaiy/resume-lm** | Open-source AI resume builder with Claude API support â€” closest to what you're building | `https://github.com/olyaiy/resume-lm` |
| **speedyapply/JobSpy** | Scrapes LinkedIn, Indeed, Glassdoor, Google, ZipRecruiter concurrently | `https://github.com/speedyapply/JobSpy` |
| **GodsScion/Auto\_job\_applier\_linkedIn** | LinkedIn Easy Apply automation with Chrome | `https://github.com/GodsScion/Auto_job_applier_linkedIn` |
| **spinlud/py-linkedin-jobs-scraper** | LinkedIn job scraper with headless browser, extracts full job details | `https://github.com/spinlud/py-linkedin-jobs-scraper` |
| **Hunterdii/Smart-AI-Resume-Analyzer** | ATS scoring across 7 categories with keyword and skills gap analysis | `https://github.com/Hunterdii/Smart-AI-Resume-Analyzer` |

---

## Python Libraries

### Document Parsing

pip install pymupdf4llm          \# PDF parsing optimized for LLM use

pip install python-docx          \# DOCX reading and writing

pip install docx2txt             \# Quick DOCX text extraction

pip install pdfminer.six         \# Alternative PDF text extraction

pip install pytesseract          \# OCR for scanned PDFs

pip install Pillow               \# Image processing (companion to tesseract)

### NLP & Resume Intelligence

pip install spacy

python \-m spacy download en\_core\_web\_sm

pip install nltk

pip install sentence-transformers    \# Semantic similarity beyond keywords

pip install scikit-learn             \# TF-IDF scoring, cosine similarity

### AI Agent Framework

pip install langchain

pip install langchain-anthropic      \# Claude integration

pip install langchain-community      \# Tools including web search

pip install langgraph                \# Stateful multi-agent workflows

### Vector Database

pip install chromadb                 \# Local vector DB, no server needed

pip install pinecone-client          \# Cloud option for cross-device persistence

### Job Board Scraping & Automation

pip install python-jobspy            \# LinkedIn, Indeed, Glassdoor, ZipRecruiter

pip install playwright               \# Browser automation for form filling

pip install selenium                 \# Alternative browser automation

pip install beautifulsoup4           \# HTML parsing

pip install requests                 \# HTTP requests

### Resume Output

pip install python-docx              \# Write tailored DOCX resumes

pip install reportlab                \# Generate PDFs programmatically

pip install jinja2                   \# Template engine for resume formatting

pip install weasyprint               \# HTML-to-PDF (alternative to reportlab)

### Data, Storage & Validation

pip install pandas

pip install pydantic                 \# Master resume schema, job data models

pip install python-dotenv            \# Environment variables and API keys

\# sqlite3 is built into Python â€” no install needed

### UI

pip install streamlit                \# Dashboard for the full system

---

## Skills to Learn

### Tier 1 â€” Must Have (Build Phase 1-4)

| Skill | You Already Have | Gap to Close |
| :---- | :---- | :---- |
| Python intermediate | âœ… INST 326 | Decorators, async, file I/O |
| JSON \+ Pydantic | Partial | Pydantic v2 models and validation |
| Prompt engineering | Partial | System prompts, few-shot, chain-of-thought |
| Git / GitHub | âœ… INST 326 | Branching strategies for multi-phase build |
| SQL basics | âœ… INST 327 | SQLite-specific syntax |

### Tier 2 â€” Build As You Go (Phase 5-7)

| Skill | Where to Learn |
| :---- | :---- |
| LangChain \+ LangGraph | LangChain Academy (free at academy.langchain.com) |
| RAG pipelines | LangChain docs \+ ChromaDB docs |
| Playwright / Selenium | Playwright Python official docs |
| Streamlit | streamlit.io/docs (30 min to learn basics) |
| REST API consumption | Python `requests` docs |

### Tier 3 â€” Peak Version (Phase 8-9)

| Skill | Where to Learn |
| :---- | :---- |
| Vector embeddings | sentence-transformers docs \+ HuggingFace |
| FastAPI | fastapi.tiangolo.com |
| Docker | Docker getting started guide |
| spaCy NLP | spacy.io/usage |
| Async Python | Python asyncio docs |

---

## Geographic & Platform Targeting

### Market Tiers

| Tier | Markets | System Behavior |
| :---- | :---- | :---- |
| **Tier 1** | DMV (DC, MD, VA) | Highest priority â€” dense with Big 4, federal consulting, Booz Allen, financial institutions |
| **Tier 2** | NYC Â· SF Â· Chicago Â· Boston | Major market â€” Big 4, banking, tech, FinTech HQs |
| **Tier 3** | LA Â· San Diego Â· Seattle | Open to relocation â€” strong tech presence |
| **Remote** | Anywhere | Flagged separately â€” hybrid roles at Tier 1/2 firms |

### Platform Strategy

| Platform | Strategy |
| :---- | :---- |
| **LinkedIn Easy Apply** | High volume, low friction, less tailoring needed |
| **Company Workday/Taleo portals** | High stakes, full tailoring required, ATS platform identified from URL |
| **Handshake** | Critical â€” Big 4 and Fortune 500 recruit heavily from UMD here |
| **Indeed** | Best scraper, no rate limiting, good for monitoring |
| **Glassdoor** | Salary data \+ job postings |
| **WayUp / Forage** | Entry-level specific, worth monitoring |

---

## Hiring Process Intelligence

### By Firm Type

#### Big 4 (Deloitte Â· PwC Â· EY Â· KPMG)

**Timeline: 3â€“6 weeks**

1. ATS screen (Workday for Deloitte, Taleo for PwC)  
2. HireVue one-way video â€” 3â€“5 behavioral questions, AI-scored  
3. Recruiter phone screen â€” 15â€“30 min, fit check  
4. First round â€” 30â€“45 min, behavioral \+ "why this firm"  
5. Super Day â€” 2â€“4 back-to-back interviews, behavioral \+ case elements  
6. Offer â†’ background check â†’ cohort start (usually September)

**ATS Platforms:**

- Deloitte â†’ Workday  
- PwC â†’ Taleo  
- EY â†’ Workday  
- KPMG â†’ Workday

#### Investment Banks (Goldman Â· JPMorgan Â· Morgan Stanley)

**Timeline: 6â€“10 weeks**

1. ATS screen â€” GPA cutoffs are real (3.5+)  
2. HireVue \+ numerical reasoning test  
3. First round â€” technical questions begin (DCF, 3-statement linkage)  
4. Superday â€” 5â€“8 back-to-back interviews, technical-heavy \+ behavioral  
5. Offer â€” often exploding (24â€“48 hrs to accept)

#### Tech Companies (Google Â· Meta Â· Microsoft Â· Stripe)

**Timeline: 4â€“8 weeks**

1. Recruiter screen â€” 15â€“30 min, light technical warmup  
2. Technical phone screen â€” SQL/coding/case depending on role  
3. Take-home assignment â€” common for analytics and finance roles  
4. Virtual on-site loop â€” 4â€“6 interviews (coding, system design, behavioral, hiring manager)  
5. Offer with level (L3/L4) â€” negotiation expected

#### FinTech (Stripe Â· Plaid Â· Robinhood Â· Block)

**Timeline: 2â€“4 weeks (faster, less formal)**

1. Recruiter screen  
2. Hiring manager interview â€” conversational, culture-focused  
3. Take-home or case  
4. Team loop â€” 3â€“4 interviewers  
5. Offer â€” more negotiation room

#### Fortune 500 Corporate Finance / Internal Audit

**Timeline: 3â€“5 weeks**

1. ATS screen \+ recruiter call  
2. Hiring manager interview â€” behavioral \+ situational  
3. Panel or loop â€” 3â€“5 interviewers, functional \+ behavioral  
4. Offer â€” RSUs at larger companies, more negotiation room than Big 4

---

## Interview Prep Agent

### The Four Skill Layers

Layer 4: EXECUTIVE PRESENCE       â€” Confidence, composure, curveballs

Layer 3: STRATEGIC POSITIONING    â€” Your narrative, differentiation, fit

Layer 2: FRAMEWORKS & STRUCTURE   â€” STAR+, case frameworks, mental models

Layer 1: QUESTION KNOWLEDGE       â€” What they'll ask (most people stop here)

### Question Types Covered

| Type | Description | Firms |
| :---- | :---- | :---- |
| **Behavioral** | STAR+ format, competency-based | Universal |
| **Fit & Motivational** | Why firm, why role, walk me through your resume | Big 4, banking, corporate |
| **Technical** | Financial statements, DCF, SQL, Python depending on track | Banking, tech, FinTech |
| **Case** | Market sizing, profitability, market entry, M\&A | Consulting, Big 4 advisory |
| **HireVue** | One-way video, AI-scored, 2â€“3 min answers | Big 4, banking |
| **Curveball** | "Sell me this pen", estimation questions, stress tests | Banking, tech |
| **Your Questions** | What you ask them â€” signals prep and curiosity | All |

### STAR+ Formula

- **S**ituation â€” 1â€“2 sentences of context  
- **T**ask â€” your specific responsibility  
- **A**ction â€” what YOU did (not "we"), 60% of answer  
- **R**esult â€” quantified whenever possible  
- **\+Reflection** â€” what you learned (Big 4 and consulting love this)  
- **\+Connection** â€” one sentence linking it to the role

### Mock Interview Modes

| Mode | Description |
| :---- | :---- |
| **Drill Mode** | Single Q\&A with instant rubric scoring |
| **Full Round Simulation** | 30â€“45 min session, agent plays specific interviewer in character |
| **Stress Test Mode** | Agent interrupts, challenges, pushes back mid-answer |
| **Story Bank Builder** | Extracts 8â€“10 strongest stories from your docs, maps to competencies |

### Your Story Bank (Pre-Mapped)

| Experience | Competencies It Covers |
| :---- | :---- |
| VP of Finance, IEFS | Leadership, ownership, financial analysis, stakeholder management |
| Kim's Industrial Grill | Real-world finance, initiative, quantitative results |
| Pi Sigma Epsilon | Teamwork, professionalism, networking, event execution |
| Python Cognitive Distortion Identifier | Technical problem solving, initiative, building from scratch |
| SQL Database Project (INST 327\) | Technical skills, collaboration, data management |
| Find My Sport App (INST 311\) | Project management, cross-functional teamwork, product thinking |
| Case Competition (AI \+ healthcare) | Strategic thinking, presentation, business judgment |
| This Job Application System | Initiative, technical ambition, self-direction â€” FinTech/tech gold |

---

## Master Resume System

### The Google XYZ Formula

**"Accomplished \[X\] as measured by \[Y\] by doing \[Z\]"**

Every bullet in the master resume is written in this format. The system selects and reorders bullets per job â€” never fabricates, only repositions.

### Master Resume â†’ Tailored Resume Flow

Master Resume DB (all experience, XYZ bullets, keyword tags, strength scores)

       â†“

JD Input â†’ keyword and skill extraction

       â†“

Bullet Selection Engine (picks highest-relevance bullets above score threshold)

       â†“

Bullet Rewrite Engine (mirrors JD language, preserves your real facts)

       â†“

Resume Formatter (enforces all format rules)

       â†“

ATS Compatibility Check (must hit threshold before export)

       â†“

Final tailored resume â†’ PDF \+ DOCX export

### Resume Format Rules

- One page, always, no exceptions for entry level  
- No tables, columns, text boxes, or graphics (ATS choke points)  
- Standard fonts only: Calibri, Garamond, Arial, or Times at 10â€“12pt  
- Consistent past tense for completed roles, present for current  
- Every bullet starts with a strong action verb â€” never "responsible for" or "helped with"  
- No personal pronouns  
- Margins no smaller than 0.5 inches  
- No photos, icons, or color beyond black

### Resume Structure (Top to Bottom)

1. Header â€” name, phone, email, LinkedIn, GitHub, city/state only  
2. Education â€” UMD, double major, GPA if 3.5+, relevant coursework, graduation date  
3. Experience â€” reverse chronological, 3â€“5 XYZ bullets per role  
4. Leadership & Activities â€” IEFS VP Finance, Pi Sigma Epsilon, other orgs  
5. Projects â€” 2â€“3 most relevant, selected per role  
6. Skills â€” technical only, grouped by category

---

## Career Manager Agent

### Your Four Career Quadrants

                    MORE TECHNICAL

                          â”‚

          Data/AI â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€ Software Eng

          Analytics       â”‚         (gap to close)

          FinTech Eng     â”‚

                          â”‚

  FINANCE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ TECH

                          â”‚

          Audit/Risk â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€ IT Audit

          FP\&A            â”‚         Cybersecurity

          Corp Finance    â”‚         ERP Consulting

                          â”‚

                    MORE FINANCE

### Career Path Analysis

| Path | Fit Level | Key Gap | Entry Point |
| :---- | :---- | :---- | :---- |
| **IT Audit / Technology Risk** | â­â­â­â­â­ | Minimal â€” best near-term fit | Big 4 Technology Risk (EY FSO, Deloitte Risk & Financial Advisory) |
| **FinTech Operations/Risk** | â­â­â­â­ | Product thinking, SQL depth | Stripe, Plaid, Robinhood, Block |
| **Data Analytics / FP\&A** | â­â­â­â­ | BI tools (Tableau, Power BI) | Fortune 500 internal analytics |
| **AI \+ Finance** | â­â­â­ | Python depth, ML fundamentals | Financial services AI teams (2â€“3 yrs out) |
| **Big 4 Audit** | â­â­â­ | No return offer pipeline | UMD campus recruiting \+ networking |
| **Investment Banking** | â­â­ | GPA cutoffs, technical depth | Regional boutiques first |

---

## Recommendations & Additions

These are things not yet in the plan that would meaningfully improve the system:

### ðŸ”´ High Priority â€” Add Before Building

**1\. Application Tracking Dashboard** A SQLite \+ Streamlit dashboard that tracks every application: company, role, date applied, platform, ATS score, network verdict, current stage, follow-up dates, outcome. Without this, the system generates applications with no visibility into what's working. This is the control center.

**2\. Email Integration (Gmail MCP)** You already have Gmail connected as an MCP. The system should monitor your inbox for recruiter responses, interview invites, and rejections automatically â€” updating the tracking dashboard and triggering the right next action (schedule prep, send thank-you, follow up).

**3\. Calendar Integration (Google Calendar MCP)** Auto-schedule interview prep sessions when an interview is booked. If you get a Super Day in 2 weeks, the system should generate a 14-day prep plan and populate your calendar with daily prep blocks. You already have Google Calendar connected.

**4\. Thank-You Email Generator** Post-interview, the system drafts a personalized thank-you email for each interviewer based on what was discussed. This is a high-leverage, low-effort touch that most candidates skip. Should auto-draft within 1 hour of interview end time.

**5\. Salary Intelligence Layer** Before applying or negotiating, the system should pull salary ranges from Glassdoor, Levels.fyi (for tech), and LinkedIn Salary for that specific role \+ location \+ experience level. This feeds directly into your negotiation prep and helps you avoid accepting below market.

### ðŸŸ¡ Medium Priority â€” Add in Later Phases

**6\. LinkedIn Profile Optimizer** Your resume and LinkedIn profile should mirror each other strategically. A module that audits your LinkedIn profile against the same JD scoring logic and suggests specific edits â€” headline, about section, experience bullets, skills section â€” would significantly improve inbound recruiter traffic.

**7\. Referral Request Template Engine** When the system gives a ðŸ”´ "network first" verdict, it should auto-generate a personalized referral request message for each specific connection â€” not a generic template, but one that references shared background (UMD, PSE, IEFS) and the specific role. This makes networking feel less awkward and more systematic.

**8\. Company Research Brief** Before any interview, auto-generate a 1-page company brief: recent news, financials (public companies), key leadership, the specific team's recent projects, and potential interview topics based on current events. This feeds directly into your "why this firm" prep.

**9\. Rejection Analysis Module** When you get rejected, the system logs it and over time surfaces patterns: which role types are rejecting you most, at which stage, and with what ATS score. This turns rejections into data that improves the system's targeting over time.

**10\. Cover Letter A/B Testing** Track which cover letter variations (more formal vs. more conversational, leading with finance vs. tech angle) correlate with better response rates. Over time the system learns your most effective voice for each firm type.

### ðŸŸ¢ Future / Peak Version

**11\. Notification System** Slack or SMS alert when a new job matching your criteria is posted under 24 hours ago (before it gets flooded with applicants). Time advantage matters enormously in competitive roles.

**12\. Interview Recording Analysis** For practice sessions, record yourself answering mock questions and have the system analyze: filler word frequency, answer length, STAR compliance, pacing, and specific phrases to cut or add. Turns subjective "practice" into measurable improvement.

**13\. Offer Comparison Engine** When you have multiple offers, the system builds a structured comparison: base salary, bonus, equity, benefits, career trajectory, location cost-of-living adjustment, company growth rate, and your personal priority weighting. Removes emotion from one of the most important decisions.

**14\. Alumni Network Map** Visualize your UMD \+ PSE \+ IEFS network mapped onto your target companies. Show which firms have the most warm connections, which have the weakest coverage, and who specifically to reach out to first. Makes the networking strategy visible.

**15\. ATS Platform Auto-Detection** When the system scrapes a job URL, auto-detect the ATS platform from the URL structure or page source. Workday URLs contain `myworkdayjobs.com`, Greenhouse contains `boards.greenhouse.io`, Lever contains `jobs.lever.co`. This routes the resume to the correct scoring mode automatically.

---

## Claude Code Kickoff Prompt

Copy and paste this as your first message when starting Claude Code:

I'm building an agentic job application system in Python. 

STACK:

\- AI: Claude API (claude-sonnet-5) via langchain-anthropic

\- Agent framework: LangChain \+ LangGraph

\- Vector DB: ChromaDB

\- Document parsing: pymupdf4llm (PDF) \+ python-docx (DOCX)

\- NLP: spaCy \+ sentence-transformers

\- Job scraping: JobSpy

\- Browser automation: Playwright

\- Data schema: Pydantic v2

\- Job tracking: SQLite

\- UI: Streamlit

\- Environment: python-dotenv

REFERENCE REPOS:

\- sunnypatell/ats-screener (ATS platform-specific scoring logic)

\- speedyapply/JobSpy (job ingestion)

\- srbhr/Resume-Matcher (semantic matching)

\- olyaiy/resume-lm (overall architecture reference)

PHASE 1 GOAL:

Build a document ingestion pipeline that:

1\. Reads all PDF and DOCX files from a specified folder

2\. Extracts structured data using spaCy and Claude API

3\. Builds a Pydantic master profile schema with fields for:

   \- Personal info

   \- Education (school, major, GPA, graduation date, relevant coursework)

   \- Work experience (role, org, dates, XYZ-format bullets, keyword tags, strength scores)

   \- Leadership and activities

   \- Projects (name, description, technologies, outcomes)

   \- Skills (grouped by category: technical, financial, soft)

   \- Target roles and firms

4\. Stores the profile in ChromaDB for semantic querying

5\. Exports a master\_profile.json as the system's source of truth

Here are my documents: \[UPLOAD FILES HERE\]

Start with the folder ingestion script and Pydantic schema definition.

---

*This document should be updated after each build phase is completed. Treat it as the living source of truth for the project.*

---

## Build Log

### Phase 1 â€” Document Ingestion + Personal Knowledge Base âœ… (June 2026)

Built the `job_bot` Python package that turns John's documents into the
system's structured source of truth.

- **Ingestion** (`ingest.py`): reads PDF (pymupdf4llm), DOCX (python-docx,
  including tables), and TXT/MD; classifies each as resume / cover_letter /
  project / transcript; dumps raw text to `data/raw_text/`.
- **Schema** (`models.py`): Pydantic v2 `MasterProfile` â€” personal info,
  education, experience (XYZ bullets with keyword tags + strength scores),
  leadership, projects, skills (categorized), targets, certifications.
- **Extraction** (`extract.py`): Claude API extractor (`claude-sonnet-5`)
  when `ANTHROPIC_API_KEY` is set, plus a markdown-aware **heuristic fallback**
  that parses real resumes with no key/offline (handles marked + unmarked
  bullets and pipe/tab/split header layouts).
- **Vector store** (`store.py`): flattens the profile into chunks and embeds
  them in a local ChromaDB collection for semantic querying; degrades
  gracefully if ChromaDB is unavailable.
- **Pipeline** (`build_profile.py`): `python -m job_bot.build_profile` â†’
  writes `data/master_profile.json`.

Verified against John's 16 documents: extracted 3 work roles (9 bullets),
2 leadership entries, the Pantry Plate project, 4 skill groups, education
(UMD double major, GPA 3.5, Dec 2027), and CPA eligibility. Semantic query
("audit and internal controls") correctly surfaces the TerpTax and Kim's
Industrial Grill bullets.

**Next:** Phase 2 â€” JD parser + reverse ATS scorer.

### Phase 2 â€” JD Parser + Reverse ATS Scoring Engine âœ… (June 2026)

Paste/point at a job description; the system scores the master profile against
it the way an ATS would and returns a ranked, actionable gap analysis.

- **Skills ontology** (`skills_ontology.py`): canonical skills + alias/synonym
  lists, role-type signals, market-tier geography, and companyâ†’ATS mapping.
- **JD parser** (`jd_parser.py`): extracts title, company, location, required
  vs preferred keywords, role type, seniority, GPA cutoff, years, geographic
  tier, and remote flag. Heuristic-first with optional Claude enrichment.
- **ATS platforms** (`ats_platforms.py`): detects Workday / Taleo / iCIMS /
  Greenhouse / Lever / SuccessFactors from URL, posting text, or company, each
  with its own scoring weights and candidate-facing tips.
- **Similarity** (`similarity.py`): pure-Python TF-IDF cosine (no torch/spaCy
  needed); auto-upgrades to sentence-transformers if installed.
- **Scoring engine** (`ats_engine.py`): platform-weighted overall score from
  four subscores â€” keyword coverage (required 1.0 / preferred 0.5), title
  alignment, quantification, content similarity â€” plus a ranked gap analysis
  ("add keyword X to section Y, +Z pts") and a verdict band.
- **CLI** (`score_job.py`): `python -m job_bot.score_job --file jd.txt
  [--url ...] [--no-llm] [--json]`; prints a report and saves
  `data/score_<role>.json`.

Verified on a Deloitte IT-Risk JD (detected Workday, Tier-1 DMV, GPA 3.2,
role = IT Audit/Technology Risk; 12 matched / 8 missing keywords; honest
"add if you genuinely have it" guidance for SOX/IT-audit gaps) and a Stripe
Data-Analyst JD via a Greenhouse URL (auto-detected Greenhouse, remote, higher
title alignment, results-weighted scoring).

**Next:** Phase 3 â€” Network vs. cold-apply decision engine.

### Phase 3 â€” Network vs. Cold-Apply Decision Engine âœ… (June 2026)

Given a JD, decides whether to cold-apply, apply-and-network, or network-first â€”
backed by a SQLite store of your connections.

- **SQLite store** (`db.py`): `connections` and `decisions` tables in
  `data/job_bot.db` (also seeds the future application-tracking dashboard).
- **Connections** (`connections.py`): imports a LinkedIn `Connections.csv`
  (with an optional `Relationship` column for warmer ties: recruiter / pse /
  umd / iefs / first_degreeâ€¦), normalizes company names, and scores per-company
  networking leverage with diminishing returns + a recruiter boost.
- **Decision engine** (`decision_engine.py`): estimates competition/applicant
  volume (company prestige, seniority, remote, niche-vs-broad role, posting
  recency), pulls resume strength from the Phase 2 ATS score, and combines them
  with connection leverage into a ðŸŸ¢/ðŸŸ¡/ðŸ”´ verdict, rationale, confidence, and
  concrete next actions (who to contact, apply timing).
- **CLI** (`decide.py`): `python -m job_bot.decide --file jd.txt [--url ...]
  [--posted YYYY-MM-DD] [--company ...]`; also
  `--import-connections Connections.csv` and `--list-connections`. Each run is
  logged to the `decisions` table.

Verified: Deloitte IT-Risk JD with a seeded recruiter + PSE + UMD contact â†’
ðŸ”´ Network-first (84% leverage, 59% competition, "reach the recruiter before
applying"); a low-prestige firm with no contacts â†’ ðŸŸ¢ Cold apply. Fixing
company extraction (known-employer + "Company â€” Location" detection) was key,
since prestige and connection lookup both key off the company name.

**Next:** Phase 4 â€” Master resume DB + tailored resume/cover-letter generator.

### Phase 4 â€” Tailored Resume + Cover Letter Generator âœ… (June 2026)
`tailor.py` selects + reorders the strongest JD-relevant bullets (never
fabricates), `render_docx.py` / `render_pdf.py` produce an ATS-clean one-page
resume, and `cover_letter.py` mirrors the JD using only real facts. CLI
`python -m job_bot.generate --file jd.txt` writes a full package to
`data/applications/<company>_<role>/` (resume.docx+pdf, cover_letter, checklist)
and reports the beforeâ†’after ATS lift. Claude rewrites bullets/letters when a
key is set; otherwise originals are kept verbatim.

### Phase 5 â€” Geographic + Platform Routing âœ… (June 2026)
`routing.py` classifies market tier, recommends a platform/tailoring strategy,
and computes a priority score (tier Ã— fit Ã— recency). `jobsearch.py` wraps
JobSpy (LinkedIn/Indeed/Glassdoor/Google/ZipRecruiter) and scores+routes each
posting into the SQLite `jobs` table. CLI `python -m job_bot.search_jobs --term
"IT audit" --location "Washington, DC"` â€” verified pulling live Indeed postings
ranked by priority. (On Python 3.14, JobSpy installed via `--no-deps`.)

### Phase 6 â€” Networking Intelligence + Outreach âœ… (June 2026)
`networking.py` finds warm contacts at a company, drafts personalized messages
(`outreach.py` â€” referral request / intro / follow-up, referencing shared
UMD/PSE/IEFS ties), and schedules a follow-up cadence into the `outreach` table.
CLI `python -m job_bot.network --company Deloitte --role "..."` and `--pending`.

### Phase 7 â€” Interview Prep + Mock Interview âœ… (June 2026)
`story_bank.py` extracts STAR+ stories mapped to competencies; `questions.py` is
a curated bank by type (behavioral/fit/technical/case/HireVue/curveball/your-
questions) and firm; `rubric.py` scores answers (STAR completeness,
quantification, ownership, length, fillers). CLI `python -m job_bot.interview
--story-bank | --questions | --drill --answer "..." | --mock --firm big4`.
Live in-character mock interviewer runs when a key is set.

### Phase 8 â€” Application Autofill âœ… (June 2026)
`autofill.py` maps the profile to common application fields and, via Playwright
+ Chromium, opens an application URL and fills matching fields by label â€”
**never auto-submitting** (assisted, ToS-safe). Falls back to a copy-paste
answer sheet without a browser. CLI `python -m job_bot.apply --url "..."
[--headless --screenshot]` and `--status applied --job-url ...` for tracking.
Verified filling a 9-field form headless.

### Phase 9 â€” Streamlit Dashboard âœ… (June 2026)
`dashboard.py` is the control center over `master_profile.json` + `job_bot.db`:
Overview (profile), Pipeline (ranked jobs + decision log), Network (connections
+ outreach queue), and a live "Score a JD" tool running Phases 2â€“3 inline. Run
with `streamlit run job_bot/dashboard.py`. Verified via Streamlit's AppTest
harness (executes clean, real metrics).

---

## Environment notes (Python 3.14)

The whole stack runs on Python 3.14. Two install quirks were handled:
- **JobSpy** pins `numpy==1.26.3` (no 3.14 wheel) â†’ install with `--no-deps`
  and add its runtime deps; numpy 2.x / pandas already satisfy it at runtime.
- **ChromaDB / Playwright / Streamlit / reportlab / jinja2** install cleanly.
- Heavy NLP (sentence-transformers, spaCy) is optional â€” the system uses a
  pure-Python TF-IDF cosine and deterministic ontologies, and auto-upgrades to
  embeddings only if those libs are present.

Everything degrades gracefully without an `ANTHROPIC_API_KEY` (heuristic
extraction/rewriting) and without optional libs (vector store, scraping,
browser) â€” so a fresh clone runs end-to-end immediately.

---

## Post-build additions (June 2026)

### Repo cleanup + transcript ingestion
- Source documents moved out of the `job_bot/` package into a dedicated
  `documents/` folder (Professional Development, School Docs, School Related
  Stuff). `config._find_dir` auto-locates them in `documents/`, the project
  root, or `job_bot/` (legacy).
- `transcript.py` parses the UMD (Testudo) transcript and enriches education
  with verified cumulative GPA (3.51), 26 cleaned courses, semester academic
  honors (3 semesters, best 3.905), and in-progress courses. This lifted the
  Deloitte sample ATS match 48.6 â†’ 51.6.

### Tracking & Communications layer (Recommendations #1â€“#4)
- `inbox.py` â€” classifies recruiting emails (interview invite / assessment /
  recruiter reply / rejection / offer) â†’ next action, detects the company, and
  advances the matching job's status. Feedable by a Gmail export or the Gmail
  MCP.
- `prep_plan.py` â€” turns an interview date into a backward-planned, firm-tuned
  prep schedule; emits Google Calendar-compatible events + an `.ics` file, and
  seeds the `interviews` table.
- `thankyou.py` â€” post-interview thank-you drafts (template / Claude).
- `pipeline.py` CLI â€” `--inbox-demo`, `--classify-subject`, `--prep-plan`,
  `--thankyou`, and `--queue` (a unified "what needs action today" view across
  jobs, outreach, interviews, and tracked emails).
- New SQLite tables: `interviews`, `tracked_emails`.
- **Live Gmail/Calendar MCP** wiring is ready, but those tokens needed
  re-authorization at build time â€” re-auth to enable live inbox triage and
  one-click calendar push of the prep plan.

### Rejection Analysis (Recommendation #9) âœ…
- `rejections.py` + `rejections` table. Rejections auto-log from inbox triage
  (stage inferred from the job's current status) or via
  `pipeline --log-rejection --company X --stage first_round`, each enriched with
  the ATS score / market tier / platform already on file for that company.
- `pipeline --rejections` analyzes patterns: by stage, role type, ATS band, and
  tier, with avg ATS on rejected apps, plus insights and targeting
  recommendations (e.g. "4/5 rejections at the ATS screen â†’ raise match before
  applying"). Also surfaced in the dashboard Pipeline tab with charts.

### Company Research Brief (Recommendation #8) âœ…
- `company_research.py` + `pipeline --brief --company X --role "â€¦"`. Three
  layers, each degrading gracefully: (1) a curated firm knowledge base with real
  hiring-process / interview-style intel for John's target firms (Deloitte, PwC,
  EY, KPMG, Goldman Sachs, Capital One, + a generic fallback); (2) local context
  from SQLite â€” open roles, warm contacts, prior decisions/rejections at that
  company; (3) recent news fed via `--news` (from web search or a news MCP) and,
  with a key, summarized by Claude into a tight "why this firm" narrative.
- Emits a readable CLI brief + `data/brief_<company>.json`, and a "ðŸ¢ Company
  Brief" tab in the dashboard. Verified end-to-end on Deloitte with real
  Tech-Trends-2026 headlines pulled live via web search.

### Offer Comparison Engine (Recommendation #13) âœ…
- `offers.py` + `offers` table. Logs competing offers and ranks them by
  **cost-of-living-adjusted** total comp (base + bonus + equity + benefits,
  scaled by a per-city COL index where 100 = US average), weighted by the
  candidate's own money/growth/fit priorities. Pure logic, no API key.
- `python -m job_bot.offers --add ...` / `--compare [--w-money .7 ...]`. Verified
  on a 3-offer scenario where Goldman's $120k NYC offer correctly *loses* to a
  $104k remote Capital One offer once COL is applied. Surfaced in the dashboard's
  ðŸ’° Offers tab (interactive priority sliders) and the `--queue` action list.

### Front-end Action Center (Recommendation #1, deepened) âœ…
- The Streamlit dashboard gained a **ðŸ  Action Center** home tab â€” the single
  "what's going on right now" front end the user asked for: headline metrics
  (active apps, upcoming interviews, follow-ups due, open offers, rejections)
  plus live lists of interviews, follow-ups, unhandled recruiter emails, open
  offers, and top new postings. New ðŸ’° Offers and ðŸ¢ Company Brief tabs round out
  a 7-tab control center. 46 modules import clean; dashboard runs end-to-end.

### Salary Intelligence Layer (Recommendation #5) âœ…
- `salary.py`. Returns a COL-adjusted 25th/50th/75th-percentile total-comp range
  for a role + location + level from a curated baseline table (Big 4 audit/risk,
  IB, data/business/financial analyst), blended with live `--market` points fed
  from web search / a salary MCP. `assess_offer()` positions an offer against the
  range (below / low / at / above market) with an approximate percentile and a
  negotiation target.
- Verified against real Levels.fyi/Glassdoor figures for Deloitte Technology Risk
  Analyst (median ~$104k): correctly flagged an $84k cash offer as low-market
  (~27th pct). Surfaced in the dashboard ðŸ’° Offers tab; pairs with the offer
  engine for end-to-end negotiation prep.

### Alumni / Network Coverage Map (Recommendation #14) âœ…
- `network_map.py`. Aggregates connections by company into a coverage score
  (summed warmth + a relationship-diversity bonus), names the best person to
  reach first at each firm (warmth tie-broken by John-specific relationship
  affinity: recruiter > PSE/IEFS > UMD > 1st-degree), and runs a gap analysis
  flagging target / pipeline companies with weak or zero coverage.
- Verified: Deloitte leads (1.95 coverage, 3 contacts across PSE/recruiter/UMD â†’
  start with the recruiter). Surfaced in the dashboard ðŸ¤ Network tab as a chart
  + table.

### Referral Request Template Engine (Recommendation #7) âœ…
- The per-contact, affiliation-aware drafting already lived in `outreach.py`
  (referral / intro / follow-up referencing PSE / IEFS / UMD / TerpTax + the
  exact role). Closed the plan's two gaps: `network --all` drafts for *every*
  warm contact (a full "referral pack", not just the top 3), and `decide.py` now
  **auto-generates the referral pack on a ðŸ”´ network-first verdict** (or on
  `--referral-pack`), logging each draft to the outreach table on its cadence.
- Verified on the Deloitte JD: a network-first verdict auto-produced 3 tailored
  drafts â€” a direct recruiter intro, a "fellow Pi Sigma Epsilon member" referral
  ask, and a "fellow Terp" intro.

### LinkedIn Profile Optimizer (Recommendation #6) âœ…
- `linkedin_optimizer.py`. Audits the master profile against the same ATS
  keyword logic and emits paste-ready edits: a length-capped headline (cleans
  verbose degree strings), an About draft (Claude-polished with a key), a
  priority-ranked Skills list that front-loads JD keyword gaps, per-role bullet
  suggestions mirrored from the resume, and a recommendations checklist
  (skills count, Open-to-Work, LinkedIn URL).
- `python -m job_bot.linkedin_optimizer [--role ... | --file jd.txt]`; also a
  ðŸ’¼ LinkedIn dashboard tab. Verified against the Deloitte JD â€” surfaced the
  required gaps (communication, excel, it audit, risk management, SOX) and a
  124-char headline.

### Cover Letter A/B Testing (Recommendation #10) âœ…
- `cover_ab.py` + `cover_variants` table. Generates two genuinely different
  variants per role â€” **A: formal + finance-led** (accounting rigor, controls,
  CPA-track) and **B: conversational + tech-led** (data/analytics, warmer) â€”
  templated by default, Claude-written with a key. `--sent` / `--response`
  record outcomes; `analyze()` reports response rate by style / angle / firm type
  and names the winning voice.
- Verified the full loop: generated A/B for Deloitte, marked Aâ†’interview /
  Bâ†’none, and the analysis correctly surfaced "formal voice best (100%)" and
  "big4 converting 50%". Surfaced in the dashboard Pipeline tab.

### Notification System (Recommendation #11) âœ…
- `notify.py` + `notifications` table (dedupe by ref). Surfaces time-sensitive
  alerts on each run: fresh, high-priority job postings (configurable
  `--max-age` hours / `--min-priority` / `--tier`), offer deadlines within N
  days, and overdue follow-ups. Sinks: console always, plus a Slack-compatible
  webhook (`--webhook` or env `JOB_BOT_WEBHOOK`) posted via stdlib urllib (no
  deps). Built to run on a schedule (Task Scheduler / cron / a Claude cron task)
  â€” only new alerts fire. Verified: emitted fresh DMV postings + 3 offer
  deadlines, and correctly said "No new alerts" on the dedupe re-run.

### Interview Recording Analysis (Recommendation #12) âœ…
- `recording.py`. Turns a recorded-answer transcript (+ optional spoken
  duration) into measurable feedback: pacing (WPM vs a 110â€“175 target), fillers
  per minute, STAR compliance, quantification/ownership (reusing the Phase 7
  rubric), and the exact fillers + weak hedges to cut. `analyze_session()`
  aggregates a whole practice set (avg/best/worst score, total fillers, avg
  pace, top focus areas). CLI `--demo` / `--file` / `--text` / `--session`; also
  a ðŸŽ¤ Interview Lab dashboard tab. Verified on a filler-heavy demo (flagged 175
  wpm, 21.8 fillers/min, listed 8 fillers + 6 hedges).

**All 15 plan recommendations are now built.** The system is 9 phases + 15
recommendations complete: 52 modules, all importing clean; the dashboard runs
end-to-end with a 9-tab control center.

