import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Notice } from '../components/ui'
import { api } from '../lib/api'
import type { CampaignProspect, CampaignResponse, EvidenceSignal } from '../lib/types'
import { ProspectOutreach } from './ProspectsPage'

function label(value: string): string {
  return value.replaceAll('_', ' ')
}

export default function ProspectPage() {
  const { campaignId, prospectId } = useParams()
  const [campaign, setCampaign] = useState<CampaignResponse | null>(null)
  const [prospect, setProspect] = useState<CampaignProspect | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    async function load() {
      if (!campaignId || !prospectId) {
        setError('The prospect link is incomplete.')
        setLoading(false)
        return
      }
      try {
        const [campaignData, prospects] = await Promise.all([
          api<CampaignResponse>(`/campaigns/${campaignId}`),
          api<CampaignProspect[]>(`/campaigns/${campaignId}/prospects`),
        ])
        const selected = prospects.find((item) => item.id === prospectId)
        if (!selected) throw new Error('Prospect not found.')
        if (active) {
          setCampaign(campaignData)
          setProspect(selected)
        }
      } catch (requestError) {
        if (active) setError(requestError instanceof Error ? requestError.message : 'Could not load the prospect.')
      } finally {
        if (active) setLoading(false)
      }
    }
    void load()
    return () => {
      active = false
    }
  }, [campaignId, prospectId])

  if (loading) return <main className="workspace-page"><div className="h-48 animate-pulse bg-surface-container-low" /></main>
  if (error || !campaign || !prospect || !campaignId) return <main className="workspace-page"><Notice kind="error">{error ?? 'Prospect not found.'}</Notice><Link to="/prospects" className="mt-4 inline-flex text-label-md font-semibold text-action hover:text-ink">Back to prospects</Link></main>

  const candidate = prospect.candidate_snapshot
  const evidence = prospect.evidence_snapshot as EvidenceSignal[]
  const name = String(candidate.company_name ?? 'Unnamed business')

  return (
    <main className="workspace-page">
      <Link to="/prospects" className="text-label-md font-medium text-on-surface-variant hover:text-on-surface">Back to prospects</Link>
      <header className="mt-6 border-b border-line pb-6">
        <p className="text-label-sm text-on-surface-variant">{campaign.title}</p>
        <div className="mt-2 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div>
            <h1 className="page-title">{name}</h1>
            <p className="mt-2 text-body-md text-on-surface-variant">{String(candidate.formatted_address ?? 'Location not listed')}</p>
          </div>
          <div className="text-left sm:text-right">
            <p className="text-label-sm text-on-surface-variant">Current state</p>
            <p className="mt-1 text-body-sm font-semibold capitalize text-on-surface">{label(prospect.workflow_state)}</p>
          </div>
        </div>
      </header>

      <section className="grid gap-10 py-8 lg:grid-cols-[minmax(0,1.4fr)_minmax(18rem,0.8fr)]">
        <div>
          <h2 className="border-b border-line pb-3 text-headline-md font-semibold text-on-surface">Evidence</h2>
          {evidence.length === 0 ? (
            <p className="py-5 text-body-sm text-on-surface-variant">No accepted evidence has been saved yet.</p>
          ) : (
            <div className="divide-y divide-line-soft">
              {evidence.map((item, index) => (
                <article key={`${item.signal_type}:${index}`} className="py-4">
                  <p className="text-label-sm font-semibold capitalize text-on-surface">{label(item.signal_type)}</p>
                  <p className="mt-1 text-body-sm text-on-surface-variant">{item.supporting_value}</p>
                  <p className="mt-2 text-label-sm text-on-surface-variant">Source: {item.source.source_url ? <a href={item.source.source_url} target="_blank" rel="noreferrer" className="font-semibold text-action hover:text-ink">{item.source.provider}</a> : item.source.provider}</p>
                </article>
              ))}
            </div>
          )}
        </div>

        <aside>
          <h2 className="border-b border-line pb-3 text-headline-md font-semibold text-on-surface">Next action</h2>
          <p className="py-4 text-body-md font-medium capitalize text-on-surface">{label(prospect.next_action)}</p>
          <ProspectOutreach campaignId={campaignId} prospect={prospect} />
        </aside>
      </section>
    </main>
  )
}
