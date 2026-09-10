import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Notice } from '../components/ui'
import { api } from '../lib/api'
import type { CampaignProspect, CampaignResponse } from '../lib/types'

interface CampaignSummary {
  campaign: CampaignResponse
  prospects: CampaignProspect[]
}

function dateLabel(value: string): string {
  return new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(value))
}

export default function CampaignsPage() {
  const [items, setItems] = useState<CampaignSummary[]>([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    async function load() {
      try {
        const campaigns = await api<CampaignResponse[]>('/campaigns')
        const summaries = await Promise.all(
          campaigns.map(async (campaign) => ({
            campaign,
            prospects: await api<CampaignProspect[]>(`/campaigns/${campaign.id}/prospects`),
          })),
        )
        if (active) setItems(summaries)
      } catch (requestError) {
        if (active) setError(requestError instanceof Error ? requestError.message : 'Could not load campaigns.')
      } finally {
        if (active) setLoading(false)
      }
    }
    void load()
    return () => {
      active = false
    }
  }, [])

  const normalizedQuery = query.trim().toLowerCase()
  const visibleItems = normalizedQuery
    ? items.filter(({ campaign }) =>
        `${campaign.title} ${campaign.goal ?? ''}`.toLowerCase().includes(normalizedQuery),
      )
    : items

  return (
    <main className="workspace-page">
      <header className="page-heading-row">
        <div>
          <h1 className="page-title">Campaigns</h1>
          <p className="page-description">Create and manage your discovery campaigns.</p>
        </div>
        <Link to="/discover" className="primary-link-button">New campaign</Link>
      </header>

      {loading && <div className="mt-8 h-72 animate-pulse border border-line bg-card" />}
      {error && <div className="mt-8"><Notice kind="error">{error}</Notice></div>}

      {!loading && !error && (
        <section className="mt-8">
          <div className="mb-3 flex items-center justify-between border-b border-line">
            <div className="flex h-10 items-center border-b-2 border-action px-2 text-[13px] font-semibold text-ink">All</div>
            <span className="pb-2 text-[12px] text-ink-faint">{items.length} campaign{items.length === 1 ? '' : 's'}</span>
          </div>

          <div className="mb-4">
            <label htmlFor="campaign-search" className="sr-only">Search campaigns</label>
            <input
              id="campaign-search"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search campaigns"
              className="h-10 w-full max-w-md rounded-control border border-line bg-card px-3 text-[13px] text-ink outline-none placeholder:text-ink-faint focus:border-action focus:ring-1 focus:ring-action"
            />
          </div>

          <div className="overflow-hidden border border-line bg-card">
            <div className="hidden min-h-10 grid-cols-[minmax(18rem,1.5fr)_minmax(14rem,1fr)_6rem_6rem_7rem_4rem] items-center gap-4 border-b border-line bg-canvas px-5 text-[11px] font-semibold text-ink-soft md:grid">
              <span>Campaign</span><span>Objective</span><span>Saved</span><span>Ready</span><span>Updated</span><span />
            </div>

            {visibleItems.length === 0 ? (
              <div className="px-6 py-16 text-center">
                <h2 className="font-display text-[22px] font-bold tracking-[-0.025em] text-ink">{items.length === 0 ? 'No campaigns yet' : 'No matching campaigns'}</h2>
                <p className="mx-auto mt-2 max-w-sm text-[13px] text-ink-soft">{items.length === 0 ? 'Create a campaign to start finding businesses.' : 'Try a different search term.'}</p>
                {items.length === 0 && <Link to="/discover" className="primary-link-button mt-5">New campaign</Link>}
              </div>
            ) : visibleItems.map(({ campaign, prospects }, index) => {
              const ready = prospects.filter((prospect) => prospect.workflow_state === 'ready_for_outreach').length
              return (
                <article key={campaign.id} className="grid gap-3 border-b border-line-soft px-5 py-4 last:border-b-0 hover:bg-canvas md:grid-cols-[minmax(18rem,1.5fr)_minmax(14rem,1fr)_6rem_6rem_7rem_4rem] md:items-center md:gap-4">
                  <div className="min-w-0">
                    <p className="text-[11px] font-semibold text-ink-faint">{String(index + 1).padStart(2, '0')}</p>
                    <h2 className="mt-1 truncate text-[14px] font-semibold text-ink">{campaign.title}</h2>
                  </div>
                  <p className="line-clamp-2 text-[13px] leading-5 text-ink-soft">{campaign.goal ?? 'No objective recorded'}</p>
                  <p className="text-[12px] text-ink-soft"><span className="md:hidden">Saved: </span>{prospects.length}</p>
                  <p className="text-[12px] text-ink-soft"><span className="md:hidden">Ready: </span>{ready}</p>
                  <time dateTime={campaign.updated_at} className="text-[12px] text-ink-soft">{dateLabel(campaign.updated_at)}</time>
                  <Link to={`/prospects?campaign=${campaign.id}`} className="text-[13px] font-semibold text-action hover:text-ink">View</Link>
                </article>
              )
            })}
          </div>
        </section>
      )}
    </main>
  )
}
