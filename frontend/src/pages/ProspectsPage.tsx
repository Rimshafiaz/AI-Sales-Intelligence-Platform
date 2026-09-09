import { useEffect, useState } from 'react'
import { CircleAlert, Loader2, UserRound } from 'lucide-react'
import { api } from '../lib/api'
import type { CampaignProspect, CampaignResponse } from '../lib/types'

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
                  <div>
                    <h3 className="font-medium text-on-surface">{String(prospect.candidate_snapshot.company_name ?? 'Unnamed business')}</h3>
                    <p className="mt-1 text-body-sm text-on-surface-variant">{String(prospect.candidate_snapshot.formatted_address ?? 'Location not listed')}</p>
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
