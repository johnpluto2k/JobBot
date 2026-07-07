/**
 * Typed client for the Job Bot FastAPI backend (job_bot/api.py).
 * All calls go through Vite's /api proxy in dev.
 */

export interface Profile {
  found: boolean
  name?: string | null
  email?: string | null
  location?: string | null
  headline?: string | null
  avatar?: string | null
}

export type StatusKey = 'offer' | 'interviewing' | 'in_review' | 'ghosted' | 'rejected'

export interface FieldStat {
  companies: number
  interviewed: number
}

export interface Summary {
  total: number
  positions: number
  by_status: Record<StatusKey, number>
  by_field: Record<string, FieldStat>
  status_labels: Record<StatusKey, string>
  reached_interview: number
  active: number
  rejected: number
  ghosted: number
  offers: number
  response_rate: number
  interview_rate: number
}

export interface Application {
  company: string
  status: StatusKey
  status_label: string
  reached_interview: boolean
  positions: number
  roles: string[]
  emails: number
  first_seen: string | null
  last_seen: string | null
  field: string
}

export interface Job {
  id: number
  title: string | null
  company: string | null
  location: string | null
  site: string | null
  url: string | null
  date_posted: string | null
  market_tier: string | null
  tier_num: number | null
  ats_score: number | null
  priority: number | null
  status: string | null
  legit_score: number | null
  legit_grade: string | null
  recommendation: string | null
  seniority: string | null
}

// --- Overview (rich profile) -------------------------------------------------
export interface EduEntry {
  school?: string
  degree?: string
  major?: string
  secondary_major?: string
  gpa?: number
  graduation_date?: string
}
export interface SkillGroup {
  category: string
  skills: string[]
}
export interface ExpEntry {
  role?: string
  organization?: string
  location?: string
  start_date?: string
  end_date?: string
  is_current?: boolean
  bullets?: string[]
}
export interface Targets {
  target_roles?: string[]
  target_firms?: string[]
  target_markets?: string[]
}
export interface Overview {
  found: boolean
  summary?: string
  education: EduEntry[]
  skills: SkillGroup[]
  targets: Targets
  certifications: string[]
  experience: ExpEntry[]
}

// --- Network -----------------------------------------------------------------
export interface Contact {
  name: string
  title?: string | null
  relationship?: string | null
  warmth?: number | null
  company: string
}
export interface CompanyCoverage {
  company: string
  contacts: Contact[]
  count: number
  coverage: number
  relationships: string[]
  reach_first: string | null
}
export interface NetworkGap {
  company: string
  coverage: number
  count: number
  status: string
}
export interface Network {
  covered: CompanyCoverage[]
  gaps: NetworkGap[]
  total_contacts: number
  companies_with_contacts: number
}

// --- Offers ------------------------------------------------------------------
export interface Offer {
  company: string
  role_title: string | null
  total_comp: number
  adjusted_comp: number
  score: number
  deadline: string | null
  subscores: { money: number; growth: number; fit: number }
}
export interface OffersResult {
  offers: Offer[]
  winner: Offer | null
  insights: string[]
}

// --- Growth ------------------------------------------------------------------
export interface FieldPlan {
  field: string
  applied_count: number
  is_stated_target: boolean
  strengths: string[]
  gaps: string[]
  certifications: [string, string, string][]
  projects: string[]
  resume_variant: { name: string; lead_with: string[]; add_keywords: string[] }
}
export interface GrowthPlan {
  have: string[]
  focus_fields: string[]
  target_fields: string[]
  per_field: FieldPlan[]
  insights: string[]
  top_actions: string[]
}

// --- Score a JD --------------------------------------------------------------
export interface Gap {
  keyword: string
  importance: string
  impact: number
  action: string
}
export interface ScoreResult {
  job: { title: string | null; company: string | null; market_tier: string | null; role_type: string | null }
  ats: {
    overall_score: number
    platform: string
    matched: string[]
    missing_required: string[]
    gap_analysis: Gap[]
  }
  decision: {
    verdict: string
    verdict_short: string
    rationale: string
    actions: string[]
    matches: { name: string; relationship: string | null; warmth: number | null }[]
  }
}

// --- Find Jobs ---------------------------------------------------------------
export interface Cycle {
  key: string
  season: string
  year: number
  kind: string
  label: string
  start: string
}
export interface CyclesInfo {
  graduation_date: string
  cycles: Cycle[]
  tracks: string[]
  default_tracks: string[]
  sites: string[]
  default_sites: string[]
}
export interface PerQuery {
  term: string
  found: number
  new: number
}
export interface SearchResult {
  scraped: number
  saved: number
  per_query: PerQuery[]
  on_target: Job[]
  n_on_target: number
  n_total: number
}

// --- Resume Studio -------------------------------------------------------------
export interface StudioSource {
  key: string
  label: string
}
export interface StudioSources {
  sources: StudioSource[]
}
export interface StudioYaml {
  yaml?: string
  field?: string
  suggested_renderer?: 'rendercv' | 'docx'
  error?: string
}
export interface StudioRender {
  pdf_b64?: string
  typ?: string | null
  pdf_name?: string
  error?: string
}
export interface StudioDocx {
  docx_b64?: string
  name?: string
  error?: string
}

// --- Company Brief -----------------------------------------------------------
export interface Brief {
  company: string
  role: string
  type: string
  ats_platform: string | null
  hiring_process: string[]
  values: string[]
  likely_topics: string[]
  why_this_firm: string[]
  smart_questions: string[]
  warm_contacts: { name: string; title?: string; relationship?: string; warmth?: number }[]
  open_roles: { title?: string; url?: string }[]
  recent_news: string[]
  narrative?: string
}

// --- LinkedIn ----------------------------------------------------------------
export interface ExperienceSuggestion {
  role?: string
  organization?: string
  suggestion?: string
  [k: string]: unknown
}
export interface LinkedInAudit {
  target_role: string
  headline: string
  about: string
  skills: string[]
  experience: ExperienceSuggestion[]
  keyword_gaps: string[]
  recommendations: string[]
}

// --- Interview recording -----------------------------------------------------
export interface Recording {
  question: string
  score: number
  band: string
  word_count: number
  star: { S: boolean; T: boolean; A: boolean; R: boolean }
  quantified: boolean
  ownership: number
  filler_count: number
  filler_breakdown: Record<string, number>
  hedges: string[]
  pacing: { wpm: number; duration_seconds: number; fillers_per_min: number } | null
  delivery_notes: string[]
  phrases_to_cut: string[]
  strengths: string[]
  improvements: string[]
}

// --- Career coach ------------------------------------------------------------
export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}
export interface CoachReply {
  reply: string | null
  error?: string
}
export interface CoachSnapshot {
  funnel?: Summary
  funnel_error?: string
  upcoming_interviews?: {
    company: string
    role_title: string | null
    round_name: string | null
    scheduled_at: string | null
    status: string
  }[]
  followups_due?: { contact_name: string; company: string; kind: string; followup_date: string }[]
  unhandled_recruiter_email?: { received_at: string; company: string; category: string }[]
  fresh_high_priority_jobs?: { title: string; company: string; priority: number | null }[]
  growth_insights?: string[]
  growth_focus_fields?: string[]
  db_error?: string
  growth_error?: string
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path, { headers: { Accept: 'application/json' } })
  if (!res.ok) throw new Error(`${path} → ${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${path} → ${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

export const api = {
  profile: () => get<Profile>('/api/profile'),
  overview: () => get<Overview>('/api/overview'),
  summary: () => get<Summary>('/api/summary'),
  applications: () => get<Application[]>('/api/applications'),
  jobs: (params?: { status?: string; limit?: number }) => {
    const q = new URLSearchParams()
    if (params?.status) q.set('status', params.status)
    if (params?.limit) q.set('limit', String(params.limit))
    const qs = q.toString()
    return get<Job[]>(`/api/jobs${qs ? `?${qs}` : ''}`)
  },
  network: () => get<Network>('/api/network'),
  offers: (w?: { money: number; growth: number; fit: number }) => {
    const q = w ? `?money=${w.money}&growth=${w.growth}&fit=${w.fit}` : ''
    return get<OffersResult>(`/api/offers${q}`)
  },
  growth: () => get<GrowthPlan>('/api/growth'),
  score: (body: { jd: string; url?: string; company?: string }) => post<ScoreResult>('/api/score', body),
  cycles: () => get<CyclesInfo>('/api/cycles'),
  search: (body: {
    tracks: string[]
    kind: string
    location?: string
    remote?: boolean
    results_per?: number
    hours_old?: number
    sites?: string[]
  }) => post<SearchResult>('/api/search', body),
  studioSources: () => get<StudioSources>('/api/resume-studio/sources'),
  studioYaml: (source: string) =>
    get<StudioYaml>(`/api/resume-studio/yaml?source=${encodeURIComponent(source)}`),
  studioRender: (yaml: string) => post<StudioRender>('/api/resume-studio/render', { yaml }),
  studioDocx: (source: string) =>
    get<StudioDocx>(`/api/resume-studio/docx?source=${encodeURIComponent(source)}`),
  brief: (body: { company: string; role?: string }) => post<Brief>('/api/brief', body),
  linkedin: (body: { target_role?: string; jd_text?: string }) => post<LinkedInAudit>('/api/linkedin', body),
  recording: (body: { question?: string; transcript: string; duration_seconds?: number }) =>
    post<Recording>('/api/recording', body),
  coachSnapshot: () => get<CoachSnapshot>('/api/coach/snapshot'),
  coach: (messages: ChatMessage[]) => post<CoachReply>('/api/coach', { messages }),
}

/** Map an application status to a Badge status-tint variant. */
export const STATUS_VARIANT: Record<StatusKey, 'green' | 'violet' | 'blue' | 'slate' | 'red'> = {
  offer: 'green',
  interviewing: 'violet',
  in_review: 'blue',
  ghosted: 'slate',
  rejected: 'red',
}
