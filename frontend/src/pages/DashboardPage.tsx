import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronRight, ArrowRight } from 'lucide-react'
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
        className={'absolute -left-5 top-[6px] h-2 w-2 rounded-full ' + activityDot(event.event_type)}
      />
      <p className="truncate text-body-sm text-on-surface">
        <span className="font-medium">{eventTitle(event.event_type)}</span>
        <span className="text-on-surface-variant">
          {' '}
          &middot; {event.company_name} &middot; {relativeTime(event.occurred_at)}
        </span>
      </p>
    </div>
  )
}

function latestPerCompany(items: ReportListItem[]): ReportListItem[] {
  const byCompany = new Map<string, ReportListItem>()
  for (const item of items) {
    const existing = byCompany.get(item.company_id)
    if (!existing || item.generated_at.localeCompare(existing.generated_at) > 0) {
      byCompany.set(item.company_id, item)
    }
  }
  return Array.from(byCompany.values())
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [reports, setReports] = useState<ReportListResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([
      api<DashboardSummary>('/dashboard/summary'),
      api<ReportListResponse>('/reports', { params: { page: 1, page_size: 50 } }),
    ])
      .then(([summaryData, reportsData]) => {
        if (cancelled) return
        setSummary(summaryData)
        setReports(reportsData)
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
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
        <Notice kind="error">{error}</Notice>
      </main>
    )
  }

  if (!summary || !reports) {
    return (
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
        <div className="h-16 animate-pulse rounded bg-surface-container-low" />
        <div className="mt-6 h-24 animate-pulse rounded-card bg-surface-container-lowest shadow-sm" />
        <div className="mt-6 h-64 animate-pulse rounded-card bg-surface-container-lowest shadow-sm" />
      </main>
    )
  }

  const items = reports.items
  const drafts = items.filter((item) => item.review_status === 'draft')
  const approved = items
    .filter((item) => item.review_status === 'approved')
    .sort((a, b) => b.generated_at.localeCompare(a.generated_at))
  const opportunities = latestPerCompany(items)
    .sort((a, b) => b.opportunity_score - a.opportunity_score)
    .slice(0, 5)
  const activity = summary.recent_activity
    .slice()
    .sort((a, b) => b.occurred_at.localeCompare(a.occurred_at))
    .slice(0, 5)

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

  const nextStep = (() => {
    if (drafts.length > 0) {
      const top = drafts[0]
      return {
        reason: `Highest-scoring draft in your queue at ${top.opportunity_score}/100.`,
        action: `Review ${top.company_name}`,
        to: `/reports/${top.id}`,
        cta: 'Review report',
      }
    }
    if (items.length > 0) {
      return {
        reason: 'Every generated report has been reviewed.',
        action: 'Research your next account',
        to: '/research',
        cta: 'Start research',
      }
    }
    return {
      reason: 'No reports yet. Discovery finds candidates matched to your offer.',
      action: 'Discover candidate companies',
      to: '/discover',
      cta: 'Start discovery',
    }
  })()

  return (
    <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-8 sm:px-6">
      <section className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="max-w-2xl space-y-1">
          <h1 className="font-display text-headline-xl font-semibold tracking-tight text-on-surface">
            Sales Intelligence Dashboard
          </h1>
          <p className="max-w-2xl text-body-md text-on-surface-variant">
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

      <button
        type="button"
        onClick={() => navigate(nextStep.to)}
        className="group flex w-full items-center gap-4 border-y border-line-soft py-4 text-left transition-colors hover:bg-surface-container-low focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary"
      >
        <span className="label-caps shrink-0 text-ink-faint">Next step</span>
        <span className="min-w-0 flex-1">
          <span className="block text-body-md font-medium text-on-surface">
            {nextStep.action}
          </span>
          <span className="mt-0.5 block truncate text-body-sm text-on-surface-variant">
            {nextStep.reason}
          </span>
        </span>
        <ArrowRight size={16} className="shrink-0 text-outline transition-colors group-hover:text-on-surface" />
      </button>

      <section className="grid grid-cols-1 gap-8 lg:grid-cols-12">
        <div className="flex flex-col gap-3 lg:col-span-8">
          <div className="flex items-center justify-between px-1">
            <h2 className="font-display text-headline-md font-semibold text-on-surface">
              Top opportunities
            </h2>
            <button
              type="button"
              onClick={() => navigate('/history')}
              className="text-label-md font-medium text-secondary transition-colors hover:text-on-surface"
            >
              All reports
            </button>
          </div>

          {opportunities.length === 0 ? (
            <div className="rounded-card bg-surface-container-lowest p-8 shadow-sm">
              <p className="text-body-md text-on-surface-variant">
                No accounts yet. Research a company or discover candidates to build your
                pipeline.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-line-soft rounded-card border border-line-soft bg-surface-container-lowest shadow-sm">
              {opportunities.map((item) => {
                const tier = scoreTier(item.opportunity_score)
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => navigate(`/reports/${item.id}`)}
                    className="group flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-surface-container-low"
                  >
                    <span className="min-w-0 flex-1 truncate text-body-md font-medium text-on-surface">
                      {item.company_name}
                    </span>
                    <span className="shrink-0 text-tabular-data text-on-surface-variant">
                      {relativeTime(item.generated_at)}
                    </span>
                    <span className="flex w-20 shrink-0 items-baseline justify-end gap-1">
                      <span className="text-body-md font-semibold text-on-surface">
                        {item.opportunity_score}
                      </span>
                      <span className="text-body-sm text-outline">/100</span>
                    </span>
                    <span
                      className={'w-14 shrink-0 text-right text-label-sm tracking-wide ' + tier.tone}
                    >
                      {tier.label}
                    </span>
                    <ChevronRight
                      size={16}
                      className="shrink-0 text-outline opacity-0 transition-opacity group-hover:opacity-100"
                    />
                  </button>
                )
              })}
            </div>
          )}

          <div className="mt-6 flex flex-col gap-3 border-l border-line-soft pl-4 pt-1">
            <h3 className="label-caps text-ink-faint">Recent activity</h3>
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

        <div className="flex flex-col gap-3 lg:col-span-4">
          <div className="flex items-center justify-between px-1">
            <h2 className="font-display text-headline-md font-semibold text-on-surface">
              Needs attention
            </h2>
            {drafts.length > 0 && (
              <span className="text-body-sm text-on-surface-variant">
                {drafts.length} awaiting review
              </span>
            )}
          </div>

          {drafts.length === 0 && approved.length === 0 ? (
            <div className="rounded-card border border-line-soft bg-surface-container-lowest p-4 shadow-sm">
              <p className="text-body-sm text-on-surface-variant">
                Nothing needs you right now. Every report has been reviewed.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-line-soft rounded-card border border-line-soft bg-surface-container-lowest shadow-sm">
              {drafts.length > 0 && (
                <button
                  type="button"
                  onClick={() => navigate('/history')}
                  className="group flex w-full items-center gap-3 px-4 py-4 text-left transition-colors hover:bg-surface-container-low"
                >
                  <span className="w-8 shrink-0 text-body-lg font-semibold text-on-surface">
                    {drafts.length}
                  </span>
                  <span className="min-w-0 flex-1 text-body-md text-on-surface">
                    {drafts.length === 1 ? 'report awaits' : 'reports await'} your review
                  </span>
                  <ArrowRight
                    size={15}
                    className="shrink-0 text-outline transition-colors group-hover:text-on-surface"
                  />
                </button>
              )}
              {approved.length > 0 && (
                <button
                  type="button"
                  onClick={() => navigate(`/reports/${approved[0].id}`)}
                  className="group flex w-full items-center gap-3 px-4 py-4 text-left transition-colors hover:bg-surface-container-low"
                >
                  <span className="w-8 shrink-0 text-body-lg font-semibold text-on-surface">
                    {approved.length}
                  </span>
                  <span className="min-w-0 flex-1 text-body-md text-on-surface">
                    {approved.length === 1 ? 'approved report' : 'approved reports'}
                  </span>
                  <ArrowRight
                    size={15}
                    className="shrink-0 text-outline transition-colors group-hover:text-on-surface"
                  />
                </button>
              )}
            </div>
          )}
        </div>
      </section>
    </main>
  )
}
