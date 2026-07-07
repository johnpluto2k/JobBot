import { GraduationCap, Briefcase, Wrench, Crosshair } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { api } from '@/lib/api'
import { useAsync } from '@/lib/useAsync'

export function ProfilePanel() {
  const { data, loading } = useAsync(api.overview, [])
  if (loading || !data?.found) return null

  const edu = data.education[0]
  const allSkills = data.skills.flatMap((g) => g.skills)

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      {/* Summary + education */}
      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <GraduationCap size={17} style={{ color: 'var(--primary)' }} /> Profile
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {data.summary && <p className="text-sm leading-relaxed text-foreground">{data.summary}</p>}
          {edu && (
            <div className="rounded-lg border border-border bg-muted/40 p-3 text-sm">
              <div className="font-semibold text-foreground">{edu.school}</div>
              <div className="text-muted-foreground">{edu.degree}</div>
              {edu.secondary_major && <div className="text-muted-foreground">{edu.secondary_major}</div>}
              <div className="mt-1 flex flex-wrap gap-x-4 text-xs text-muted-foreground">
                {edu.gpa != null && <span>GPA {edu.gpa}</span>}
                {edu.graduation_date && <span>Grad {edu.graduation_date}</span>}
              </div>
            </div>
          )}
          {/* Experience */}
          <div>
            <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <Briefcase size={13} /> Experience
            </p>
            <div className="space-y-2.5">
              {data.experience.map((e, i) => (
                <div key={i} className="text-sm">
                  <div className="flex items-baseline justify-between">
                    <span className="font-medium text-foreground">{e.role}</span>
                    <span className="text-xs text-muted-foreground">
                      {e.start_date}{e.start_date && ' – '}{e.is_current ? 'Present' : e.end_date}
                    </span>
                  </div>
                  <div className="text-muted-foreground">{e.organization}</div>
                </div>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Skills + targets */}
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Wrench size={16} style={{ color: 'var(--status-violet)' }} /> Skills
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-1.5">
            {allSkills.map((s) => (
              <Badge key={s} variant="secondary">
                {s}
              </Badge>
            ))}
          </CardContent>
        </Card>
        {data.targets?.target_roles && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Crosshair size={16} style={{ color: 'var(--status-green)' }} /> Targets
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div>
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Roles</p>
                <div className="flex flex-wrap gap-1.5">
                  {data.targets.target_roles.map((r) => (
                    <Badge key={r} variant="blue">
                      {r}
                    </Badge>
                  ))}
                </div>
              </div>
              {data.targets.target_firms && (
                <div>
                  <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Firms</p>
                  <div className="flex flex-wrap gap-1.5">
                    {data.targets.target_firms.map((f) => (
                      <Badge key={f} variant="secondary">
                        {f}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}
