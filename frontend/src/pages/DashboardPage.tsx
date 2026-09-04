import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import { api } from '../lib/api'
import type {
  DashboardSummary,
  ReportListResponse,
  ReportListItem,
} from '../lib/types'
import { Notice } from '../components/ui'

interface DashboardActivity {
  event_type: string
  company_name: string
  status: string | null
  occurred_at: string
}

function relativeTime(iso: string): string {
  const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (seconds < 60) return 'just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days === 1) return 'yesterday'
  return `${days}d ago`
}

function eventTitle(eventType: string): string {
  return eventType
    .split('_')
    .map((word, index) =>
      index === 0 ? word.charAt(0).toUpperCase() + word.slice(1) : word,
    )
    .join(' ')
}

function scoreTier(score: number): { label: string; tone: string } {
  if (score >= 70) return { label: 'High', tone: 'text-secondary' }
  if (score >= 40) return { label: 'Medium', tone: 'text-on-surface-variant' }
  return { label: 'Low', tone: 'text-outline' }
}

function activityDot(eventType: string): string {
  if (eventType === 'research_failed') return 'bg-error'
  if (eventType === 'research_requested')
    return 'border border-outline bg-surface-container-lowest'
  return 'bg-on-surface'
}

function ActivityRow({ event }: { event: DashboardActivity }) {
  return (
    <div className="relative">
      <span
        className={'absolute -left-5 top-1.5 h-2 w-2 rounded-full ' + activityDot(event.event_type)}
      />
      <p className="text-body-md font-medium text-on-surface">
        {eventTitle(event.event_type)}
      </p>
      <p className="mt-0.5 min-w-0 truncate text-body-sm text-on-surface-variant">
        {event.company_name} &middot; {relativeTime(event.occurred_at)}
      </p>
    </div>
  )
}

function StatusChip({ status }: { status: 'draft' | 'approved' }) {
  return status === 'approved' ? (
    <span className="inline-flex items-center gap-1 rounded-control border border-forest bg-forest-wash px-1.5 py-0.5 font-ui text-[11px] font-medium text-ok-ink">
      Approved
    </span>
  ) : (
    <span className="inline-flex items-center rounded-control border border-warn-bg bg-warn-bg px-1.5 py-0.5 font-ui text-[11px] font-medium text-warn-ink">
      Draft
    </span>
  )
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [recent, setRecent] = useState<ReportListResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([
      api<DashboardSummary>('/dashboard/summary'),
      api<ReportListResponse>('/reports', { params: { page: 1, page_size: 5 } }),
    ])
      .then(([summaryData, reportsData]) => {
        if (cancelled) return
        setSummary(summaryData)
        setRecent(reportsData)
      })
      .catch((e: unknown) => {
        if (!cancelled)
          setError(e instanceof Error ? e.message : 'Could not load the dashboard.')
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (error) {
    return (
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        <Notice kind="error">{error}</Notice>
      </main>
    )
  }

  if (!summary || !recent) {
    return (
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        <div className="h-16 animate-pulse rounded bg-surface-container-low" />
        <div className="mt-6 h-24 animate-pulse rounded-card bg-surface-container-lowest shadow-sm" />
        <div className="mt-6 h-64 animate-pulse rounded-card bg-surface-container-lowest shadow-sm" />
      </main>
    )
  }

  const stats: { value: string; label: string }[] = [
    { value: String(summary.reports_generated), label: 'reports generated' },
    { value: String(summary.companies_researched), label: 'companies researched' },
    { value: String(summary.industries_researched), label: 'industries researched' },
    {
      value:
        summary.average_opportunity_score !== null
          ? String(summary.average_opportunity_score)
          : '\u2014',
      label: 'avg opportunity /100',
    },
  ]

  const activity = summary.recent_activity
    .slice()
    .sort((a, b) => b.occurred_at.localeCompare(a.occurred_at))
    .slice(0, 6)

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-8 sm:px-6">
      <section className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="max-w-2xl space-y-1">
          <h1 className="font-display text-headline-xl font-semibold tracking-tight text-on-surface">
            Sales Intelligence Dashboard
          </h1>
          <p className="text-body-lg text-on-surface-variant">
            Evidence-backed account research and verified company dossiers.
          </p>
        </div>
        <div className="flex shrink-0 flex-col gap-2 sm:flex-row sm:items-center">
          <button
            type="button"
            onClick={() => navigate('/research')}
            className="inline-flex w-full items-center justify-center gap-2 rounded-control bg-primary px-4 py-2 text-label-md font-medium text-on-primary transition-colors hover:bg-inverse-surface sm:w-auto"
          >
            Research a company
          </button>
          <button
            type="button"
            onClick={() => navigate('/discover')}
            className="inline-flex w-full items-center justify-center gap-2 rounded-control border border-line bg-surface-container-lowest px-4 py-2 text-label-md font-medium text-on-surface transition-colors hover:border-outline hover:bg-surface-container-low sm:w-auto"
          >
            Discover companies
          </button>
        </div>
      </section>

      <section className="flex flex-wrap items-center gap-x-5 gap-y-2 px-1">
        {stats.map((stat, index) => (
          <div key={stat.label} className="flex items-baseline gap-1.5">
            {index > 0 && <span className="mr-3.5 hidden h-4 w-px bg-line-soft sm:block" />}
            <span className="font-display text-headline-md font-semibold text-on-surface">
              {stat.value}
            </span>
            <span className="text-body-sm text-on-surface-variant">{stat.label}</span>
          </div>
        ))}
      </section>

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="flex flex-col gap-3 lg:col-span-8">
          <div className="flex items-center justify-between px-1">
            <h2 className="font-display text-headline-md font-semibold text-on-surface">
              Recent reports
            </h2>
            <button
              type="button"
              onClick={() => navigate('/history')}
              className="text-label-md font-medium text-secondary transition-colors hover:text-on-surface"
            >
              View all reports
            </button>
          </div>

          {recent.items.length === 0 ? (
            <div className="flex flex-col items-center gap-4 rounded-card bg-surface-container-lowest p-8 text-center shadow-sm">
              <p className="text-body-md text-on-surface-variant">
                No reports yet. Generate your first one from the workflows above.
              </p>
              <div className="flex flex-col gap-2 sm:flex-row">
                <button
                  type="button"
                  onClick={() => navigate('/research')}
                  className="inline-flex w-full items-center justify-center gap-2 rounded-control bg-primary px-4 py-2 text-label-md font-medium text-on-primary transition-colors hover:bg-inverse-surface sm:w-auto"
                >
                  Research a company
                </button>
                <button
                  type="button"
                  onClick={() => navigate('/discover')}
                  className="inline-flex w-full items-center justify-center gap-2 rounded-control border border-line bg-surface-container-lowest px-4 py-2 text-label-md font-medium text-on-surface transition-colors hover:border-outline hover:bg-surface-container-low sm:w-auto"
                >
                  Discover companies
                </button>
              </div>
            </div>
          ) : (
            <div className="overflow-hidden rounded-card bg-surface-container-lowest shadow-sm">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[560px] table-fixed text-left">
                <thead>
                  <tr className="bg-surface-container-low text-label-sm uppercase tracking-wider text-outline">
                    <th className="w-[45%] px-4 py-2 font-medium">Company</th>
                    <th className="w-[19%] px-4 py-2 font-medium">Score</th>
                    <th className="w-[17%] px-4 py-2 font-medium">Status</th>
                    <th className="w-[15%] px-4 py-2 font-medium">Age</th>
                    <th className="w-[4%] px-2 py-2">
                      <span className="sr-only">Open</span>
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line-soft text-on-surface">
                  {recent.items.map((item: ReportListItem) => {
                    const tier = scoreTier(item.opportunity_score)
                    return (
                      <tr
                        key={item.id}
                        onClick={() => navigate(`/reports/${item.id}`)}
                        className="group cursor-pointer transition-colors hover:bg-surface-container-low"
                      >
                        <td className="px-4 py-3.5">
                          <div className="flex items-center gap-2.5">
                            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-control bg-surface-container font-display text-sm font-semibold text-on-surface">
                              {item.company_name.charAt(0).toUpperCase()}
                            </div>
                            <span className="font-display text-headline-sm font-semibold text-on-surface">
                              {item.company_name}
                            </span>
                          </div>
                        </td>
                        <td className="px-4 py-3.5">
                          <div className="flex items-baseline gap-1.5">
                            <span className="font-display text-headline-md font-semibold text-on-surface">
                              {item.opportunity_score}
                            </span>
                            <span className="text-body-sm text-outline">/100</span>
                            <span className={'text-label-sm tracking-wide ' + tier.tone}>
                              {tier.label}
                            </span>
                          </div>
                        </td>
                        <td className="px-4 py-3.5">
                          <StatusChip status={item.review_status} />
                        </td>
                        <td className="px-4 py-3.5 text-tabular-data text-on-surface-variant">
                          {relativeTime(item.generated_at)}
                        </td>
                        <td className="w-10 px-2 py-3.5 text-right">
                          <ChevronRight
                            size={16}
                            className="text-outline opacity-0 transition-opacity group-hover:opacity-100"
                          />
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              </div>
            </div>
          )}
        </div>

        <div className="flex flex-col gap-3 lg:col-span-4">
          <h2 className="px-1 label-caps text-ink-faint">Recent activity</h2>
          <div className="ml-1 flex flex-col gap-4 border-l border-line-soft pl-4">
            {activity.length === 0 && (
              <p className="text-body-sm text-on-surface-variant">
                No activity yet. Start by discovering or researching a company.
              </p>
            )}
            {activity.map((event) => (
              <ActivityRow key={`${event.event_type}-${event.occurred_at}`} event={event} />
            ))}
          </div>
        </div>
      </section>
    </main>
  )
}
