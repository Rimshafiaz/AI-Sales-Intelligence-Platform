import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowUpRight,
  CheckCircle2,
  CircleAlert,
  FileSearch,
  Info,
  Loader2,
  Pencil,
  Search,
  Sparkles,
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
  'web_conversion.no_verified_web_presence': 'No verified web presence',
  'web_conversion.mobile_performance': 'Mobile performance',
  'web_conversion.booking_contact_path': 'Booking or inquiry path',
  'web_conversion.restaurant_reservation_path': 'Restaurant reservation path',
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
  const hasSocialIntent = /social|instagram|tiktok|content|reels|short.form|short form/.test(text)

  if (hasWebIntent) {
    modelIds.push(
      'web_conversion.no_verified_web_presence',
      'web_conversion.mobile_performance',
    )
    if (/booking|appointment|reservation|inquiry/.test(text)) {
      modelIds.push(
        /restaurant|cafe/.test(industry)
          ? 'web_conversion.restaurant_reservation_path'
          : 'web_conversion.booking_contact_path',
      )
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
      const criteria = criteriaPayload()
      const campaign = await api<CampaignResponse>('/campaigns', {
        method: 'POST',
        body: {
          title: `${objective.target_geographies[0] ?? 'New'} ${objective.target_sectors[0] ?? 'business'} prospects`,
          criteria,
          model_selection: {
            model_ids: selectedModels,
            confirmed_by_user: true,
          },
        },
      })
      const campaignRun = await api<CampaignRunResponse>(`/campaigns/${campaign.id}/runs`, {
        method: 'POST',
        body: {
          provider_summary: providerSummary(result),
          discovered_candidate_count: result.candidates.length,
        },
      })
      const batch = await api<CampaignRecommendedBatchResponse>(
        `/campaigns/runs/${campaignRun.id}/recommended-batch`,
        { method: 'POST', body: { opportunities } },
      )
      await Promise.all(
        batch.selections.map((selection) =>
          api(`/research-requests/${selection.research_request_id}/evidence-gate`, {
            method: 'POST',
          }),
        ),
      )
      navigate(`/research/${batch.selections[0].research_request_id}`)
    } catch (error) {
      setHandoffError(error instanceof Error ? error.message : 'Could not start evidence review for this batch.')
      setStartingBatch(false)
    }
  }

  const inputClass =
    'h-9 w-full rounded bg-surface-container-low px-space-sm text-body-md text-on-surface outline-none transition-colors placeholder:text-outline-variant focus:bg-surface-container-lowest focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary'

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <div className="mb-8 flex flex-col justify-between gap-3 md:flex-row md:items-end">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-label-sm font-semibold uppercase tracking-widest text-secondary">Discovery</span>
            <span className="text-label-sm text-outline-variant">•</span>
            <span className="text-label-sm text-on-surface-variant">Evidence-backed opportunity queue</span>
          </div>
          <h1 className="font-display text-headline-xl font-semibold tracking-tight text-on-surface">Find the companies worth pursuing</h1>
          <p className="max-w-2xl text-body-md text-on-surface-variant">SalesLens finds local, web, and social candidates, then only shows businesses with an observable signal relevant to the service you sell.</p>
        </div>
      </div>

      {step === 'form' && (
        <section className="mb-8 rounded-card bg-surface-container-lowest p-space-lg shadow-md">
          <form className="space-y-4" onSubmit={handleParse}>
            <div className="space-y-1.5">
              <label htmlFor="discovery-goal" className="block text-label-sm font-medium uppercase tracking-wide text-on-surface-variant">What are you looking for?</label>
              <textarea id="discovery-goal" rows={3} placeholder="e.g. I want salons in Lahore to pitch website and booking improvements to." value={form.goal} onChange={(event) => update('goal', event.target.value)} className={inputClass + ' h-auto min-h-20 resize-y py-2 leading-relaxed'} />
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {OBJECTIVE_CHIPS.map((chip) => {
                const active = activeChip === chip.value
                return <button key={chip.value} type="button" aria-pressed={active} onClick={() => setActiveChip(active ? null : chip.value)} className={'rounded-full border px-3 py-1 text-label-md transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary ' + (active ? 'border-primary bg-primary text-on-primary' : 'border-line bg-surface-container-lowest text-on-surface-variant hover:border-outline hover:text-on-surface')}>{chip.label}</button>
              })}
              <span className="text-label-sm text-outline">optional hint — your text always wins</span>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5"><label htmlFor="discovery-region" className="block text-label-sm font-medium uppercase tracking-wide text-on-surface-variant">Where (optional)</label><input id="discovery-region" placeholder="e.g. Lahore" value={form.region} onChange={(event) => update('region', event.target.value)} className={inputClass} /></div>
              <div className="space-y-1.5"><label htmlFor="discovery-size" className="block text-label-sm font-medium uppercase tracking-wide text-on-surface-variant">Company size (optional)</label><input id="discovery-size" placeholder="e.g. 50-250, startups" value={form.company_size} onChange={(event) => update('company_size', event.target.value)} className={inputClass} /></div>
            </div>
            {searchError && <ErrorNotice message={searchError} />}
            <div className="flex flex-col justify-between gap-2 pt-1 sm:flex-row sm:items-center"><div className="flex items-center gap-1 text-on-surface-variant"><Info size={16} className="text-secondary" /><span className="text-label-sm">We show what we understood before running anything.</span></div><Button type="submit" disabled={parsing} className="h-10 px-space-lg">{parsing ? <><Loader2 size={18} className="animate-spin" />Interpreting goal...</> : <><FileSearch size={18} />Continue</>}</Button></div>
          </form>
        </section>
      )}

      {step === 'confirm' && objective && (
        <section className="mb-8 rounded-card border border-line-soft bg-surface-container-lowest p-space-lg shadow-md">
          <div className="flex items-center gap-2"><Sparkles size={18} className="text-secondary" /><span className="label-caps text-ink-faint">Here&apos;s what we&apos;ll look for</span></div>
          <p className="mt-3 text-body-lg font-medium text-on-surface">{GOAL_TYPE_LABELS[objective.goal_type] ?? 'Custom goal'}{objective.target_sectors.length > 0 && <span className="text-on-surface-variant"> · {joinItems(objective.target_sectors)}</span>}{objective.target_geographies.length > 0 && <span className="text-on-surface-variant"> · {joinItems(objective.target_geographies)}</span>}</p>
          {objective.offering && <p className="mt-1 text-body-md text-on-surface-variant">Offering: {objective.offering}</p>}
          <div className="mt-4 border-t border-line-soft pt-3"><p className="label-caps text-ink-faint">Opportunity lenses</p>{selectedModels.length > 0 ? <div className="mt-2 flex flex-wrap gap-1.5">{selectedModels.map((modelId) => <span key={modelId} className="rounded-control bg-secondary-container px-2 py-1 text-label-sm text-on-surface">{MODEL_LABELS[modelId]}</span>)}</div> : <p className="mt-1 text-body-sm text-warn-ink">This offering does not yet map to an evidence-backed Opportunity Model.</p>}</div>
          <div className="mt-4 border-t border-line-soft pt-3"><p className="label-caps text-ink-faint">We&apos;ll search</p><ul className="mt-1.5 space-y-1">{objective.search_queries.map((query) => <li key={query} className="flex items-start gap-1.5 text-body-sm text-on-surface-variant"><Search size={13} className="mt-1 shrink-0 text-outline" /><span>{query}</span></li>)}</ul></div>
          {gate && !gate.supported && gate.message && <div className="mt-4 rounded-card border border-warn-bg bg-warn-bg p-4"><p className="text-label-sm font-semibold uppercase tracking-wide text-warn-ink">Not supported yet</p><p className="mt-1 text-body-sm text-on-surface">{gate.message}</p></div>}
          {searchError && <div className="mt-4"><ErrorNotice message={searchError} /></div>}
          <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center">{(!gate || gate.supported) && <Button type="button" onClick={handleConfirmedRun} disabled={searching || selectedModels.length === 0} className="h-10 px-space-lg">{searching ? <><Loader2 size={18} className="animate-spin" />Finding opportunities...</> : <><FileSearch size={18} />Looks right — find opportunities</>}</Button>}<button type="button" onClick={() => setStep('form')} className="inline-flex items-center justify-center gap-1.5 text-label-md font-medium text-secondary transition-colors hover:text-on-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary"><Pencil size={14} />Edit</button></div>
        </section>
      )}

      {handoffError && <div className="mb-6"><ErrorNotice message={handoffError} /></div>}
      {searching && <div className="space-y-4" aria-live="polite"><div className="flex items-center gap-2 rounded-card border border-line-soft bg-surface-container-lowest p-4 shadow-sm"><Loader2 size={18} className="shrink-0 animate-spin text-secondary" /><p className="text-body-md text-on-surface">Finding businesses and checking observable evidence...</p></div>{[1, 2, 3].map((index) => <div key={index} className="h-40 animate-pulse rounded-card bg-surface-container-lowest shadow-md" />)}</div>}

      {!searching && result && queue && queue.candidates.length === 0 && <section className="rounded-card bg-surface-container-lowest p-8 text-center shadow-md"><p className="font-display text-headline-md font-semibold text-on-surface">No evidence-backed opportunities yet</p><p className="mx-auto mt-2 max-w-xl text-body-md text-on-surface-variant">We found {result.candidates.length} candidates, but none has enough observable evidence for the selected service models. SalesLens will not make you research them blindly.</p>{queue.needs_verification_count > 0 && <p className="mt-2 text-label-md text-on-surface-variant">{queue.needs_verification_count} candidates need additional identity or evidence verification.</p>}</section>}

      {!searching && queue && queue.candidates.length > 0 && (
        <section className="mb-12 space-y-4">
          <div className="rounded-card border border-secondary/30 bg-secondary-container/35 p-space-lg shadow-sm"><div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between"><div><p className="label-caps text-secondary">Recommended first batch</p><h2 className="mt-1 font-display text-headline-lg font-semibold text-on-surface">Review {selectedQueueIndexes.length} evidence-backed prospect{selectedQueueIndexes.length === 1 ? '' : 's'}</h2><p className="mt-1 max-w-2xl text-body-sm text-on-surface-variant">These are selected to cover observable patterns, not ranked as the “best” businesses. Every card shows the factual reason it appeared.</p></div><Button type="button" onClick={startRecommendedResearch} disabled={startingBatch || selectedQueueIndexes.length === 0} className="h-10 px-space-lg">{startingBatch ? <><Loader2 size={18} className="animate-spin" />Starting evidence review...</> : <><FileSearch size={18} />Start evidence review</>}</Button></div></div>
          <div className="flex items-center justify-between gap-3"><div><h2 className="font-display text-headline-md font-semibold text-on-surface">Opportunity queue</h2><p className="text-body-sm text-on-surface-variant">{queue.candidates.length} candidates with a supported observed signal. Choose up to three.</p></div>{queue.needs_verification_count > 0 && <span className="rounded-full bg-surface-container-high px-3 py-1 text-label-sm text-on-surface-variant">{queue.needs_verification_count} hidden pending verification</span>}</div>
          <div className="space-y-4">{queue.candidates.map((opportunity) => <OpportunityCard key={`${opportunity.candidate_input.candidate.source_provider}:${opportunity.candidate_input.candidate.source_record_id}`} opportunity={opportunity} selected={selectedQueueIndexes.includes(opportunity.queue_entry.candidate_index)} onToggle={toggleQueueCandidate} />)}</div>
        </section>
      )}
    </main>
  )
}

function OpportunityCard({ opportunity, selected, onToggle }: { opportunity: PreparedDiscoveryOpportunity; selected: boolean; onToggle: (candidateIndex: number) => void }) {
  const candidate = opportunity.candidate_input.candidate
  return (
    <article className={'relative overflow-hidden rounded-card border bg-surface-container-lowest p-space-lg shadow-md transition-shadow hover:shadow-xl ' + (selected ? 'border-secondary' : 'border-transparent')}>
      <div className={'absolute bottom-0 left-0 top-0 w-1.5 ' + (selected ? 'bg-secondary' : 'bg-surface-container-high')} />
      <div className="flex flex-col gap-5 pl-2 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1 space-y-3"><div className="flex flex-wrap items-center gap-x-2 gap-y-1"><h3 className="font-display text-headline-lg font-semibold text-on-surface">{candidate.company_name}</h3>{candidate.website && <a href={candidate.website} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-0.5 text-label-md text-secondary hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary"><span>{domainOf(candidate.website)}</span><ArrowUpRight size={14} /></a>}{candidate.industry && <span className="rounded bg-surface-container px-1.5 py-0.5 text-label-sm text-on-surface-variant">{candidate.industry}</span>}</div>{candidate.formatted_address && <p className="text-body-sm text-on-surface-variant">{candidate.formatted_address}</p>}<div className="space-y-2 rounded-lg bg-surface-container-low p-4"><div className="flex items-center gap-1.5 text-secondary"><CheckCircle2 size={17} /><span className="text-label-sm font-semibold uppercase tracking-wider">Why SalesLens showed this</span></div>{opportunity.queue_entry.reasons.map((reason) => <div key={`${reason.model_id}:${reason.signal_type}`} className="border-l-2 border-secondary/60 pl-3"><p className="text-label-sm font-medium text-on-surface">{MODEL_LABELS[reason.model_id]}</p><p className="mt-0.5 text-body-sm leading-relaxed text-on-surface-variant">{reason.supporting_value}</p><p className="mt-1 text-label-sm text-outline">Source: {reason.source.source_url ? <a href={reason.source.source_url} target="_blank" rel="noopener noreferrer" className="text-secondary hover:underline">{domainOf(reason.source.source_url)}</a> : reason.source.provider}</p></div>)}</div></div>
        <label className="flex shrink-0 cursor-pointer items-center gap-2 rounded-control border border-line bg-surface-container-lowest px-4 py-2 text-label-md font-medium text-on-surface transition-colors hover:border-secondary lg:mt-1"><input type="checkbox" checked={selected} onChange={() => onToggle(opportunity.queue_entry.candidate_index)} className="size-4 accent-current" /><span>{selected ? 'In research batch' : 'Add to batch'}</span></label>
      </div>
    </article>
  )
}
