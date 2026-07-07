import {
  Briefcase,
  AtSign,
  Building2,
  CheckCircle2,
  GraduationCap,
  MessageCircle,
  Mic,
  Search,
  Send,
  Sparkles,
  Target,
  TrendingUp,
  Users,
  Gift,
  XCircle,
} from 'lucide-react'
import { AppHeader } from '@/components/AppHeader'
import { ApplicationsTable } from '@/components/ApplicationsTable'
import { BriefTab } from '@/components/BriefTab'
import { CoachTab } from '@/components/CoachTab'
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
import { ScoreTab } from '@/components/ScoreTab'
import { Card } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { api } from '@/lib/api'
import { useAsync } from '@/lib/useAsync'

function ErrorNote({ error }: { error: string }) {
  return (
    <Card className="border-destructive/30 bg-destructive/5 p-6 text-sm text-destructive">
      <p className="font-medium">Couldn't reach the API.</p>
      <p className="mt-1 text-destructive/80">{error}</p>
      <p className="mt-3 text-muted-foreground">
        Start the server from the project root:{' '}
        <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs text-foreground">
          uvicorn job_bot.api:app --port 8000
        </code>
      </p>
    </Card>
  )
}

function SkeletonGrid() {
  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="h-28 animate-pulse rounded-xl border border-border bg-card" />
      ))}
    </div>
  )
}

export default function App() {
  const profile = useAsync(api.profile, [])
  const summary = useAsync(api.summary, [])
  const apps = useAsync(api.applications, [])
  const jobs = useAsync(() => api.jobs({ limit: 100 }), [])

  const s = summary.data

  return (
    <div className="mx-auto max-w-6xl px-5 py-8 md:px-8 md:py-10">
      <AppHeader profile={profile.data} />

      <div className="mt-8">
        {summary.error ? (
          <ErrorNote error={summary.error} />
        ) : summary.loading || !s ? (
          <SkeletonGrid />
        ) : (
          <Tabs defaultValue="overview">
            <div className="overflow-x-auto pb-1">
              <TabsList>
                <TabsTrigger value="overview">
                  <Target size={15} /> Overview
                </TabsTrigger>
                <TabsTrigger value="coach">
                  <MessageCircle size={15} /> Coach
                </TabsTrigger>
                <TabsTrigger value="applications">
                  <Send size={15} /> Applications
                </TabsTrigger>
                <TabsTrigger value="pipeline">
                  <Briefcase size={15} /> Pipeline
                </TabsTrigger>
                <TabsTrigger value="find">
                  <Search size={15} /> Find Jobs
                </TabsTrigger>
                <TabsTrigger value="network">
                  <Users size={15} /> Network
                </TabsTrigger>
                <TabsTrigger value="growth">
                  <GraduationCap size={15} /> Growth
                </TabsTrigger>
                <TabsTrigger value="offers">
                  <Gift size={15} /> Offers
                </TabsTrigger>
                <TabsTrigger value="score">
                  <Sparkles size={15} /> Score a JD
                </TabsTrigger>
                <TabsTrigger value="brief">
                  <Building2 size={15} /> Company Brief
                </TabsTrigger>
                <TabsTrigger value="linkedin">
                  <AtSign size={15} /> LinkedIn
                </TabsTrigger>
                <TabsTrigger value="interview">
                  <Mic size={15} /> Interview Lab
                </TabsTrigger>
              </TabsList>
            </div>

            {/* ---------------------------------------------------- Overview */}
            <TabsContent value="overview" className="space-y-6">
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
                <KpiCard
                  label="Rejected"
                  value={s.rejected}
                  sub={`${s.offers} offers open`}
                  icon={XCircle}
                  accent="red"
                />
              </div>

              <div className="grid gap-6 lg:grid-cols-2">
                <PipelineFunnel summary={s} />
                <FieldMix summary={s} />
              </div>

              <ProfilePanel />
            </TabsContent>

            {/* ------------------------------------------------------ Coach */}
            <TabsContent value="coach">
              <CoachTab />
            </TabsContent>

            {/* ------------------------------------------------ Applications */}
            <TabsContent value="applications" className="space-y-4">
              <p className="text-sm text-muted-foreground">
                {apps.data?.length ?? 0} companies · reconciled from your tracker, Gmail history, interviews,
                rejections, and offers.
              </p>
              {apps.error ? (
                <ErrorNote error={apps.error} />
              ) : apps.loading ? (
                <div className="h-64 animate-pulse rounded-xl border border-border bg-card" />
              ) : (
                <ApplicationsTable apps={apps.data ?? []} />
              )}
            </TabsContent>

            {/* --------------------------------------------------- Pipeline */}
            <TabsContent value="pipeline" className="space-y-4">
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
            </TabsContent>

            {/* --------------------------------------------------- Find Jobs */}
            <TabsContent value="find">
              <FindJobsTab />
            </TabsContent>

            {/* ---------------------------------------------------- Network */}
            <TabsContent value="network">
              <NetworkTab />
            </TabsContent>

            {/* ----------------------------------------------------- Growth */}
            <TabsContent value="growth">
              <GrowthTab />
            </TabsContent>

            {/* ----------------------------------------------------- Offers */}
            <TabsContent value="offers">
              <OffersTab />
            </TabsContent>

            {/* -------------------------------------------------- Score a JD */}
            <TabsContent value="score">
              <ScoreTab />
            </TabsContent>

            {/* ----------------------------------------------- Company Brief */}
            <TabsContent value="brief">
              <BriefTab />
            </TabsContent>

            {/* ----------------------------------------------------- LinkedIn */}
            <TabsContent value="linkedin">
              <LinkedInTab />
            </TabsContent>

            {/* ------------------------------------------------ Interview Lab */}
            <TabsContent value="interview">
              <InterviewTab />
            </TabsContent>
          </Tabs>
        )}
      </div>

      <footer className="mt-12 border-t border-border pt-6 text-center text-xs text-muted-foreground">
        Job Bot · Career OS — single React dashboard on the FastAPI layer
      </footer>
    </div>
  )
}
