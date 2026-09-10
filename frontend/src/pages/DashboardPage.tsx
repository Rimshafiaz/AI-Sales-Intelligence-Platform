import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Notice } from '../components/ui'
import { api } from '../lib/api'
import type { DashboardAction, DashboardActivity, DashboardSummary } from '../lib/types'

function label(value: string): string {
  return value.replaceAll('_', ' ')
}

function relativeTime(iso: string): string {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000))
  if (seconds < 60) return 'Just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return days === 1 ? 'Yesterday' : `${days}d ago`
}

function ActionRow({ action }: { action: DashboardAction }) {
  return (
    <Link to={`/campaigns/${action.campaign_id}/prospects/${action.prospect_id}`} className="group grid gap-1 border-b border-line-soft px-5 py-4 transition-colors last:border-b-0 hover:bg-canvas sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
      <span className="min-w-0">
        <span className="block text-[14px] font-semibold text-ink">{action.prospect_name}</span>
        <span className="mt-1 block text-[13px] text-ink-soft">{action.reason}</span>
        <span className="mt-1.5 block text-[12px] text-ink-faint">{action.campaign_title}</span>
      </span>
      <span className="text-[13px] font-semibold text-action group-hover:text-ink">Open</span>
    </Link>
  )
}

function ActivityRow({ event }: { event: DashboardActivity }) {
  return (
    <div className="border-b border-line-soft py-3.5 last:border-b-0">
      <p className="text-[13px] leading-5 text-ink"><span className="font-semibold capitalize">{label(event.event_type)}</span><span className="text-ink-faint"> · </span>{event.prospect_name}</p>
      <p className="mt-1 text-[12px] text-ink-faint">{event.campaign_title} · {relativeTime(event.occurred_at)}</p>
    </div>
  )
}

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    api<DashboardSummary>('/dashboard/summary')
      .then((data) => {
        if (active) setSummary(data)
      })
      .catch((requestError: unknown) => {
        if (active) setError(requestError instanceof Error ? requestError.message : 'Could not load the dashboard.')
      })
    return () => {
      active = false
    }
  }, [])

  if (error) return <main className="workspace-page"><Notice kind="error">{error}</Notice></main>
  if (!summary) return <main className="workspace-page"><div className="h-80 animate-pulse rounded-card border border-line bg-card" /></main>

  const stats = [
    ['Need review', summary.pipeline.needs_research, 'Research required'],
    ['Ready to contact', summary.pipeline.ready_for_outreach, 'Approved prospects'],
    ['Replies', summary.pipeline.replied, 'Outreach responses'],
  ] as const
  const today = new Intl.DateTimeFormat(undefined, {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(new Date())

  return (
    <main className="workspace-page">
      <header className="page-heading-row">
        <div>
          <p className="page-date">{today}</p>
          <h1 className="page-title">Your prospecting workspace</h1>
          <p className="page-description">Review opportunities, take action, and keep campaigns moving.</p>
        </div>
        <Link to="/discover" className="primary-link-button">New campaign</Link>
      </header>

      <section className="mt-9 grid grid-cols-1 border-y border-line sm:grid-cols-3" aria-label="Work summary">
        {stats.map(([name, value, detail]) => (
          <div key={name} className="grid grid-cols-[3.25rem_1fr] items-center gap-3 border-b border-line px-2 py-5 last:border-b-0 sm:border-b-0 sm:border-r sm:px-7 sm:first:pl-2 sm:last:border-r-0">
            <p className="text-[30px] font-semibold leading-none tracking-[-0.04em] text-ink tabular-nums">{value}</p>
            <div>
              <p className="text-[13px] font-semibold text-ink">{name}</p>
              <p className="mt-1 text-[12px] text-ink-faint">{detail}</p>
            </div>
          </div>
        ))}
      </section>

      {summary.next_best_action && (
        <section className="mt-6 flex flex-col gap-3 border border-line bg-card px-5 py-4 sm:flex-row sm:items-center">
          <p className="shrink-0 text-[12px] font-semibold text-ink-soft">Next action</p>
          <div className="min-w-0 flex-1">
            <p className="text-[14px] font-semibold capitalize text-ink">{label(summary.next_best_action.action_type)} for {summary.next_best_action.prospect_name}</p>
            <p className="mt-0.5 text-[13px] text-ink-soft">{summary.next_best_action.reason}</p>
          </div>
          <Link to={`/campaigns/${summary.next_best_action.campaign_id}/prospects/${summary.next_best_action.prospect_id}`} className="text-[13px] font-semibold text-action hover:text-ink">Continue</Link>
        </section>
      )}

      <section className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,1.8fr)_minmax(17rem,0.8fr)]">
        <div>
          <div className="section-heading-row">
            <div><h2>Needs your attention</h2><p>Prospects and messages waiting for a decision.</p></div>
            <span>{summary.needs_attention.length}</span>
          </div>
          <div className="overflow-hidden border border-line bg-card">
            {summary.needs_attention.length === 0 ? (
              <div className="px-5 py-10"><p className="text-[14px] font-semibold text-ink">Nothing needs attention</p><p className="mt-1 text-[13px] text-ink-soft">New research and outreach tasks will appear here.</p></div>
            ) : summary.needs_attention.map((action) => (
              <ActionRow key={`${action.action_type}:${action.prospect_id}:${action.outreach_attempt_id ?? ''}`} action={action} />
            ))}
          </div>
        </div>

        <aside>
          <div className="section-heading-row"><div><h2>Recent activity</h2><p>Your latest prospecting updates.</p></div></div>
          <div className="border-t border-line">
            {summary.recent_activity.length === 0 ? (
              <div className="py-5"><p className="text-[13px] font-semibold text-ink">No activity yet</p><p className="mt-1 text-[12px] text-ink-soft">Campaign updates will appear here.</p></div>
            ) : summary.recent_activity.map((event) => (
              <ActivityRow key={`${event.event_type}:${event.prospect_id}:${event.occurred_at}`} event={event} />
            ))}
          </div>
        </aside>
      </section>

      <section className="mt-9 flex items-center justify-between border-t border-line pt-5">
        <div><h2 className="text-[14px] font-semibold text-ink">Your campaigns</h2><p className="mt-1 text-[13px] text-ink-soft">Return to discovery work and saved prospects.</p></div>
        <Link to="/campaigns" className="text-[13px] font-semibold text-action hover:text-ink">View campaigns</Link>
      </section>
    </main>
  )
}
