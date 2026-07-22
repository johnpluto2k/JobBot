import { useState } from 'react'
import { CheckCircle2, AlertCircle, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ErrorNote } from '@/components/ErrorNote'
import { api, type Company } from '@/lib/api'
import { useAsync } from '@/lib/useAsync'

// Helper to parse JSON strings from database
function parseJsonField(value: any): any[] {
  if (Array.isArray(value)) return value
  if (!value) return []
  if (typeof value === 'string') {
    try {
      return JSON.parse(value)
    } catch {
      return []
    }
  }
  return []
}

export function CompanyTrackerTab() {
  const [refreshKey, setRefreshKey] = useState(0)
  const [filter, setFilter] = useState<'all' | 'overdue'>('all')
  const [checking, setChecking] = useState<Set<number>>(new Set())
  const [error, setError] = useState<string | null>(null)

  // Include refreshKey in dependency array to trigger re-fetch on manual refresh
  const companies = useAsync(api.companies, [refreshKey])

  const displayCompanies = companies.data
    ?.filter((c: Company) => {
      if (filter === 'all') return true
      if (!c.next_check_due) return true
      const dueDate = new Date(c.next_check_due)
      const today = new Date()
      today.setHours(0, 0, 0, 0)
      return dueDate <= today
    })
    .sort((a: Company, b: Company) => {
      // Sort overdue first, then by due date
      const aOverdue = !a.next_check_due || new Date(a.next_check_due) <= new Date()
      const bOverdue = !b.next_check_due || new Date(b.next_check_due) <= new Date()
      if (aOverdue !== bOverdue) return aOverdue ? -1 : 1
      return (a.next_check_due || '').localeCompare(b.next_check_due || '')
    })

  const overdueCount = companies.data?.filter((c: Company) => {
    if (!c.next_check_due) return true
    const dueDate = new Date(c.next_check_due)
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    return dueDate <= today
  }).length ?? 0

  async function markChecked(companyId: number) {
    setChecking((prev) => new Set(prev).add(companyId))
    setError(null)
    try {
      const response = await fetch(`/api/companies/${companyId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ next_check_in_days: 7 }),
      })
      if (!response.ok) {
        const statusText = response.statusText || `HTTP ${response.status}`
        throw new Error(`Failed to mark checked: ${statusText}`)
      }
      // Trigger refresh
      setRefreshKey((prev) => prev + 1)
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      setError(message)
      console.error('Error marking company checked:', err)
    } finally {
      setChecking((prev) => {
        const next = new Set(prev)
        next.delete(companyId)
        return next
      })
    }
  }

  if (companies.loading && !companies.data) {
    return <div className="h-64 animate-pulse rounded-xl border border-border bg-card" />
  }

  return (
    <div className="space-y-6">
      {/* Error Message */}
      {error && <ErrorNote error={error} />}

      {/* Summary Cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
        <Card>
          <CardContent className="pt-6">
            <div className="text-center">
              <p className="text-2xl font-bold">{companies.data?.length ?? 0}</p>
              <p className="text-xs text-muted-foreground">Companies tracked</p>
            </div>
          </CardContent>
        </Card>
        <Card className={overdueCount > 0 ? 'border-orange-500/50 bg-orange-500/5' : ''}>
          <CardContent className="pt-6">
            <div className="text-center">
              <p className="text-2xl font-bold text-orange-600">{overdueCount}</p>
              <p className="text-xs text-muted-foreground">Due for check-in</p>
            </div>
          </CardContent>
        </Card>
        <Card className="hidden lg:block">
          <CardContent className="pt-6">
            <div className="text-center">
              <p className="text-2xl font-bold">
                {companies.data?.filter((c: Company) => c.tier === 'Big4' || c.tier === 'Big 4').length ?? 0}
              </p>
              <p className="text-xs text-muted-foreground">Big 4 firms</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filter Tabs */}
      <div className="flex gap-2">
        <Button
          variant={filter === 'all' ? 'default' : 'outline'}
          onClick={() => setFilter('all')}
          size="sm"
        >
          All Companies
        </Button>
        <Button
          variant={filter === 'overdue' ? 'default' : 'outline'}
          onClick={() => setFilter('overdue')}
          size="sm"
          className={overdueCount > 0 ? 'relative' : ''}
        >
          Overdue
          {overdueCount > 0 && (
            <span className="ml-2 inline-flex h-5 w-5 items-center justify-center rounded-full bg-orange-600 text-[10px] font-bold text-white">
              {overdueCount}
            </span>
          )}
        </Button>
      </div>

      {/* Companies Table */}
      {companies.error ? (
        <ErrorNote error={companies.error} />
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">
              {filter === 'overdue' ? 'Companies Due for Check-in' : 'All Companies'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="px-4 py-3 text-left font-semibold">Company</th>
                    <th className="px-4 py-3 text-left font-semibold">Tier</th>
                    <th className="px-4 py-3 text-left font-semibold">Portals</th>
                    <th className="px-4 py-3 text-left font-semibold">Target Fields</th>
                    <th className="px-4 py-3 text-left font-semibold">Last Checked</th>
                    <th className="px-4 py-3 text-left font-semibold">Next Check Due</th>
                    <th className="px-4 py-3 text-center font-semibold">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {(displayCompanies ?? []).length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                        {filter === 'overdue'
                          ? 'No companies due for check-in'
                          : 'No companies tracked yet'}
                      </td>
                    </tr>
                  ) : (
                    (displayCompanies ?? []).map((company: Company) => {
                      const isOverdue =
                        !company.next_check_due ||
                        new Date(company.next_check_due) <= new Date()
                      // Cache parsed JSON fields to avoid re-parsing in each render
                      const portals = parseJsonField(company.portals)
                      const targetFields = parseJsonField(company.target_fields)
                      return (
                        <tr
                          key={company.id}
                          className={`border-b border-border transition-colors ${
                            isOverdue ? 'bg-orange-500/5' : 'hover:bg-muted/50'
                          }`}
                        >
                          <td className="px-4 py-3 font-medium">{company.name}</td>
                          <td className="px-4 py-3">
                            {company.tier ? (
                              <Badge variant="outline" className="text-xs">
                                {company.tier}
                              </Badge>
                            ) : (
                              <span className="text-muted-foreground">—</span>
                            )}
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex flex-wrap gap-1">
                              {portals.slice(0, 3).map((p) => (
                                <Badge key={p} variant="secondary" className="text-xs">
                                  {p}
                                </Badge>
                              ))}
                              {portals.length > 3 && (
                                <Badge variant="secondary" className="text-xs">
                                  +{portals.length - 3}
                                </Badge>
                              )}
                            </div>
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex flex-wrap gap-1">
                              {targetFields.slice(0, 2).map((f) => (
                                <Badge key={f} variant="secondary" className="text-xs">
                                  {f}
                                </Badge>
                              ))}
                              {targetFields.length > 2 && (
                                <Badge variant="secondary" className="text-xs">
                                  +{targetFields.length - 2}
                                </Badge>
                              )}
                            </div>
                          </td>
                          <td className="px-4 py-3 text-xs text-muted-foreground">
                            {company.last_checked
                              ? new Date(company.last_checked).toLocaleDateString()
                              : 'Never'}
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              {isOverdue && (
                                <span title="Due for check-in">
                                  <AlertCircle size={14} className="text-orange-600" />
                                </span>
                              )}
                              <span className={isOverdue ? 'font-semibold text-orange-600' : 'text-xs text-muted-foreground'}>
                                {company.next_check_due
                                  ? new Date(company.next_check_due).toLocaleDateString()
                                  : 'Not set'}
                              </span>
                            </div>
                          </td>
                          <td className="px-4 py-3 text-center">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => markChecked(company.id)}
                              disabled={checking.has(company.id)}
                              className="w-full"
                            >
                              {checking.has(company.id) ? (
                                <Loader2 size={14} className="mr-1 animate-spin" />
                              ) : (
                                <CheckCircle2 size={14} className="mr-1" />
                              )}
                              {checking.has(company.id) ? 'Checking...' : 'Check'}
                            </Button>
                          </td>
                        </tr>
                      )
                    })
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
