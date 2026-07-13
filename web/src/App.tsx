import { useEffect, useState } from 'react'
import {
  Briefcase,
  AtSign,
  Building2,
  CheckCircle2,
  FileCode2,
  GraduationCap,
  LogOut,
  Menu,
  MessageCircle,
  Mic,
  Search,
  Send,
  Sparkles,
  Target,
  TrendingUp,
  Users,
  Gift,
  X,
  XCircle,
  type LucideIcon,
} from 'lucide-react'
import { AppHeader } from '@/components/AppHeader'
import { ApplicationsTable } from '@/components/ApplicationsTable'
import { BriefTab } from '@/components/BriefTab'
import { CoachTab } from '@/components/CoachTab'
import { ErrorNote } from '@/components/ErrorNote'
import { FieldMix } from '@/components/FieldMix'
import { FindJobsTab } from '@/components/FindJobsTab'
import { GrowthTab } from '@/components/GrowthTab'
import { InterviewTab } from '@/components/InterviewTab'
import { JobsTable } from '@/components/JobsTable'
import { KpiCard } from '@/components/KpiCard'
import { LinkedInTab } from '@/components/LinkedInTab'
import { NetworkTab } from '@/components/NetworkTab'
import { OffersTab } from '@/components/OffersTab'
import { PipelineFunnel } from '@/components/PipelineFunnel'
import { ProfilePanel } from '@/components/ProfilePanel'
import { ResumeStudioTab } from '@/components/ResumeStudioTab'
import { ScoreTab } from '@/components/ScoreTab'
import { SignInScreen } from '@/components/SignInScreen'
import { SyncIndicator } from '@/components/SyncIndicator'
import { api, type AuthStatus } from '@/lib/api'
import { useAsync } from '@/lib/useAsync'

function SkeletonGrid() {
  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="h-28 animate-pulse rounded-xl border border-border bg-card" />
      ))}
    </div>
  )
}

type PageKey =
  | 'overview'
  | 'coach'
  | 'applications'
  | 'pipeline'
  | 'find'
  | 'studio'
  | 'score'
  | 'linkedin'
  | 'network'
  | 'growth'
  | 'offers'
  | 'brief'
  | 'interview'

interface NavItem {
  key: PageKey
  label: string
  icon: LucideIcon
}

const NAV: { section: string; items: NavItem[] }[] = [
  {
    section: 'Overview',
    items: [
      { key: 'overview', label: 'Overview', icon: Target },
      { key: 'coach', label: 'Coach', icon: MessageCircle },
    ],
  },
  {
    section: 'Pipeline',
    items: [
      { key: 'applications', label: 'Applications', icon: Send },
      { key: 'pipeline', label: 'Pipeline', icon: Briefcase },
      { key: 'find', label: 'Find Jobs', icon: Search },
    ],
  },
  {
    section: 'Build',
    items: [
      { key: 'studio', label: 'Resume Studio', icon: FileCode2 },
      { key: 'score', label: 'Score a JD', icon: Sparkles },
      { key: 'linkedin', label: 'LinkedIn', icon: AtSign },
    ],
  },
  {
    section: 'Network & Growth',
    items: [
      { key: 'network', label: 'Network', icon: Users },
      { key: 'growth', label: 'Growth', icon: GraduationCap },
      { key: 'offers', label: 'Offers', icon: Gift },
      { key: 'brief', label: 'Company Brief', icon: Building2 },
      { key: 'interview', label: 'Interview Lab', icon: Mic },
    ],
  },
]

const PAGE_KEYS = new Set<string>(NAV.flatMap((s) => s.items.map((i) => i.key)))
const STORAGE_KEY = 'jobbot.page'

export default function App() {
  // Auth gate: everything under /api/* is 401 until the Google login sets the
  // session cookie, so don't mount the dashboard (and its fetches) before then.
  const auth = useAsync(api.authStatus, [])

  if (auth.loading) {
    return (
      <div className="flex min-h-dvh items-center justify-center">
        <div className="h-28 w-full max-w-sm animate-pulse rounded-2xl border border-border bg-card" />
      </div>
    )
  }
  if (auth.error) {
    return (
      <div className="mx-auto max-w-lg px-5 py-16">
        <ErrorNote error={`Can't reach the API — is uvicorn running on :8000? (${auth.error})`} />
      </div>
    )
  }
  if (!auth.data?.logged_in) {
    return <SignInScreen configured={auth.data?.configured ?? false} />
  }
  return <Dashboard auth={auth.data} />
}

function Dashboard({ auth }: { auth: AuthStatus }) {
  const profile = useAsync(api.profile, [])
  const summary = useAsync(api.summary, [])
  const apps = useAsync(api.applications, [])
  const jobs = useAsync(() => api.jobs({ limit: 100 }), [])

  const [page, setPage] = useState<PageKey>(() => {
    const saved = localStorage.getItem(STORAGE_KEY)
    return saved && PAGE_KEYS.has(saved) ? (saved as PageKey) : 'overview'
  })
  const [navOpen, setNavOpen] = useState(false)

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, page)
  }, [page])

  function go(key: PageKey) {
    setPage(key)
    setNavOpen(false)
  }

  async function signOut() {
    try {
      await api.logout()
    } finally {
      window.location.reload() // re-runs the auth gate → sign-in screen
    }
  }

  const s = summary.data

  function renderPage() {
    switch (page) {
      case 'overview':
        if (!s) return null
        return (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              <KpiCard
                label="Applications"
                value={s.total}
                sub={`${s.positions} positions`}
                icon={Send}
                accent="indigo"
              />
              <KpiCard
                label="Interview rate"
                value={`${s.interview_rate}%`}
                sub={`${s.reached_interview} reached interview`}
                icon={TrendingUp}
                accent="violet"
              />
              <KpiCard
                label="Response rate"
                value={`${s.response_rate}%`}
                sub={`${s.ghosted} ghosted`}
                icon={CheckCircle2}
                accent="green"
              />
              <KpiCard label="Rejected" value={s.rejected} sub={`${s.offers} offers open`} icon={XCircle} accent="red" />
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <PipelineFunnel summary={s} />
              <FieldMix summary={s} />
            </div>

            <ProfilePanel />
          </div>
        )
      case 'coach':
        return <CoachTab />
      case 'applications':
        return (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              {apps.data?.length ?? 0} companies · reconciled from your tracker, Gmail history, interviews, rejections,
              and offers.
            </p>
            {apps.error ? (
              <ErrorNote error={apps.error} />
            ) : apps.loading ? (
              <div className="h-64 animate-pulse rounded-xl border border-border bg-card" />
            ) : (
              <ApplicationsTable apps={apps.data ?? []} />
            )}
          </div>
        )
      case 'pipeline':
        return (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Live scored postings, ranked by priority. Higher ATS score = closer fit to your profile.
            </p>
            {jobs.error ? (
              <ErrorNote error={jobs.error} />
            ) : jobs.loading ? (
              <div className="h-64 animate-pulse rounded-xl border border-border bg-card" />
            ) : (
              <JobsTable jobs={jobs.data ?? []} />
            )}
          </div>
        )
      case 'find':
        return <FindJobsTab />
      case 'studio':
        return <ResumeStudioTab />
      case 'score':
        return <ScoreTab />
      case 'linkedin':
        return <LinkedInTab />
      case 'network':
        return <NetworkTab />
      case 'growth':
        return <GrowthTab />
      case 'offers':
        return <OffersTab />
      case 'brief':
        return <BriefTab />
      case 'interview':
        return <InterviewTab />
    }
  }

  const nav = (
    <nav className="space-y-5">
      {NAV.map((group) => (
        <div key={group.section}>
          <p className="mb-1.5 px-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            {group.section}
          </p>
          <ul className="space-y-0.5">
            {group.items.map(({ key, label, icon: Icon }) => (
              <li key={key}>
                <button
                  onClick={() => go(key)}
                  aria-current={page === key ? 'page' : undefined}
                  className={`flex w-full items-center gap-2.5 rounded-lg px-2 py-1.5 text-left text-sm transition-colors ${
                    page === key
                      ? 'bg-primary/10 font-medium text-primary'
                      : 'text-foreground/80 hover:bg-muted hover:text-foreground'
                  }`}
                >
                  <Icon size={16} className="shrink-0" aria-hidden />
                  <span className="truncate">{label}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  )

  return (
    <div className="min-h-dvh md:flex">
      {/* Mobile top bar */}
      <div className="sticky top-0 z-30 flex items-center gap-3 border-b border-border bg-background/95 px-4 py-3 backdrop-blur md:hidden">
        <button
          onClick={() => setNavOpen(true)}
          aria-label="Open navigation"
          className="rounded-lg p-1.5 hover:bg-muted"
        >
          <Menu size={20} />
        </button>
        <span className="text-sm font-semibold">Job Bot · Career OS</span>
      </div>

      {/* Mobile drawer scrim */}
      {navOpen && (
        <div className="fixed inset-0 z-40 bg-black/50 md:hidden" onClick={() => setNavOpen(false)} aria-hidden />
      )}

      {/* Sidebar: static column on md+, slide-in drawer below */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-60 overflow-y-auto border-r border-border bg-card p-4 transition-transform duration-200 md:sticky md:top-0 md:z-auto md:h-dvh md:shrink-0 md:translate-x-0 ${
          navOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="mb-6 flex items-center justify-between px-2">
          <div>
            <p className="text-sm font-bold tracking-tight">Job Bot</p>
            <p className="text-[11px] text-muted-foreground">Career OS</p>
          </div>
          <button
            onClick={() => setNavOpen(false)}
            aria-label="Close navigation"
            className="rounded-lg p-1.5 hover:bg-muted md:hidden"
          >
            <X size={18} />
          </button>
        </div>
        {nav}
      </aside>

      {/* Content */}
      <main className="min-w-0 flex-1">
        <div className="mx-auto max-w-6xl px-5 py-8 md:px-8 md:py-10">
          <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
            <AppHeader profile={profile.data} />
            <div className="flex items-center gap-2">
              <SyncIndicator />
              <button
                onClick={signOut}
                title={auth.email ? `Sign out (${auth.email})` : 'Sign out'}
                className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                <LogOut size={13} /> Sign out
              </button>
            </div>
          </div>

          <div className="mt-8">
            {summary.error ? <ErrorNote error={summary.error} /> : summary.loading || !s ? <SkeletonGrid /> : renderPage()}
          </div>

          <footer className="mt-12 border-t border-border pt-6 text-center text-xs text-muted-foreground">
            Job Bot · Career OS — single React dashboard on the FastAPI layer
          </footer>
        </div>
      </main>
    </div>
  )
}
