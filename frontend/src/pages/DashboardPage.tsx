import { useEffect, useState } from 'react'
import { ArrowRight, Clock3 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Notice } from '../components/ui'
import { api } from '../lib/api'
import type { DashboardAction, DashboardActivity, DashboardSummary } from '../lib/types'


function label(value: string): string {
  return value.replaceAll('_', ' ')
}

function relativeTime(iso: string): string {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000))
  if (seconds < 60) return 'just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return days === 1 ? 'yesterday' : `${days}d ago`
}

function ActionRow({ action }: { action: DashboardAction }) {
  return (
    <Link to="/prospects" className="group flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-surface-container-low focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary">
      <span className="min-w-0 flex-1">
        <span className="block text-body-md font-medium text-on-surface">{action.prospect_name}</span>
        <span className="mt-0.5 block text-body-sm text-on-surface-variant">{action.reason}</span>
      </span>
      {action.channel && <span className="rounded-full bg-surface-container-high px-2 py-0.5 text-label-sm text-on-surface-variant">{action.channel}</span>}
      <ArrowRight size={15} className="shrink-0 text-outline transition-colors group-hover:text-on-surface" />
    </Link>
  )
}

function ActivityRow({ event }: { event: DashboardActivity }) {
  return (
    <div className="flex items-start gap-3 py-2">
      <span className="mt-2 h-2 w-2 shrink-0 rounded-full bg-secondary" />
      <div className="min-w-0 flex-1">
        <p className="text-body-sm text-on-surface"><span className="font-medium capitalize">{label(event.event_type)}</span> · {event.prospect_name}</p>
        <p className="text-label-sm text-on-surface-variant">{event.campaign_title} · {relativeTime(event.occurred_at)}</p>
      </div>
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

  if (error) {
    return <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6"><Notice kind="error">{error}</Notice></main>
  }
  if (!summary) {
    return <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6"><div className="h-48 animate-pulse rounded-card bg-surface-container-lowest shadow-sm" /></main>
  }

  const stats = [
    ['Saved', summary.pipeline.prospects_saved],
    ['Need research', summary.pipeline.needs_research],
    ['Ready for outreach', summary.pipeline.ready_for_outreach],
    ['Contacted', summary.pipeline.contacted],
    ['Replied', summary.pipeline.replied],
    ['Interested', summary.pipeline.interested],
  ] as const
  return (
    <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-8 sm:px-6">
      <section>
        <p className="label-caps text-secondary">SalesLens workspace</p>
        <h1 className="mt-1 font-display text-headline-xl font-semibold tracking-tight text-on-surface">What needs your attention</h1>
        <p className="mt-2 max-w-2xl text-body-md text-on-surface-variant">Move evidence-backed prospects from research to outreach and follow-up.</p>
      </section>

      <section className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6" aria-label="Prospect pipeline">
        {stats.map(([name, value]) => (
          <div key={name} className="rounded-card border border-line-soft bg-surface-container-lowest p-4 shadow-sm">
            <p className="font-display text-headline-lg font-semibold text-on-surface">{value}</p>
            <p className="mt-1 text-label-sm text-on-surface-variant">{name}</p>
          </div>
        ))}
      </section>

      {summary.next_best_action ? (
        <Link to="/prospects" className="group flex w-full items-center gap-4 border-y border-line-soft py-4 text-left hover:bg-surface-container-low">
          <span className="label-caps shrink-0 text-secondary">Next action</span>
          <span className="min-w-0 flex-1">
            <span className="block text-body-md font-medium text-on-surface">{label(summary.next_best_action.action_type)} · {summary.next_best_action.prospect_name}</span>
            <span className="mt-0.5 block text-body-sm text-on-surface-variant">{summary.next_best_action.reason}</span>
          </span>
          <ArrowRight size={16} className="shrink-0 text-outline group-hover:text-on-surface" />
        </Link>
      ) : (
        <Link to="/discover" className="group flex w-full items-center gap-4 border-y border-line-soft py-4 text-left hover:bg-surface-container-low">
          <span className="label-caps shrink-0 text-secondary">Next action</span>
          <span className="min-w-0 flex-1 text-body-md font-medium text-on-surface">Start a discovery campaign</span>
          <ArrowRight size={16} className="shrink-0 text-outline group-hover:text-on-surface" />
        </Link>
      )}

      <section className="grid gap-6 lg:grid-cols-12">
        <div className="space-y-6 lg:col-span-8">
          <div>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-display text-headline-md font-semibold text-on-surface">Needs attention</h2>
              <span className="text-label-sm text-on-surface-variant">{summary.needs_attention.length}</span>
            </div>
            <div className="divide-y divide-line-soft rounded-card border border-line-soft bg-surface-container-lowest shadow-sm">
              {summary.needs_attention.length === 0 ? <p className="p-4 text-body-sm text-on-surface-variant">No prospect or draft currently needs attention.</p> : summary.needs_attention.map((action) => <ActionRow key={`${action.action_type}:${action.prospect_id}:${action.outreach_attempt_id ?? ''}`} action={action} />)}
            </div>
          </div>

          <div>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="flex items-center gap-2 font-display text-headline-md font-semibold text-on-surface"><Clock3 size={18} />Follow-ups due</h2>
              <span className="text-label-sm text-on-surface-variant">{summary.follow_ups_due.length}</span>
            </div>
            <div className="divide-y divide-line-soft rounded-card border border-line-soft bg-surface-container-lowest shadow-sm">
              {summary.follow_ups_due.length === 0 ? <p className="p-4 text-body-sm text-on-surface-variant">No sent outreach currently needs a follow-up.</p> : summary.follow_ups_due.map((action) => <ActionRow key={`follow-up:${action.outreach_attempt_id}`} action={action} />)}
            </div>
          </div>
        </div>

        <div className="lg:col-span-4">
          <h2 className="mb-3 font-display text-headline-md font-semibold text-on-surface">Recent activity</h2>
          <div className="rounded-card border border-line-soft bg-surface-container-lowest px-4 py-2 shadow-sm">
            {summary.recent_activity.length === 0 ? <p className="py-3 text-body-sm text-on-surface-variant">No prospecting activity yet.</p> : summary.recent_activity.map((event) => <ActivityRow key={`${event.event_type}:${event.prospect_id}:${event.occurred_at}`} event={event} />)}
          </div>
        </div>
      </section>
    </main>
  )
}
