import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowUpRight,
  CircleAlert,
  Loader2,
} from 'lucide-react'
import { api } from '../lib/api'
import type {
  CampaignRecommendedBatchResponse,
  CampaignResponse,
  CampaignRunResponse,
  DiscoveryObjective,
  DiscoveryOpportunityPreparationResponse,
  DiscoveryResponse,
  OpportunityModelId,
  ParseDiscoveryResponse,
  PreparedDiscoveryOpportunity,
} from '../lib/types'
import { Button } from '../components/ui'

interface GoalForm {
  goal: string
  region: string
  company_size: string
}

const EMPTY_FORM: GoalForm = { goal: '', region: '', company_size: '' }

const OBJECTIVE_CHIPS = [
  { value: 'service_pitch', label: 'Pitch a service' },
  { value: 'client_prospecting', label: 'Find clients' },
]

const GOAL_TYPE_LABELS: Record<string, string> = {
  service_pitch: 'Pitch a service',
  client_prospecting: 'Find clients',
  investment: 'Investment',
  hiring: 'Hiring',
  market_research: 'Market research',
  other: 'Custom goal',
}

const MODEL_LABELS: Record<OpportunityModelId, string> = {
  'web_conversion.no_verified_web_presence': 'No website listed by provider',
  'web_conversion.mobile_performance': 'Mobile performance',
  'web_conversion.booking_contact_path': 'Booking or inquiry path',
  'web_conversion.restaurant_reservation_path': 'Restaurant reservation path',
  'web_conversion.restaurant_customer_path': 'Restaurant customer path',
  'web_conversion.fitness_membership_path': 'Fitness membership path',
  'web_conversion.retail_product_path': 'Retail product path',
  'web_conversion.clinic_patient_path': 'Clinic patient path',
  'social_presence.dormant_official_presence': 'Dormant official social presence',
}

function domainOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

function joinItems(items: string[]): string {
  return items.join(' · ')
}

function opportunityModelsFor(objective: DiscoveryObjective): OpportunityModelId[] {
  const text = [
    objective.offering,
    ...objective.triggers,
    ...objective.signals_to_look_for,
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
  const industry = objective.target_sectors.join(' ').toLowerCase()
  const modelIds: OpportunityModelId[] = []
  const hasWebIntent = /website|web design|web development|landing page|conversion|cms|wordpress|seo/.test(text)
  const redesignOnly =
    /redesign|rebuild|revamp|overhaul|website refresh/.test(text) &&
    !/new website|website development|build a website|create a website|landing page|no website|web presence/.test(
      text,
    )
  const hasSocialIntent = /social|instagram|tiktok|content|reels|short.form|short form/.test(text)

  if (hasWebIntent) {
    if (!redesignOnly) {
      modelIds.push('web_conversion.no_verified_web_presence')
    }
    modelIds.push(
      'web_conversion.mobile_performance',
    )
    if (/restaurant|cafe/.test(industry)) {
      modelIds.push('web_conversion.restaurant_customer_path')
    } else if (/fitness|gym/.test(industry)) {
      modelIds.push('web_conversion.fitness_membership_path')
    } else if (/boutique|retail|fashion/.test(industry)) {
      modelIds.push('web_conversion.retail_product_path')
    } else if (/dental|dentist|clinic/.test(industry)) {
      modelIds.push('web_conversion.clinic_patient_path')
    } else if (/booking|appointment|inquiry/.test(text)) {
      modelIds.push('web_conversion.booking_contact_path')
    }
  }
  if (hasSocialIntent) modelIds.push('social_presence.dormant_official_presence')
  return [...new Set(modelIds)].slice(0, 3)
}

function recommendedIndexes(opportunities: PreparedDiscoveryOpportunity[]): number[] {
  const selected: number[] = []
  const representedModels = new Set<OpportunityModelId>()
  for (const opportunity of opportunities) {
    const primaryModel = opportunity.queue_entry.reasons[0]?.model_id
    if (primaryModel && !representedModels.has(primaryModel)) {
      selected.push(opportunity.queue_entry.candidate_index)
      representedModels.add(primaryModel)
    }
    if (selected.length === 3) return selected
  }
  for (const opportunity of opportunities) {
    const index = opportunity.queue_entry.candidate_index
    if (!selected.includes(index)) selected.push(index)
    if (selected.length === 3) break
  }
  return selected
}

function providerSummary(result: DiscoveryResponse): Record<string, number> {
  return result.candidates.reduce<Record<string, number>>((summary, candidate) => {
    const provider = candidate.source_provider ?? 'unknown'
    summary[provider] = (summary[provider] ?? 0) + 1
    return summary
  }, {})
}

function ErrorNotice({ message }: { message: string }) {
  return (
    <div className="flex items-start gap-2 rounded-lg bg-error-container/40 p-3">
      <CircleAlert size={16} className="mt-0.5 shrink-0 text-error" />
      <p className="text-body-sm text-on-surface">{message}</p>
    </div>
  )
}

export default function DiscoveryPage() {
  const navigate = useNavigate()
  const [form, setForm] = useState<GoalForm>(EMPTY_FORM)
  const [activeChip, setActiveChip] = useState<string | null>(null)
  const [step, setStep] = useState<'form' | 'confirm'>('form')
  const [parsing, setParsing] = useState(false)
  const [objective, setObjective] = useState<DiscoveryObjective | null>(null)
  const [gate, setGate] = useState<{ supported: boolean; message: string | null } | null>(null)
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [result, setResult] = useState<DiscoveryResponse | null>(null)
  const [queue, setQueue] = useState<DiscoveryOpportunityPreparationResponse | null>(null)
  const [selectedQueueIndexes, setSelectedQueueIndexes] = useState<number[]>([])
  const [startingBatch, setStartingBatch] = useState(false)
  const [savingProspectIndex, setSavingProspectIndex] = useState<number | null>(null)
  const [savedProspectIndexes, setSavedProspectIndexes] = useState<number[]>([])
  const [campaignContext, setCampaignContext] = useState<{ campaignId: string; campaignRunId: string } | null>(null)
  const [handoffError, setHandoffError] = useState<string | null>(null)
  const selectedModels = objective ? opportunityModelsFor(objective) : []

  function update(field: keyof GoalForm, value: string) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  function criteriaPayload() {
    return {
      goal: form.goal.trim(),
      objective: objective ?? undefined,
      region: form.region.trim() || undefined,
      company_size: form.company_size.trim() || undefined,
    }
  }

  async function handleParse(event: FormEvent) {
    event.preventDefault()
    if (parsing) return

    const goal = form.goal.trim()
    if (goal.length < 3) {
      setSearchError('Describe what you are looking for first.')
      return
    }

    setParsing(true)
    setSearchError(null)
    setResult(null)
    setQueue(null)
    setSelectedQueueIndexes([])
    setCampaignContext(null)
    setSavedProspectIndexes([])
    try {
      const response = await api<ParseDiscoveryResponse>('/company-discovery/parse', {
        method: 'POST',
        body: {
          goal,
          objective_hint: activeChip ?? undefined,
          region: form.region.trim() || undefined,
          company_size: form.company_size.trim() || undefined,
        },
      })
      setObjective(response.objective)
      setGate({ supported: response.supported, message: response.message })
      setStep('confirm')
    } catch (error) {
      setSearchError(error instanceof Error ? error.message : 'Could not interpret the goal.')
    } finally {
      setParsing(false)
    }
  }

  async function handleConfirmedRun() {
    if (searching || !objective) return
    if (selectedModels.length === 0) {
      setSearchError('SalesLens currently supports Web & Conversion and Social Presence & Content opportunity models only.')
      return
    }

    setSearching(true)
    setSearchError(null)
    setHandoffError(null)
    setCampaignContext(null)
    setSavedProspectIndexes([])
    try {
      const criteria = criteriaPayload()
      const discovery = await api<DiscoveryResponse>('/company-discovery', {
        method: 'POST',
        body: criteria,
      })
      const preparedQueue = await api<DiscoveryOpportunityPreparationResponse>(
        '/company-discovery/prepare-opportunity-queue',
        {
          method: 'POST',
          body: {
            criteria,
            model_selection: {
              model_ids: selectedModels,
              confirmed_by_user: true,
            },
            candidates: discovery.candidates,
          },
        },
      )
      setResult(discovery)
      setQueue(preparedQueue)
      setSelectedQueueIndexes(recommendedIndexes(preparedQueue.candidates))
    } catch (error) {
      setSearchError(error instanceof Error ? error.message : 'Discovery failed.')
    } finally {
      setSearching(false)
    }
  }

  function toggleQueueCandidate(candidateIndex: number) {
    const isSelected = selectedQueueIndexes.includes(candidateIndex)
    if (!isSelected && selectedQueueIndexes.length >= 3) {
      setHandoffError('Choose up to three prospects for one evidence-review batch.')
      return
    }
    setHandoffError(null)
    setSelectedQueueIndexes((current) =>
      isSelected
        ? current.filter((index) => index !== candidateIndex)
        : [...current, candidateIndex],
    )
  }

  async function startRecommendedResearch() {
    if (!queue || !result || !objective || startingBatch) return
    const opportunities = queue.candidates.filter((opportunity) =>
      selectedQueueIndexes.includes(opportunity.queue_entry.candidate_index),
    )
    if (opportunities.length === 0) {
      setHandoffError('Select at least one evidence-backed prospect first.')
      return
    }

    setStartingBatch(true)
    setHandoffError(null)
    try {
      const { campaignRunId } = await ensureCampaignRun()
      const batch = await api<CampaignRecommendedBatchResponse>(
        `/campaigns/runs/${campaignRunId}/recommended-batch`,
        { method: 'POST', body: { opportunities } },
      )
      await Promise.all(
        batch.selections.map((selection) =>
          api(`/research-requests/${selection.research_request_id}/evidence-gate`, {
            method: 'POST',
          }),
        ),
      )
      navigate(`/research/${batch.selections[0].research_request_id}`, {
        state: {
          batchRequestIds: batch.selections.map(
            (selection) => selection.research_request_id,
          ),
        },
      })
    } catch (error) {
      setHandoffError(error instanceof Error ? error.message : 'Could not start evidence review for this batch.')
      setStartingBatch(false)
    }
  }

  async function ensureCampaignRun(): Promise<{ campaignId: string; campaignRunId: string }> {
    if (campaignContext) return campaignContext
    if (!result || !objective) throw new Error('Run discovery before saving a prospect.')
    const campaign = await api<CampaignResponse>('/campaigns', {
      method: 'POST',
      body: {
        title: `${objective.target_geographies[0] ?? 'New'} ${objective.target_sectors[0] ?? 'business'} prospects`,
        criteria: criteriaPayload(),
        model_selection: { model_ids: selectedModels, confirmed_by_user: true },
      },
    })
    const campaignRun = await api<CampaignRunResponse>(`/campaigns/${campaign.id}/runs`, {
      method: 'POST',
      body: {
        provider_summary: providerSummary(result),
        discovered_candidate_count: result.candidates.length,
      },
    })
    const context = { campaignId: campaign.id, campaignRunId: campaignRun.id }
    setCampaignContext(context)
    return context
  }

  async function saveProspect(opportunity: PreparedDiscoveryOpportunity) {
    if (!result || !objective || savingProspectIndex !== null) return
    const candidateIndex = opportunity.queue_entry.candidate_index
    setSavingProspectIndex(candidateIndex)
    setHandoffError(null)
    try {
      const { campaignId, campaignRunId } = await ensureCampaignRun()
      await api(`/campaigns/${campaignId}/prospects`, {
        method: 'POST',
        body: {
          campaign_run_id: campaignRunId,
          candidate_input: opportunity.candidate_input,
          shortlist_entry: opportunity.shortlist_entry,
        },
      })
      setSavedProspectIndexes((current) => [...current, candidateIndex])
    } catch (error) {
      setHandoffError(error instanceof Error ? error.message : 'Could not save this prospect.')
    } finally {
      setSavingProspectIndex(null)
    }
  }

  const inputClass =
    'h-10 w-full rounded-control border border-line bg-card px-3 text-[13px] text-ink outline-none transition-colors placeholder:text-ink-faint focus:border-action focus:ring-1 focus:ring-action'

  return (
    <main className="workspace-page">
      <header>
        <div className="space-y-1">
          <h1 className="page-title">{step === 'form' ? 'New campaign' : step === 'confirm' ? 'Review campaign' : 'Research queue'}</h1>
          <p className="page-description">Describe the businesses you want to find and the service you offer.</p>
        </div>
      </header>

      {step === 'form' && (
        <section className="mt-8 grid gap-8 border-t border-line pt-7 lg:grid-cols-[minmax(0,1.65fr)_minmax(18rem,0.75fr)]">
          <form className="space-y-5" onSubmit={handleParse}>
            <div className="space-y-2">
              <label htmlFor="discovery-goal" className="block text-[13px] font-medium text-ink">What are you looking for?<span className="text-error"> *</span></label>
              <textarea id="discovery-goal" rows={4} placeholder="For example, find restaurants in Lahore that I can pitch website and reservation improvements to." value={form.goal} onChange={(event) => update('goal', event.target.value)} className={inputClass + ' h-auto min-h-28 resize-y py-3 leading-5'} />
            </div>
            <fieldset>
              <legend className="sr-only">Campaign objective</legend>
              <div className="flex flex-wrap gap-2">
                {OBJECTIVE_CHIPS.map((chip) => {
                  const active = activeChip === chip.value
                  return <button key={chip.value} type="button" aria-pressed={active} onClick={() => setActiveChip(active ? null : chip.value)} className={'rounded-control border px-3 py-1.5 text-[12px] font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-action ' + (active ? 'border-action bg-action text-white' : 'border-line bg-card text-ink-soft hover:border-action hover:text-ink')}>{chip.label}</button>
                })}
              </div>
            </fieldset>
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
              <div className="space-y-2"><label htmlFor="discovery-region" className="block text-[13px] font-medium text-ink">Where <span className="font-normal text-ink-faint">(optional)</span></label><input id="discovery-region" placeholder="For example, Lahore" value={form.region} onChange={(event) => update('region', event.target.value)} className={inputClass} /></div>
              <div className="space-y-2"><label htmlFor="discovery-size" className="block text-[13px] font-medium text-ink">Company size <span className="font-normal text-ink-faint">(optional)</span></label><input id="discovery-size" placeholder="For example, 10–50" value={form.company_size} onChange={(event) => update('company_size', event.target.value)} className={inputClass} /></div>
            </div>
            {searchError && <ErrorNotice message={searchError} />}
            <div className="flex justify-end border-t border-line pt-5"><Button type="submit" disabled={parsing} className="h-10 min-w-28 px-5">{parsing ? <><Loader2 size={16} className="animate-spin" />Reviewing</> : <>Continue</>}</Button></div>
          </form>

          <aside className="border-t border-line pt-6 lg:border-l lg:border-t-0 lg:pl-8 lg:pt-0">
            <h2 className="font-display text-[20px] font-bold tracking-[-0.025em] text-ink">Campaign brief</h2>
            <p className="mt-1 text-[13px] text-ink-soft">Built from your input before discovery begins.</p>
            <dl className="mt-6 space-y-5 text-[13px]">
              <div><dt className="text-ink-soft">Objective</dt><dd className="mt-1 font-medium text-ink">{activeChip ? GOAL_TYPE_LABELS[activeChip] : 'Not set'}</dd></div>
              <div><dt className="text-ink-soft">Target businesses</dt><dd className="mt-1 line-clamp-3 font-medium text-ink">{form.goal.trim() || 'Not set'}</dd></div>
              <div><dt className="text-ink-soft">Location</dt><dd className="mt-1 font-medium text-ink">{form.region.trim() || 'Any location'}</dd></div>
              <div><dt className="text-ink-soft">Company size</dt><dd className="mt-1 font-medium text-ink">{form.company_size.trim() || 'Any size'}</dd></div>
            </dl>
          </aside>
        </section>
      )}

      {step === 'confirm' && objective && (
        <section className="mb-6 max-w-4xl border-b border-line pb-6">
          <p className="text-label-sm font-semibold text-ink">What we will check</p>
          <p className="mt-3 text-body-lg font-medium text-on-surface">{GOAL_TYPE_LABELS[objective.goal_type] ?? 'Custom goal'}{objective.target_sectors.length > 0 && <span className="text-on-surface-variant"> · {joinItems(objective.target_sectors)}</span>}{objective.target_geographies.length > 0 && <span className="text-on-surface-variant"> · {joinItems(objective.target_geographies)}</span>}</p>
          {objective.offering && <p className="mt-1 text-body-md text-on-surface-variant">Offering: {objective.offering}</p>}
          <div className="mt-4 border-t border-line-soft pt-3"><p className="label-caps text-ink-faint">Research lenses</p>{selectedModels.length > 0 ? <div className="mt-2 flex flex-wrap gap-1.5">{selectedModels.map((modelId) => <span key={modelId} className="rounded-control bg-secondary-container px-2 py-1 text-label-sm text-on-surface">{MODEL_LABELS[modelId]}</span>)}</div> : <p className="mt-1 text-body-sm text-warn-ink">This offering does not yet map to an evidence-backed Opportunity Model.</p>}</div>
          <div className="mt-4 border-t border-line-soft pt-3"><p className="text-label-sm font-semibold text-on-surface">Searches</p><ul className="mt-1.5 space-y-1">{objective.search_queries.map((query) => <li key={query} className="text-body-sm text-on-surface-variant">{query}</li>)}</ul></div>
          {gate && !gate.supported && gate.message && <div className="mt-4 rounded-card border border-warn-bg bg-warn-bg p-4"><p className="text-label-sm font-semibold uppercase tracking-wide text-warn-ink">Not supported yet</p><p className="mt-1 text-body-sm text-on-surface">{gate.message}</p></div>}
          {searchError && <div className="mt-4"><ErrorNotice message={searchError} /></div>}
          <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center">{(!gate || gate.supported) && <Button type="button" onClick={handleConfirmedRun} disabled={searching || selectedModels.length === 0} className="h-10 px-space-lg">{searching ? <><Loader2 size={18} className="animate-spin" />Finding research candidates...</> : <>Find research candidates</>}</Button>}<button type="button" onClick={() => setStep('form')} className="inline-flex items-center justify-center text-label-md font-medium text-secondary transition-colors hover:text-on-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary">Edit</button></div>
        </section>
      )}

      {handoffError && <div className="mb-6"><ErrorNotice message={handoffError} /></div>}
      {searching && <div className="space-y-4" aria-live="polite"><div className="flex items-center gap-2 rounded-card border border-line bg-card p-4"><Loader2 size={18} className="shrink-0 animate-spin text-secondary" /><p className="text-body-md text-on-surface">Finding businesses and checking observable evidence...</p></div>{[1, 2, 3].map((index) => <div key={index} className="h-40 animate-pulse rounded-card border border-line bg-card" />)}</div>}

      {!searching && result && queue && queue.candidates.length === 0 && <section className="rounded-card border border-line bg-card p-8 text-center"><p className="font-display text-headline-md font-semibold text-on-surface">No research candidates with an observed signal yet</p><p className="mx-auto mt-2 max-w-xl text-body-md text-on-surface-variant">We found {result.candidates.length} candidates, but none has enough observable evidence for the selected service models. SalesLens will not make you research them blindly.</p>{queue.needs_verification_count > 0 && <p className="mt-2 text-label-md text-on-surface-variant">{queue.needs_verification_count} candidates need additional identity or evidence verification.</p>}</section>}

      {!searching && queue && queue.candidates.length > 0 && (
        <section className="mb-12 space-y-4">
          <div className="border-y border-line py-5"><div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between"><div><p className="text-label-sm font-semibold text-ink-soft">Suggested research batch</p><h2 className="mt-1 text-headline-lg font-semibold text-on-surface">Review {selectedQueueIndexes.length} evidence-backed prospect{selectedQueueIndexes.length === 1 ? '' : 's'}</h2><p className="mt-1 max-w-2xl text-body-sm text-on-surface-variant">Selected to represent different observable opportunities. This is not a ranking.</p></div><Button type="button" onClick={startRecommendedResearch} disabled={startingBatch || selectedQueueIndexes.length === 0} className="h-10 px-space-lg">{startingBatch ? <><Loader2 size={18} className="animate-spin" />Starting evidence review...</> : <>Start evidence review</>}</Button></div></div>
          <div className="flex items-center justify-between gap-3"><div><h2 className="font-display text-headline-md font-semibold text-on-surface">Research queue</h2><p className="text-body-sm text-on-surface-variant">{queue.candidates.length} candidates with a supported observed signal. Choose up to three.</p></div>{queue.needs_verification_count > 0 && <span className="rounded-full bg-surface-container-high px-3 py-1 text-label-sm text-on-surface-variant">{queue.needs_verification_count} hidden pending verification</span>}</div>
          <div className="space-y-4">{queue.candidates.map((opportunity) => <OpportunityCard key={`${opportunity.candidate_input.candidate.source_provider}:${opportunity.candidate_input.candidate.source_record_id}`} opportunity={opportunity} selected={selectedQueueIndexes.includes(opportunity.queue_entry.candidate_index)} saved={savedProspectIndexes.includes(opportunity.queue_entry.candidate_index)} saving={savingProspectIndex === opportunity.queue_entry.candidate_index} onToggle={toggleQueueCandidate} onSave={saveProspect} />)}</div>
        </section>
      )}
    </main>
  )
}

function OpportunityCard({ opportunity, selected, saved, saving, onToggle, onSave }: { opportunity: PreparedDiscoveryOpportunity; selected: boolean; saved: boolean; saving: boolean; onToggle: (candidateIndex: number) => void; onSave: (opportunity: PreparedDiscoveryOpportunity) => void }) {
  const candidate = opportunity.candidate_input.candidate
  return (
    <article className={'relative overflow-hidden rounded-card border bg-card p-space-lg transition-colors ' + (selected ? 'border-action' : 'border-line')}>
      <div className={'absolute bottom-0 left-0 top-0 w-1.5 ' + (selected ? 'bg-secondary' : 'bg-surface-container-high')} />
      <div className="flex flex-col gap-5 pl-2 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1 space-y-3"><div className="flex flex-wrap items-center gap-x-2 gap-y-1"><h3 className="text-headline-lg font-semibold text-on-surface">{candidate.company_name}</h3>{candidate.website && <a href={candidate.website} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-0.5 text-label-md text-secondary hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary"><span>{domainOf(candidate.website)}</span><ArrowUpRight size={14} /></a>}{candidate.industry && <span className="rounded bg-surface-container px-1.5 py-0.5 text-label-sm text-on-surface-variant">{candidate.industry}</span>}</div>{candidate.formatted_address && <p className="text-body-sm text-on-surface-variant">{candidate.formatted_address}</p>}<div className="space-y-2 bg-surface-container-low p-4"><p className="text-label-sm font-semibold text-ink">Why this appeared</p>{opportunity.queue_entry.reasons.map((reason) => <div key={`${reason.model_id}:${reason.signal_type}`} className="border-l-2 border-line pl-3"><p className="text-label-sm font-medium text-on-surface">{MODEL_LABELS[reason.model_id]}</p><p className="mt-0.5 text-body-sm leading-relaxed text-on-surface-variant">{reason.supporting_value}</p><p className="mt-1 text-label-sm text-outline">Source: {reason.source.source_url ? <a href={reason.source.source_url} target="_blank" rel="noopener noreferrer" className="text-secondary hover:underline">{domainOf(reason.source.source_url)}</a> : reason.source.provider}</p></div>)}</div></div>
        <div className="flex shrink-0 flex-col gap-2 lg:mt-1"><label className="flex cursor-pointer items-center gap-2 rounded-control border border-line bg-surface-container-lowest px-4 py-2 text-label-md font-medium text-on-surface transition-colors hover:border-secondary"><input type="checkbox" checked={selected} onChange={() => onToggle(opportunity.queue_entry.candidate_index)} className="size-4 accent-current" /><span>{selected ? 'In research batch' : 'Add to batch'}</span></label><button type="button" onClick={() => onSave(opportunity)} disabled={saved || saving} className="rounded-control border border-secondary px-4 py-2 text-label-md font-medium text-secondary transition-colors hover:bg-secondary-container disabled:cursor-not-allowed disabled:opacity-60">{saving ? 'Saving...' : saved ? 'Saved to prospects' : 'Save prospect'}</button></div>
      </div>
    </article>
  )
}
