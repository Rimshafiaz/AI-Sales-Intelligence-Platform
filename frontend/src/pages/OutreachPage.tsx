import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Notice } from '../components/ui'
import { api } from '../lib/api'
import type { OutreachAttempt, OutreachChannel, OutreachDraftOption, OutreachWorkbenchGroup } from '../lib/types'

function label(value: string): string {
  return value.replaceAll('_', ' ')
}

export default function OutreachPage() {
  const [groups, setGroups] = useState<OutreachWorkbenchGroup[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    async function load() {
      try {
        const workbench = await api<OutreachWorkbenchGroup[]>('/outreach-workbench')
        if (active) setGroups(workbench)
      } catch (requestError) {
        if (active) setError(requestError instanceof Error ? requestError.message : 'Could not load outreach.')
      } finally {
        if (active) setLoading(false)
      }
    }
    void load()
    return () => {
      active = false
    }
  }, [])

  return (
    <main className="workspace-page">
      <header className="border-b border-line pb-6">
        <h1 className="page-title">Outreach</h1>
        <p className="page-description">Draft, approve, send, and record responses.</p>
      </header>

      {loading && <div className="mt-8 h-44 animate-pulse bg-surface-container-low" />}
      {error && <div className="mt-8"><Notice kind="error">{error}</Notice></div>}
      {!loading && !error && groups.length === 0 && (
        <section className="py-12">
          <h2 className="text-headline-md font-semibold text-on-surface">No outreach yet</h2>
          <p className="mt-2 text-body-md text-on-surface-variant">Qualified prospects with verified contact details will appear here.</p>
        </section>
      )}

      <div className="divide-y divide-line">
        {groups.flatMap(({ campaign_id, campaign_title, prospects }) =>
          prospects.map((item) => (
            <article key={item.prospect.id} className="grid gap-6 py-7 lg:grid-cols-[minmax(15rem,0.7fr)_minmax(0,1.3fr)]">
              <div>
                <p className="text-label-sm text-on-surface-variant">{campaign_title}</p>
                <h2 className="mt-1 text-headline-md font-semibold text-on-surface">
                  {String(item.prospect.candidate_snapshot.company_name ?? 'Unnamed business')}
                </h2>
                <p className="mt-2 text-label-sm capitalize text-on-surface-variant">{label(item.prospect.workflow_state)}</p>
                <Link to={`/campaigns/${campaign_id}/prospects/${item.prospect.id}`} className="mt-3 inline-flex text-label-md font-semibold text-action hover:text-ink">Open prospect</Link>
              </div>
              <WorkbenchProspect
                campaignId={campaign_id}
                prospectId={item.prospect.id}
                headline={item.qualification_headline}
                opportunityReason={item.opportunity_reason}
                pitchAngle={item.pitch_angle}
                attempts={item.attempts}
                options={item.options}
              />
            </article>
          )),
        )}
      </div>
    </main>
  )
}

function WorkbenchProspect({
  campaignId,
  prospectId,
  headline,
  opportunityReason,
  pitchAngle,
  attempts: initialAttempts,
  options: initialOptions,
}: {
  campaignId: string
  prospectId: string
  headline: string
  opportunityReason: string
  pitchAngle: string | null
  attempts: OutreachAttempt[]
  options: OutreachDraftOption[]
}) {
  const [attempts, setAttempts] = useState(initialAttempts)
  const [options, setOptions] = useState(initialOptions)
  const [workingChannel, setWorkingChannel] = useState<OutreachChannel | null>(null)
  const [error, setError] = useState<string | null>(null)
  const attemptsByChannel = new Map<OutreachChannel, OutreachAttempt>()
  const optionsByChannel = new Map<OutreachChannel, OutreachDraftOption>()
  attempts.forEach((attempt) => {
    if (!attemptsByChannel.has(attempt.channel)) attemptsByChannel.set(attempt.channel, attempt)
  })
  options.forEach((option) => {
    if (!optionsByChannel.has(option.channel)) optionsByChannel.set(option.channel, option)
  })
  const channels = Array.from(new Set([...optionsByChannel.keys(), ...attemptsByChannel.keys()]))

  async function createDraft(option: OutreachDraftOption) {
    setWorkingChannel(option.channel)
    setError(null)
    try {
      const attempt = await api<OutreachAttempt>(
        `/campaigns/${campaignId}/prospects/${prospectId}/outreach-attempts`,
        {
          method: 'POST',
          body: {
            research_report_id: option.research_report_id,
            channel: option.channel,
            recipient: option.recipient,
          },
        },
      )
      setAttempts((current) => [attempt, ...current])
      setOptions((current) => current.filter((item) => item.channel !== option.channel))
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Could not create outreach draft.')
    } finally {
      setWorkingChannel(null)
    }
  }

  return (
    <section aria-label="Outreach summary">
      <p className="text-label-sm font-semibold text-ink">{headline}</p>
      <p className="mt-1 max-w-2xl text-body-sm text-on-surface-variant">{opportunityReason}</p>
      {pitchAngle && <p className="mt-2 max-w-2xl text-body-sm font-medium text-on-surface">{pitchAngle}</p>}
      {error && <p className="mt-3 text-body-sm text-error">{error}</p>}
      <div className="mt-4 divide-y divide-line-soft border-y border-line-soft">
        {channels.map((channel) => {
          const attempt = attemptsByChannel.get(channel)
          const option = optionsByChannel.get(channel)
          return (
            <div key={channel} className="flex flex-wrap items-center justify-between gap-3 py-3">
              <div>
                <p className="text-label-md font-semibold capitalize text-on-surface">{label(channel)}</p>
                <p className="mt-0.5 text-label-sm text-on-surface-variant">{attempt?.recipient ?? option?.recipient}</p>
              </div>
              {attempt ? (
                <AttemptAction campaignId={campaignId} prospectId={prospectId} attempt={attempt} />
              ) : option ? (
                <button type="button" disabled={workingChannel !== null} onClick={() => void createDraft(option)} className="rounded-control border border-secondary px-3 py-1.5 text-label-md font-medium text-secondary transition-colors hover:bg-secondary-container focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary disabled:opacity-60">
                  Create {label(channel)} draft
                </button>
              ) : null}
            </div>
          )
        })}
      </div>
    </section>
  )
}

function AttemptAction({ campaignId, prospectId, attempt }: { campaignId: string; prospectId: string; attempt: OutreachAttempt }) {
  const detailUrl = `/campaigns/${campaignId}/prospects/${prospectId}`
  if (attempt.status === 'draft' || attempt.status === 'failed') {
    return <Link to={detailUrl} className="text-label-md font-semibold text-action hover:text-ink">Continue draft</Link>
  }
  if (attempt.status === 'approved') {
    return <Link to={detailUrl} className="text-label-md font-semibold text-action hover:text-ink">Approved / Send</Link>
  }
  return <span className="text-label-md font-medium capitalize text-on-surface-variant">{label(attempt.status)}</span>
}
