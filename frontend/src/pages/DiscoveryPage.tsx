import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowUpRight,
  CircleAlert,
  ExternalLink,
  FileSearch,
  Info,
  Link2,
  Loader2,
  Microscope,
  Pencil,
  Search,
  Sparkles,
} from 'lucide-react'
import { api } from '../lib/api'
import type {
  DiscoveryObjective,
  DiscoveryResponse,
  ParseDiscoveryResponse,
} from '../lib/types'
import { Button } from '../components/ui'

interface GoalForm {
  goal: string
  region: string
  company_size: string
}

const EMPTY_FORM: GoalForm = { goal: '', region: '', company_size: '' }

const OBJECTIVE_CHIPS: { value: string; label: string }[] = [
  { value: 'service_pitch', label: 'Pitch a service' },
  { value: 'client_prospecting', label: 'Find clients' },
  { value: 'investment', label: 'Investment' },
  { value: 'hiring', label: 'Hiring' },
]

const GOAL_TYPE_LABELS: Record<string, string> = {
  service_pitch: 'Pitch a service',
  client_prospecting: 'Find clients',
  investment: 'Investment',
  hiring: 'Hiring',
  market_research: 'Market research',
  other: 'Custom goal',
}

const SEARCH_STAGES = [
  'Interpreting your goal...',
  'Searching the web for evidence...',
  'Verifying candidates...',
  'Scoring fit against your goal...',
]

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
  const [busyCandidate, setBusyCandidate] = useState<string | null>(null)
  const [handoffError, setHandoffError] = useState<string | null>(null)
  const [searchStage, setSearchStage] = useState(0)

  useEffect(() => {
    if (!searching) {
      setSearchStage(0)
      return
    }
    const timer = window.setInterval(() => {
      setSearchStage((current) =>
        current < SEARCH_STAGES.length - 1 ? current + 1 : current,
      )
    }, 20000)
    return () => window.clearInterval(timer)
  }, [searching])

  function update(field: keyof GoalForm, value: string) {
    setForm((current) => ({ ...current, [field]: value }))
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
    try {
      const response = await api<ParseDiscoveryResponse>(
        '/company-discovery/parse',
        {
          method: 'POST',
          body: {
            goal,
            objective_hint: activeChip ?? undefined,
            region: form.region.trim() || undefined,
            company_size: form.company_size.trim() || undefined,
          },
        },
      )
      setObjective(response.objective)
      setGate({ supported: response.supported, message: response.message })
      setStep('confirm')
    } catch (error) {
      setSearchError(
        error instanceof Error ? error.message : 'Could not interpret the goal.',
      )
    } finally {
      setParsing(false)
    }
  }

  async function handleConfirmedRun() {
    if (searching || !objective) return

    setSearching(true)
    setSearchError(null)
    try {
      const response = await api<DiscoveryResponse>('/company-discovery', {
        method: 'POST',
        body: {
          goal: form.goal.trim(),
          objective,
          region: form.region.trim() || undefined,
          company_size: form.company_size.trim() || undefined,
        },
      })
      setResult(response)
    } catch (error) {
      setSearchError(error instanceof Error ? error.message : 'Discovery failed.')
    } finally {
      setSearching(false)
    }
  }

  async function startResearch(companyName: string, website: string | null) {
    if (busyCandidate) return
    setBusyCandidate(companyName)
    setHandoffError(null)
    try {
      const company = await api<{ id: string }>('/companies', {
        method: 'POST',
        body: { name: companyName, ...(website ? { website } : {}) },
      })
      const request = await api<{ id: string }>(
        `/companies/${company.id}/research-requests`,
        {
          method: 'POST',
          body: {
            goal: form.goal.trim() || undefined,
            objective: objective ?? undefined,
          },
        },
      )
      navigate(`/research/${request.id}`)
    } catch (error) {
      setHandoffError(error instanceof Error ? error.message : 'Could not start research.')
      setBusyCandidate(null)
    }
  }

  const inputClass =
    'h-9 w-full bg-surface-container-low text-on-surface px-space-sm text-body-md rounded ' +
    'outline-none transition-colors placeholder:text-outline-variant ' +
    'focus:bg-surface-container-lowest focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary'

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <div className="mb-8 flex flex-col justify-between gap-3 md:flex-row md:items-end">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-label-sm font-semibold uppercase tracking-widest text-secondary">
              Discovery
            </span>
            <span className="text-label-sm text-outline-variant">&bull;</span>
            <span className="text-label-sm text-on-surface-variant">
              Intent-driven shortlisting
            </span>
          </div>
          <h1 className="font-display text-headline-xl font-semibold tracking-tight text-on-surface">
            Find the companies worth pursuing
          </h1>
          <p className="max-w-2xl text-body-md text-on-surface-variant">
            Tell SalesLens what you are trying to sell and who you are looking
            for. It discovers potential companies, verifies them against your
            goal, and ranks the strongest opportunities. Candidates are not
            saved until research is initiated.
          </p>
        </div>
      </div>

      {step === 'form' && (
        <section className="mb-8 rounded-card bg-surface-container-lowest p-space-lg shadow-md">
          <form className="space-y-4" onSubmit={handleParse}>
            <div className="space-y-1.5">
              <label
                htmlFor="discovery-goal"
                className="block text-label-sm font-medium uppercase tracking-wide text-on-surface-variant"
              >
                What are you looking for?
              </label>
              <textarea
                id="discovery-goal"
                rows={3}
                placeholder="e.g. I'm a freelancer looking for beauty companies in Pakistan I can pitch website development to."
                value={form.goal}
                onChange={(event) => update('goal', event.target.value)}
                className={
                  inputClass +
                  ' h-auto min-h-20 resize-y py-2 leading-relaxed'
                }
              />
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {OBJECTIVE_CHIPS.map((chip) => {
                const active = activeChip === chip.value
                return (
                  <button
                    key={chip.value}
                    type="button"
                    aria-pressed={active}
                    onClick={() =>
                      setActiveChip(active ? null : chip.value)
                    }
                    className={
                      'rounded-full border px-3 py-1 text-label-md transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary ' +
                      (active
                        ? 'border-primary bg-primary text-on-primary'
                        : 'border-line bg-surface-container-lowest text-on-surface-variant hover:border-outline hover:text-on-surface')
                    }
                  >
                    {chip.label}
                  </button>
                )
              })}
              <span className="text-label-sm text-outline">
                optional hint &mdash; your text always wins
              </span>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label
                  htmlFor="discovery-region"
                  className="block text-label-sm font-medium uppercase tracking-wide text-on-surface-variant"
                >
                  Where (optional)
                </label>
                <input
                  id="discovery-region"
                  placeholder="e.g. Pakistan, UAE, US-East"
                  value={form.region}
                  onChange={(event) => update('region', event.target.value)}
                  className={inputClass}
                />
              </div>
              <div className="space-y-1.5">
                <label
                  htmlFor="discovery-size"
                  className="block text-label-sm font-medium uppercase tracking-wide text-on-surface-variant"
                >
                  Company size (optional)
                </label>
                <input
                  id="discovery-size"
                  placeholder="e.g. 50-250, startups"
                  value={form.company_size}
                  onChange={(event) => update('company_size', event.target.value)}
                  className={inputClass}
                />
              </div>
            </div>

            {searchError && (
              <div className="flex items-start gap-2 rounded-lg bg-error-container/40 p-3">
                <CircleAlert size={16} className="mt-0.5 shrink-0 text-error" />
                <p className="text-body-sm text-on-surface">{searchError}</p>
              </div>
            )}

            <div className="flex flex-col justify-between gap-2 pt-1 sm:flex-row sm:items-center">
              <div className="flex items-center gap-1 text-on-surface-variant">
                <Info size={16} className="text-secondary" />
                <span className="text-label-sm">
                  We show what we understood before running anything.
                </span>
              </div>
              <Button type="submit" disabled={parsing} className="h-10 px-space-lg">
                {parsing ? (
                  <>
                    <Loader2 size={18} className="animate-spin" />
                    Interpreting goal...
                  </>
                ) : (
                  <>
                    <FileSearch size={18} />
                    Continue
                  </>
                )}
              </Button>
            </div>
          </form>
        </section>
      )}

      {step === 'confirm' && objective && (
        <section className="mb-8 rounded-card border border-line-soft bg-surface-container-lowest p-space-lg shadow-md">
          <div className="flex items-center gap-2">
            <Sparkles size={18} className="text-secondary" />
            <span className="label-caps text-ink-faint">
              Here&apos;s what we&apos;ll look for
            </span>
          </div>

          <p className="mt-3 text-body-lg font-medium text-on-surface">
            {GOAL_TYPE_LABELS[objective.goal_type] ?? 'Custom goal'}
            {objective.target_sectors.length > 0 && (
              <span className="text-on-surface-variant">
                {' '}
                &middot; {joinItems(objective.target_sectors)}
              </span>
            )}
            {objective.target_geographies.length > 0 && (
              <span className="text-on-surface-variant">
                {' '}
                &middot; {joinItems(objective.target_geographies)}
              </span>
            )}
          </p>

          {objective.offering && (
            <p className="mt-1 text-body-md text-on-surface-variant">
              Offering: {objective.offering}
            </p>
          )}

          {(objective.triggers.length > 0 ||
            objective.signals_to_look_for.length > 0) && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {[...objective.triggers, ...objective.signals_to_look_for]
                .slice(0, 8)
                .map((signal) => (
                  <span
                    key={signal}
                    className="rounded-control bg-surface-container px-2 py-0.5 text-label-sm text-on-surface-variant"
                  >
                    {signal}
                  </span>
                ))}
            </div>
          )}

          <div className="mt-4 border-t border-line-soft pt-3">
            <p className="label-caps text-ink-faint">We&apos;ll search</p>
            <ul className="mt-1.5 space-y-1">
              {objective.search_queries.map((query) => (
                <li
                  key={query}
                  className="flex items-start gap-1.5 text-body-sm text-on-surface-variant"
                >
                  <Search size={13} className="mt-1 shrink-0 text-outline" />
                  <span>{query}</span>
                </li>
              ))}
            </ul>
          </div>

          {gate && !gate.supported && gate.message && (
            <div className="mt-4 rounded-card border border-warn-bg bg-warn-bg p-4">
              <p className="text-label-sm font-semibold uppercase tracking-wide text-warn-ink">
                Not supported yet
              </p>
              <p className="mt-1 text-body-sm text-on-surface">{gate.message}</p>
            </div>
          )}

          {searchError && (
            <div className="mt-4 flex items-start gap-2 rounded-lg bg-error-container/40 p-3">
              <CircleAlert size={16} className="mt-0.5 shrink-0 text-error" />
              <p className="text-body-sm text-on-surface">{searchError}</p>
            </div>
          )}

          <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center">
            {(!gate || gate.supported) && (
              <Button
                type="button"
                onClick={handleConfirmedRun}
                disabled={searching}
                className="h-10 px-space-lg"
              >
                {searching ? (
                  <>
                    <Loader2 size={18} className="animate-spin" />
                    Finding companies...
                  </>
                ) : (
                  <>
                    <FileSearch size={18} />
                    Looks right &mdash; find companies
                  </>
                )}
              </Button>
            )}
            <button
              type="button"
              onClick={() => setStep('form')}
              className="inline-flex items-center justify-center gap-1.5 text-label-md font-medium text-secondary transition-colors hover:text-on-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary"
            >
              <Pencil size={14} />
              Edit
            </button>
          </div>
        </section>
      )}

      {handoffError && (
        <div className="mb-6 flex items-start gap-2 rounded-lg bg-error-container/40 p-3">
          <CircleAlert size={18} className="mt-px shrink-0 text-error" />
          <p className="text-body-sm text-on-surface">{handoffError}</p>
        </div>
      )}

      {searching && (
        <div className="space-y-4">
          <div className="flex items-center gap-2 rounded-card border border-line-soft bg-surface-container-lowest p-4 shadow-sm">
            <Loader2 size={18} className="shrink-0 animate-spin text-secondary" />
            <p className="text-body-md text-on-surface">
              {SEARCH_STAGES[searchStage]}
            </p>
          </div>
          {[1, 2, 3].map((index) => (
            <div
              key={index}
              className="h-40 animate-pulse rounded-card bg-surface-container-lowest shadow-md"
            />
          ))}
        </div>
      )}

      {!searching && result && result.candidates.length === 0 && (
        <div className="rounded-card bg-surface-container-lowest p-8 text-center shadow-md">
          <p className="text-body-md text-on-surface-variant">
            No companies matched your goal. Try broader terms or edit the
            interpretation.
          </p>
          <button
            type="button"
            onClick={() => setStep('form')}
            className="mt-3 text-label-md font-medium text-secondary transition-colors hover:text-on-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary"
          >
            Edit goal
          </button>
        </div>
      )}

      {!searching && result && result.candidates.length > 0 && (
        <div className="mb-12 space-y-4">
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <span className="font-display text-headline-md font-semibold text-on-surface">
                Potential prospects
              </span>
              <span className="rounded-full bg-surface-container-high px-2 py-0.5 text-label-sm font-semibold text-on-surface">
                {result.candidates.length} found
              </span>
            </div>
            <p className="text-body-sm text-on-surface-variant">
              Ranked by how closely each company fits your goal.
            </p>
          </div>

          <div className="space-y-4">
            {result.candidates.map((candidate) => (
              <article
                key={candidate.company_name}
                className="group relative overflow-hidden rounded-card bg-surface-container-lowest p-space-lg shadow-md transition-all hover:shadow-xl"
              >
                <div className="absolute bottom-0 left-0 top-0 w-1.5 bg-secondary" />
                <div className="flex flex-col justify-between gap-6 pl-1.5 lg:flex-row lg:items-start">
                  <div className="flex-1 space-y-3">
                    <div>
                      <div className="mb-0.5 flex flex-wrap items-center gap-x-2 gap-y-1">
                        <h3 className="font-display text-headline-lg font-semibold text-on-surface">
                          {candidate.company_name}
                        </h3>
                        {candidate.website && (
                          <a
                            href={candidate.website}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-0.5 text-label-md text-secondary hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary"
                          >
                            <span>{domainOf(candidate.website)}</span>
                            <ArrowUpRight size={14} />
                          </a>
                        )}
                        {candidate.industry && (
                          <span className="rounded bg-surface-container px-1 py-0.5 text-label-sm text-on-surface-variant">
                            {candidate.industry}
                          </span>
                        )}
                      </div>
                      {candidate.short_description && (
                        <p className="text-body-md text-on-surface-variant">
                          {candidate.short_description}
                        </p>
                      )}
                    </div>

                    <div className="space-y-1.5 rounded-lg bg-surface-container-low p-4">
                      {candidate.fit_score !== null && candidate.fit_score !== undefined ? (
                        <>
                          <div className="flex items-baseline gap-2">
                            <span className="text-body-lg font-semibold text-on-surface">
                              Fit {candidate.fit_score}
                              <span className="text-body-sm font-medium text-outline">
                                /100
                              </span>
                            </span>
                            {candidate.fit_tier && (
                              <span
                                className={
                                  'text-label-sm font-medium uppercase tracking-wide ' +
                                  (candidate.fit_tier === 'high'
                                    ? 'text-secondary'
                                    : candidate.fit_tier === 'medium'
                                      ? 'text-on-surface-variant'
                                      : 'text-outline')
                                }
                              >
                                {candidate.fit_tier} fit
                              </span>
                            )}
                          </div>
                          <p className="text-body-md leading-relaxed text-on-surface">
                            {candidate.fit_reason || candidate.match_explanation}
                          </p>
                        </>
                      ) : (
                        <>
                          <div className="flex items-center gap-1 text-secondary">
                            <Sparkles size={18} />
                            <span className="text-label-sm font-semibold uppercase tracking-wider">
                              Why this is a good prospect
                            </span>
                          </div>
                          <p className="text-body-md leading-relaxed text-on-surface">
                            {candidate.match_explanation}
                          </p>
                        </>
                      )}
                    </div>

                    {candidate.supporting_source_urls.length > 0 && (
                      <div className="space-y-1.5">
                        <span className="block text-label-sm font-medium uppercase tracking-wide text-outline">
                          Evidence
                        </span>
                        <div className="flex flex-wrap items-center gap-2">
                          {candidate.supporting_source_urls.map((url) => (
                            <a
                              key={url}
                              href={url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 rounded-full bg-surface-container px-2 py-1 text-label-sm shadow-sm transition-colors hover:bg-surface-container-high focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary"
                            >
                              <Link2 size={14} className="text-secondary" />
                              <span className="font-medium text-on-surface">
                                {domainOf(url)}
                              </span>
                              <ExternalLink size={12} className="text-outline" />
                            </a>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="flex shrink-0 flex-col justify-end gap-1.5 pt-1 lg:w-64 lg:items-end lg:text-right">
                    <button
                      type="button"
                      onClick={() =>
                        startResearch(candidate.company_name, candidate.website)
                      }
                      disabled={busyCandidate !== null}
                      className="inline-flex w-full items-center justify-center gap-1 rounded-control bg-primary px-4 py-2 font-display text-headline-sm text-on-primary shadow-sm transition-all hover:bg-inverse-surface active:scale-[0.98] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary disabled:cursor-not-allowed disabled:opacity-60 lg:w-full"
                    >
                      {busyCandidate === candidate.company_name ? (
                        <>
                          <Loader2 size={18} className="animate-spin" />
                          Initiating research...
                        </>
                      ) : (
                        <>
                          <Microscope size={18} />
                          Research this company
                        </>
                      )}
                    </button>
                    <p className="text-center text-label-sm text-on-surface-variant lg:text-right">
                      Creates company record and begins evidence gathering.
                    </p>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </div>
      )}
    </main>
  )
}
