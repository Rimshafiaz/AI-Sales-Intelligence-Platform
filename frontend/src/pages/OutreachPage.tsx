import { useEffect, useState } from 'react'
import { Notice } from '../components/ui'
import { api } from '../lib/api'
import type { CampaignProspect, CampaignResponse } from '../lib/types'
import { ProspectOutreach } from './ProspectsPage'

interface CampaignProspects {
  campaign: CampaignResponse
  prospects: CampaignProspect[]
}

export default function OutreachPage() {
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
        <h1 className="text-headline-xl font-semibold tracking-tight text-brand">Outreach</h1>
        <p className="mt-2 max-w-xl text-body-md text-on-surface-variant">Draft, approve, send, and record responses.</p>
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
        {groups.flatMap(({ campaign, prospects }) =>
          prospects.map((prospect) => (
            <section key={prospect.id} className="grid gap-5 py-6 lg:grid-cols-[minmax(14rem,0.6fr)_minmax(0,1.4fr)]">
              <div>
                <p className="text-label-sm text-on-surface-variant">{campaign.title}</p>
                <h2 className="mt-1 text-headline-md font-semibold text-on-surface">
                  {String(prospect.candidate_snapshot.company_name ?? 'Unnamed business')}
                </h2>
              </div>
              <ProspectOutreach campaignId={campaign.id} prospect={prospect} />
            </section>
          )),
        )}
      </div>
    </main>
  )
}
