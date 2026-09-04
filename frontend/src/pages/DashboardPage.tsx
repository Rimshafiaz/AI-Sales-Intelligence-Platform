import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowRight,
  Building2,
  CheckCircle2,
  CircleAlert,
  FileSearch,
  FileText,
  Hourglass,
  PenLine,
  Shapes,
  TrendingUp,
} from 'lucide-react'
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

const ACTIVITY_ICONS: Record<string, typeof FileText> = {
  research_requested: Hourglass,
  research_completed: CheckCircle2,
  research_failed: CircleAlert,
  report_generated: FileText,
  report_approved: CheckCircle2,
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

function ActivityRow({ event }: { event: DashboardActivity }) {
  const failed = event.event_type === 'research_failed'
  const Icon =
    failed
      ? CircleAlert
      : ACTIVITY_ICONS[event.event_type] ?? FileText
  const tileClass = failed
    ? 'bg-error-container text-on-error-container'
    : event.event_type === 'research_requested'
      ? 'bg-surface-container-high text-outline'
      : 'bg-surface-container-high text-on-surface'
  const title = event.event_type
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')

  return (
    <div className="relative flex items-start gap-3">
      <div
        className={
          'flex h-8 w-8 shrink-0 items-center justify-center rounded ' + tileClass
        }
      >
        <Icon size={18} />
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <div className="flex items-center justify-between">
          <span
            className={
              'font-label-md font-semibold text-on-surface ' +
              (failed ? 'text-error' : '')
            }
          >
            {title}
          </span>
          <span className="text-tabular-data text-outline">
            {relativeTime(event.occurred_at)}
          </span>
        </div>
        <p className="truncate text-body-sm text-on-surface-variant">
          {event.company_name}
          {event.status ? ` — ${event.status}` : ''}
        </p>
      </div>
    </div>
  )
}

function ScorePill({ score }: { score: number }) {
  const dot = score >= 70 ? 'bg-secondary' : score >= 40 ? 'bg-warn-ink' : 'bg-outline'
  return (
    <div className="inline-flex items-center gap-1 rounded-full bg-surface-container px-2 py-0.5">
      <span className={'h-2 w-2 rounded-full ' + dot} />
      <span className="text-tabular-data font-semibold text-on-surface">{score}</span>
      <span className="text-label-sm text-outline">/100</span>
    </div>
  )
}

function StatusChip({ status }: { status: 'draft' | 'approved' }) {
  return status === 'approved' ? (
    <span className="inline-flex items-center gap-1 rounded bg-surface-container-high px-2 py-0.5 text-label-sm text-on-surface-variant">
      <CheckCircle2 size={14} />
      Approved
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 rounded bg-surface-container px-2 py-0.5 text-label-sm text-outline">
      <PenLine size={14} />
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
        <div className="mt-8 grid grid-cols-1 gap-6 md:grid-cols-2">
          {[1, 2].map((index) => (
            <div key={index} className="h-40 animate-pulse rounded bg-surface-container-lowest shadow-sm" />
          ))}
        </div>
        <div className="mt-6 h-28 animate-pulse rounded bg-surface-container-lowest shadow-sm" />
      </main>
    )
  }

  const metrics: { label: string; icon: typeof FileText; value: string; suffix?: string }[] = [
    {
      label: 'Reports generated',
      icon: FileText,
      value: String(summary.reports_generated),
    },
    {
      label: 'Companies researched',
      icon: Building2,
      value: String(summary.companies_researched),
    },
    {
      label: 'Industries researched',
      icon: Shapes,
      value: String(summary.industries_researched),
    },
    {
      label: 'Avg opportunity score',
      icon: TrendingUp,
      value:
        summary.average_opportunity_score !== null
          ? String(summary.average_opportunity_score)
          : '\u2014',
      suffix: summary.average_opportunity_score !== null ? '/ 100' : undefined,
    },
  ]

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-4 py-8 sm:px-6">
      <section className="flex flex-col justify-between gap-6 md:flex-row md:items-end">
        <div className="max-w-2xl space-y-1">
          <h1 className="font-display text-headline-xl font-semibold tracking-tight text-on-surface">
            Sales Intelligence Dashboard
          </h1>
          <p className="text-body-lg text-on-surface-variant">
            Evidence-backed account research and verified company dossiers.
          </p>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <div className="group relative flex flex-col justify-between rounded bg-surface-container-lowest p-8 shadow-sm transition-all hover:shadow-md">
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="text-label-sm uppercase tracking-widest text-outline">
                01 / Discovery
              </span>
              <div className="flex h-8 w-8 items-center justify-center rounded bg-surface-container text-on-surface">
                <FileSearch size={18} />
              </div>
            </div>
            <div className="space-y-1">
              <h2 className="font-display text-headline-lg font-semibold tracking-tight text-on-surface">
                Discover companies
              </h2>
              <p className="max-w-md text-body-md text-on-surface-variant">
                Define ICP criteria (industry, geography, headcount) to surface
                matched prospects with evidence.
              </p>
            </div>
          </div>
          <div className="flex items-center justify-between pt-8">
            <button
              type="button"
              onClick={() => navigate('/discover')}
              className="inline-flex items-center gap-2 rounded bg-primary px-4 py-2 text-label-md text-on-primary transition-colors hover:bg-surface-tint"
            >
              Discover companies
              <ArrowRight size={16} />
            </button>
          </div>
        </div>

        <div className="group relative flex flex-col justify-between rounded bg-surface-container-lowest p-8 shadow-sm transition-all hover:shadow-md">
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="text-label-sm uppercase tracking-widest text-outline">
                02 / Research
              </span>
              <div className="flex h-8 w-8 items-center justify-center rounded bg-surface-container text-on-surface">
                <FileSearch size={18} />
              </div>
            </div>
            <div className="space-y-1">
              <h2 className="font-display text-headline-lg font-semibold tracking-tight text-on-surface">
                Research a company
              </h2>
              <p className="max-w-md text-body-md text-on-surface-variant">
                Input any company name or URL to collect real-time web citations
                and build an intelligence dossier.
              </p>
            </div>
          </div>
          <div className="flex items-center justify-between pt-8">
            <button
              type="button"
              onClick={() => navigate('/research')}
              className="inline-flex items-center gap-2 rounded bg-surface-container-high px-4 py-2 text-label-md text-on-surface transition-colors hover:bg-surface-variant"
            >
              Research a company
              <ArrowRight size={16} />
            </button>
          </div>
        </div>
      </section>

      <section className="w-full overflow-hidden rounded bg-surface-container-lowest shadow-sm">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
          {metrics.map((metric) => (
            <div key={metric.label} className="flex flex-col justify-between gap-2 p-6">
              <div className="flex items-center justify-between">
                <span className="text-label-sm uppercase tracking-wider text-outline">
                  {metric.label}
                </span>
                <metric.icon size={16} className="text-outline" />
              </div>
              <div className="flex items-baseline gap-2">
                <span className="font-display text-numeric-metric font-semibold text-on-surface">
                  {metric.value}
                </span>
                {metric.suffix && (
                  <span className="text-body-md text-outline">{metric.suffix}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="grid grid-cols-1 gap-8 lg:grid-cols-12">
        <div className="flex flex-col gap-3 lg:col-span-8">
          <div className="flex items-center justify-between px-1">
            <div className="flex items-center gap-2">
              <h3 className="font-display text-headline-md font-semibold text-on-surface">
                Recent Reports
              </h3>
              <span className="rounded bg-surface-container px-2 py-0.5 text-label-sm text-on-surface-variant">
                {recent.total} total
              </span>
            </div>
            <button
              type="button"
              onClick={() => navigate('/history')}
              className="group inline-flex items-center gap-1 text-label-md text-on-surface-variant transition-colors hover:text-on-surface"
            >
              View all in History
              <ArrowRight
                size={16}
                className="transition-transform group-hover:translate-x-0.5"
              />
            </button>
          </div>

          {recent.items.length === 0 ? (
            <div className="rounded bg-surface-container-lowest p-8 text-center shadow-sm">
              <p className="text-body-md text-on-surface-variant">
                No reports yet. Generate your first one from the workflows above.
              </p>
            </div>
          ) : (
            <div className="overflow-hidden rounded bg-surface-container-lowest shadow-sm">
              <table className="w-full text-left">
                <thead>
                  <tr className="bg-surface-container-low text-label-sm uppercase tracking-wider text-outline">
                    <th className="px-4 py-2">Company</th>
                    <th className="px-4 py-2">Opportunity Score</th>
                    <th className="px-4 py-2">Review Status</th>
                    <th className="px-4 py-2">Generated</th>
                    <th className="px-4 py-2 text-right">Inspect</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line-soft text-on-surface">
                  {recent.items.map((item: ReportListItem) => (
                    <tr
                      key={item.id}
                      onClick={() => navigate(`/reports/${item.id}`)}
                      className="group cursor-pointer transition-colors hover:bg-surface-container-low"
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div className="flex h-7 w-7 items-center justify-center rounded bg-surface-container font-display text-sm font-semibold text-on-surface">
                            {item.company_name.charAt(0).toUpperCase()}
                          </div>
                          <div className="font-display text-headline-sm font-medium text-on-surface">
                            {item.company_name}
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <ScorePill score={item.opportunity_score} />
                      </td>
                      <td className="px-4 py-3">
                        <StatusChip status={item.review_status} />
                      </td>
                      <td className="px-4 py-3 text-tabular-data text-on-surface-variant">
                        {relativeTime(item.generated_at)}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <ArrowRight
                          size={18}
                          className="text-outline transition-all group-hover:translate-x-1 group-hover:text-on-surface"
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="flex flex-col gap-3 lg:col-span-4">
          <div className="flex items-center justify-between px-1">
            <h3 className="font-display text-headline-md font-semibold text-on-surface">
              Activity Stream
            </h3>
            <span className="text-label-sm uppercase tracking-wider text-outline">
              Latest
            </span>
          </div>
          <div className="flex flex-col gap-6 rounded bg-surface-container-lowest p-6 shadow-sm">
            {summary.recent_activity.length === 0 && (
              <p className="text-body-sm text-on-surface-variant">
                No activity yet. Start by discovering or researching a company.
              </p>
            )}
            {summary.recent_activity.map((event, index) => (
              <ActivityRow
                key={`${event.event_type}-${event.occurred_at}-${index}`}
                event={event}
              />
            ))}
          </div>
        </div>
      </section>
    </main>
  )
}
