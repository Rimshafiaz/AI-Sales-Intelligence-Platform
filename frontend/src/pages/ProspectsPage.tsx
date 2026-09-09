import { useEffect, useState } from 'react'
import { CircleAlert, Loader2, UserRound } from 'lucide-react'
import { api } from '../lib/api'
import type {
  CampaignProspect,
  CampaignResponse,
  OutreachAttempt,
  OutreachDraftOption,
} from '../lib/types'

interface CampaignProspects {
  campaign: CampaignResponse
  prospects: CampaignProspect[]
}

function label(value: string): string {
  return value.replaceAll('_', ' ')
}

export default function ProspectsPage() {
  const [groups, setGroups] = useState<CampaignProspects[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    async function load() {
      try {
        const campaigns = await api<CampaignResponse[]>('/campaigns')
        const loaded = await Promise.all(
          campaigns.map(async (campaign) => ({
            campaign,
            prospects: await api<CampaignProspect[]>(`/campaigns/${campaign.id}/prospects`),
          })),
        )
        if (active) setGroups(loaded.filter((group) => group.prospects.length > 0))
      } catch (requestError) {
        if (active) setError(requestError instanceof Error ? requestError.message : 'Could not load prospects.')
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
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <div className="mb-8 flex items-end justify-between gap-4">
        <div>
          <p className="label-caps text-secondary">Prospect workspace</p>
          <h1 className="mt-1 font-display text-headline-xl font-semibold text-on-surface">Saved prospects</h1>
          <p className="mt-2 max-w-2xl text-body-md text-on-surface-variant">
            Candidates you explicitly saved from a campaign. Discovery records remain temporary until saved.
          </p>
        </div>
        <UserRound className="hidden text-secondary sm:block" size={28} />
      </div>

      {loading && <div className="flex items-center gap-2 text-body-sm text-on-surface-variant"><Loader2 size={16} className="animate-spin" />Loading prospects...</div>}
      {error && <div className="flex items-start gap-2 rounded-lg bg-error-container/40 p-3 text-body-sm text-on-surface"><CircleAlert size={16} className="mt-0.5 text-error" />{error}</div>}
      {!loading && !error && groups.length === 0 && (
        <section className="rounded-card bg-surface-container-lowest p-space-lg shadow-md">
          <p className="font-display text-headline-md font-semibold text-on-surface">No saved prospects yet</p>
          <p className="mt-2 text-body-md text-on-surface-variant">Save an evidence-backed candidate from Discovery to keep it in this workspace.</p>
        </section>
      )}
      <div className="space-y-6">
        {groups.map(({ campaign, prospects }) => (
          <section key={campaign.id} className="rounded-card bg-surface-container-lowest p-space-lg shadow-md">
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="font-display text-headline-md font-semibold text-on-surface">{campaign.title}</h2>
              <span className="text-label-md text-on-surface-variant">{prospects.length} saved</span>
            </div>
            <div className="divide-y divide-line-soft">
              {prospects.map((prospect) => (
                <article key={prospect.id} className="flex flex-col gap-3 py-4 first:pt-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0 flex-1">
                    <h3 className="font-medium text-on-surface">{String(prospect.candidate_snapshot.company_name ?? 'Unnamed business')}</h3>
                    <p className="mt-1 text-body-sm text-on-surface-variant">{String(prospect.candidate_snapshot.formatted_address ?? 'Location not listed')}</p>
                    <ProspectOutreach campaignId={campaign.id} prospect={prospect} />
                  </div>
                  <div className="flex items-center gap-3 text-label-md">
                    <span className="rounded-full bg-secondary-container px-2.5 py-1 text-on-secondary-container">{label(prospect.workflow_state)}</span>
                    <span className="text-on-surface-variant">Next: {label(prospect.next_action)}</span>
                  </div>
                </article>
              ))}
            </div>
          </section>
        ))}
      </div>
    </main>
  )
}

function ProspectOutreach({ campaignId, prospect }: { campaignId: string; prospect: CampaignProspect }) {
  const [attempts, setAttempts] = useState<OutreachAttempt[]>([])
  const [options, setOptions] = useState<OutreachDraftOption[]>([])
  const [working, setWorking] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    async function load() {
      try {
        const [savedAttempts, draftOptions] = await Promise.all([
          api<OutreachAttempt[]>(`/campaigns/${campaignId}/prospects/${prospect.id}/outreach-attempts`),
          api<OutreachDraftOption[]>(`/campaigns/${campaignId}/prospects/${prospect.id}/outreach-options`),
        ])
        if (active) {
          setAttempts(savedAttempts)
          setOptions(draftOptions)
        }
      } catch (requestError) {
        if (active) setError(requestError instanceof Error ? requestError.message : 'Could not load outreach.')
      }
    }
    void load()
    return () => {
      active = false
    }
  }, [campaignId, prospect.id])

  async function createDraft(option: OutreachDraftOption) {
    setWorking(true)
    setError(null)
    try {
      const attempt = await api<OutreachAttempt>(
        `/campaigns/${campaignId}/prospects/${prospect.id}/outreach-attempts`,
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
      setOptions((current) => current.filter((item) => item !== option))
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Could not create outreach draft.')
    } finally {
      setWorking(false)
    }
  }

  if (attempts.length === 0 && options.length === 0 && !error) return null

  return (
    <div className="mt-4 space-y-3 border-t border-line-soft pt-3">
      <p className="text-label-sm font-semibold uppercase tracking-wide text-secondary">Outreach</p>
      {error && <p className="text-body-sm text-error">{error}</p>}
      {options.map((option) => (
        <button key={`${option.research_report_id}:${option.channel}:${option.recipient}`} type="button" disabled={working} onClick={() => createDraft(option)} className="rounded-control border border-secondary px-3 py-1.5 text-label-md font-medium text-secondary hover:bg-secondary-container disabled:opacity-60">
          Create {option.channel} draft for {option.recipient}
        </button>
      ))}
      {attempts.map((attempt) => (
        <OutreachAttemptCard
          key={attempt.id}
          attempt={attempt}
          working={working}
          setWorking={setWorking}
          setError={setError}
          onChanged={(updated) => setAttempts((current) => current.map((item) => item.id === updated.id ? updated : item))}
        />
      ))}
    </div>
  )
}

function OutreachAttemptCard({
  attempt,
  working,
  setWorking,
  setError,
  onChanged,
}: {
  attempt: OutreachAttempt
  working: boolean
  setWorking: (working: boolean) => void
  setError: (error: string | null) => void
  onChanged: (attempt: OutreachAttempt) => void
}) {
  const [subject, setSubject] = useState(attempt.subject ?? '')
  const [body, setBody] = useState(attempt.body)
  const editable = attempt.status === 'draft' || attempt.status === 'approved'
  const changed = subject !== (attempt.subject ?? '') || body !== attempt.body

  async function saveDraft(): Promise<OutreachAttempt> {
    return api<OutreachAttempt>(`/outreach-attempts/${attempt.id}/draft`, {
      method: 'PATCH',
      body: { subject: attempt.channel === 'email' ? subject : null, body },
    })
  }

  async function run(action: 'save' | 'approve' | 'sent') {
    setWorking(true)
    setError(null)
    try {
      let updated = attempt
      if (action === 'save' || (action === 'approve' && changed)) updated = await saveDraft()
      if (action === 'approve') {
        updated = await api<OutreachAttempt>(`/outreach-attempts/${attempt.id}/approve`, { method: 'POST' })
      }
      if (action === 'sent') {
        updated = await api<OutreachAttempt>(`/outreach-attempts/${attempt.id}/manual-linkedin-send`, { method: 'POST' })
      }
      onChanged(updated)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Could not update outreach.')
    } finally {
      setWorking(false)
    }
  }

  async function recordOutcome(outcome: 'interested' | 'not_interested' | 'no_response', replied: boolean) {
    setWorking(true)
    setError(null)
    try {
      const updated = await api<OutreachAttempt>(`/outreach-attempts/${attempt.id}/manual-outcome`, {
        method: 'POST',
        body: { outcome, replied },
      })
      onChanged(updated)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Could not record outreach outcome.')
    } finally {
      setWorking(false)
    }
  }

  return (
    <div className="rounded-lg bg-surface-container-low p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-label-md font-medium text-on-surface">{label(attempt.channel)} / {attempt.recipient}</p>
        <span className="rounded-full bg-surface-container-high px-2 py-0.5 text-label-sm text-on-surface-variant">{label(attempt.status)}</span>
      </div>
      {attempt.channel === 'email' && (
        <input aria-label="Email subject" disabled={!editable || working} value={subject} onChange={(event) => setSubject(event.target.value)} className="mt-3 w-full rounded-control border border-line-soft bg-surface-container-lowest px-3 py-2 text-body-sm text-on-surface" />
      )}
      <textarea aria-label={`${label(attempt.channel)} message`} disabled={!editable || working} value={body} onChange={(event) => setBody(event.target.value)} rows={6} className="mt-2 w-full rounded-control border border-line-soft bg-surface-container-lowest px-3 py-2 text-body-sm text-on-surface" />
      {editable && (
        <div className="mt-3 flex flex-wrap gap-2">
          <button type="button" disabled={working || !changed} onClick={() => void run('save')} className="rounded-control border border-secondary px-3 py-1.5 text-label-md font-medium text-secondary disabled:opacity-60">Save changes</button>
          {(attempt.status === 'draft' || changed) && <button type="button" disabled={working} onClick={() => void run('approve')} className="rounded-control bg-primary px-3 py-1.5 text-label-md font-medium text-on-primary disabled:opacity-60">{attempt.status === 'approved' ? 'Approve changes' : 'Approve draft'}</button>}
        </div>
      )}
      {attempt.edited_by_user && <p className="mt-2 text-label-sm text-on-surface-variant">User-edited after evidence-grounded generation.</p>}
      {attempt.status === 'approved' && attempt.channel === 'email' && !changed && <p className="mt-3 text-label-sm text-on-surface-variant">Approved and waiting for connected Gmail sending in M84.</p>}
      {attempt.status === 'approved' && attempt.channel === 'linkedin' && !changed && (
        <div className="mt-3 flex flex-wrap gap-2">
          <button type="button" disabled={working} onClick={() => void navigator.clipboard.writeText(body)} className="rounded-control border border-secondary px-3 py-1.5 text-label-md font-medium text-secondary disabled:opacity-60">Copy message</button>
          <a href={attempt.recipient} target="_blank" rel="noreferrer" className="rounded-control border border-secondary px-3 py-1.5 text-label-md font-medium text-secondary">Open LinkedIn</a>
          <button type="button" disabled={working} onClick={() => void run('sent')} className="rounded-control bg-primary px-3 py-1.5 text-label-md font-medium text-on-primary disabled:opacity-60">Mark sent</button>
        </div>
      )}
      {attempt.channel === 'linkedin' && (attempt.status === 'sent' || attempt.status === 'replied') && (
        <div className="mt-3 flex flex-wrap gap-2">
          <button type="button" disabled={working} onClick={() => void recordOutcome('interested', true)} className="rounded-control border border-secondary px-3 py-1.5 text-label-md text-secondary disabled:opacity-60">Replied: interested</button>
          <button type="button" disabled={working} onClick={() => void recordOutcome('not_interested', true)} className="rounded-control border border-secondary px-3 py-1.5 text-label-md text-secondary disabled:opacity-60">Replied: not interested</button>
          {attempt.status === 'sent' && <button type="button" disabled={working} onClick={() => void recordOutcome('no_response', false)} className="rounded-control border border-line-soft px-3 py-1.5 text-label-md text-on-surface-variant disabled:opacity-60">Close: no response</button>}
        </div>
      )}
      {attempt.outcome && <p className="mt-2 text-label-sm text-on-surface-variant">Outcome: {label(attempt.outcome)}</p>}
    </div>
  )
}
