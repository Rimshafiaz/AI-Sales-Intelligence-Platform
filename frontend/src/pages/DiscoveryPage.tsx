import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowUpRight,
  Building2,
  CircleAlert,
  ExternalLink,
  FileSearch,
  Globe,
  Info,
  Link2,
  Loader2,
  Microscope,
  RotateCcw,
  SlidersHorizontal,
  Sparkles,
  Tag,
  Users,
} from 'lucide-react'
import { api } from '../lib/api'
import type { DiscoveryResponse } from '../lib/types'
import { Button } from '../components/ui'

interface Criteria {
  industry: string
  region: string
  company_size: string
  keywords: string
}

const EMPTY_CRITERIA: Criteria = { industry: '', region: '', company_size: '', keywords: '' }

function domainOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

export default function DiscoveryPage() {
  const navigate = useNavigate()
  const [criteria, setCriteria] = useState<Criteria>(EMPTY_CRITERIA)
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [result, setResult] = useState<DiscoveryResponse | null>(null)
  const [busyCandidate, setBusyCandidate] = useState<string | null>(null)
  const [handoffError, setHandoffError] = useState<string | null>(null)

  function update(field: keyof Criteria, value: string) {
    setCriteria((current) => ({ ...current, [field]: value }))
  }

  function resetCriteria() {
    setCriteria(EMPTY_CRITERIA)
    setSearchError(null)
  }

  async function handleSearch(event: FormEvent) {
    event.preventDefault()
    if (searching) return

    const payload = Object.fromEntries(
      Object.entries(criteria).map(([key, value]) => [key, value.trim() || undefined]),
    )
    if (Object.values(payload).every((value) => value === undefined)) {
      setSearchError('At least one criterion required.')
      return
    }

    setSearching(true)
    setSearchError(null)
    setHandoffError(null)
    setResult(null)
    try {
      const response = await api<DiscoveryResponse>('/company-discovery', {
        method: 'POST',
        body: payload,
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
        { method: 'POST' },
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
    'focus:bg-surface-container-lowest pr-8'

  return (
    <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
      <div className="mb-8 flex flex-col justify-between gap-3 md:flex-row md:items-end">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-label-sm font-semibold uppercase tracking-widest text-secondary">
              Discovery
            </span>
            <span className="text-label-sm text-outline-variant">&bull;</span>
            <span className="text-label-sm text-on-surface-variant">
              Evidence-backed shortlisting
            </span>
          </div>
          <h1 className="font-display text-headline-xl font-semibold tracking-tight text-on-surface">
            Company Discovery
          </h1>
          <p className="max-w-2xl text-body-md text-on-surface-variant">
            Surface prospect accounts matching your territory criteria. Candidates
            are not saved until research is initiated.
          </p>
        </div>
      </div>

      <section className="mb-8 rounded-xl bg-surface-container-lowest p-space-lg shadow-md">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <SlidersIcon />
            <h2 className="font-display text-headline-sm font-semibold text-on-surface">
              Ideal Customer Profile (ICP) Parameters
            </h2>
          </div>
          <button
            type="button"
            onClick={resetCriteria}
            className="flex items-center gap-0.5 text-label-md text-on-surface-variant transition-colors hover:text-on-surface"
          >
            <RotateCcw size={16} />
            Reset query
          </button>
        </div>

        <form className="space-y-4" onSubmit={handleSearch}>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
            <div className="space-y-1.5">
              <label
                htmlFor="filter-industry"
                className="block text-label-sm font-medium uppercase tracking-wide text-on-surface-variant"
              >
                Industry &amp; Sector
              </label>
              <div className="relative">
                <input
                  id="filter-industry"
                  placeholder="e.g. Developer Tools, Healthcare IT"
                  value={criteria.industry}
                  onChange={(event) => update('industry', event.target.value)}
                  className={inputClass}
                />
                <Building2
                  size={18}
                  className="pointer-events-none absolute right-2.5 top-2.5 text-outline"
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <label
                htmlFor="filter-region"
                className="block text-label-sm font-medium uppercase tracking-wide text-on-surface-variant"
              >
                Geographic Footprint
              </label>
              <div className="relative">
                <input
                  id="filter-region"
                  placeholder="e.g. EMEA, US-East, DACH"
                  value={criteria.region}
                  onChange={(event) => update('region', event.target.value)}
                  className={inputClass}
                />
                <Globe
                  size={18}
                  className="pointer-events-none absolute right-2.5 top-2.5 text-outline"
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <label
                htmlFor="filter-size"
                className="block text-label-sm font-medium uppercase tracking-wide text-on-surface-variant"
              >
                Headcount Band
              </label>
              <div className="relative">
                <input
                  id="filter-size"
                  placeholder="e.g. 50-250, 250-1000"
                  value={criteria.company_size}
                  onChange={(event) => update('company_size', event.target.value)}
                  className={inputClass}
                />
                <Users
                  size={18}
                  className="pointer-events-none absolute right-2.5 top-2.5 text-outline"
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <label
                htmlFor="filter-keywords"
                className="block text-label-sm font-medium uppercase tracking-wide text-on-surface-variant"
              >
                Intent &amp; Infrastructure Triggers
              </label>
              <div className="relative">
                <input
                  id="filter-keywords"
                  placeholder="e.g. SOC2, Salesforce CRM, Series B"
                  value={criteria.keywords}
                  onChange={(event) => update('keywords', event.target.value)}
                  className={inputClass}
                />
                <Tag
                  size={18}
                  className="pointer-events-none absolute right-2.5 top-2.5 text-outline"
                />
              </div>
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
                At least one criterion required. Searches run against live web evidence.
              </span>
            </div>
            <Button type="submit" disabled={searching} className="h-10 px-space-lg">
              {searching ? (
                <>
                  <Loader2 size={18} className="animate-spin" />
                  Evaluating signals...
                </>
              ) : (
                <>
                  <FileSearch size={18} />
                  Find companies
                </>
              )}
            </Button>
          </div>
        </form>
      </section>

      <div className="mb-6 flex items-center justify-between gap-4 rounded-lg bg-surface-container-low p-4 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-canvas text-on-surface">
            <FileSearch size={18} />
          </div>
          <div>
            <p className="font-display text-headline-sm font-semibold text-on-surface">
              Discovery scratchpad
            </p>
            <p className="text-body-sm text-on-surface-variant">
              Candidates are not saved to your workspace until you select{' '}
              <strong className="font-semibold text-on-surface">
                &quot;Research this company&quot;
              </strong>
              .
            </p>
          </div>
        </div>
      </div>

      {handoffError && (
        <div className="mb-6 flex items-start gap-2 rounded-lg bg-error-container/40 p-3">
          <CircleAlert size={18} className="mt-px shrink-0 text-error" />
          <p className="text-body-sm text-on-surface">{handoffError}</p>
        </div>
      )}

      {searching && (
        <div className="space-y-4">
          {[1, 2, 3].map((index) => (
            <div
              key={index}
              className="h-40 animate-pulse rounded-xl bg-surface-container-lowest shadow-md"
            />
          ))}
        </div>
      )}

      {!searching && result && result.candidates.length === 0 && (
        <div className="rounded-xl bg-surface-container-lowest p-8 text-center shadow-md">
          <p className="font-narrative text-sm text-on-surface-variant">
            No companies matched your criteria. Try broader terms.
          </p>
        </div>
      )}

      {!searching && result && result.candidates.length > 0 && (
        <div className="mb-12 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="font-display text-headline-md font-semibold text-on-surface">
                Matched candidates
              </span>
              <span className="rounded-full bg-surface-container-high px-2 py-0.5 text-label-sm font-semibold text-on-surface">
                {result.candidates.length} found
              </span>
            </div>
          </div>

          <div className="space-y-4">
            {result.candidates.map((candidate) => (
              <article
                key={candidate.company_name}
                className="group relative overflow-hidden rounded-xl bg-surface-container-lowest p-space-lg shadow-md transition-all hover:shadow-xl"
              >
                <div className="absolute bottom-0 left-0 top-0 w-1.5 bg-secondary" />
                <div className="flex flex-col justify-between gap-6 pl-1.5 lg:flex-row lg:items-start">
                  <div className="flex-1 space-y-3">
                    <div>
                      <div className="mb-0.5 flex flex-wrap items-center gap-x-2 gap-y-1">
                        <h3 className="font-narrative text-headline-lg font-semibold text-on-surface">
                          {candidate.company_name}
                        </h3>
                        {candidate.website && (
                          <a
                            href={candidate.website}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-0.5 text-label-md text-secondary hover:underline"
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
                      <div className="flex items-center gap-1 text-secondary">
                        <Sparkles size={18} />
                        <span className="text-label-sm font-semibold uppercase tracking-wider">
                          AI Signal Rationale
                        </span>
                      </div>
                      <p className="font-narrative text-body-md leading-relaxed text-on-surface">
                        {candidate.match_explanation}
                      </p>
                    </div>

                    {candidate.supporting_source_urls.length > 0 && (
                      <div className="space-y-1.5">
                        <span className="block text-label-sm font-medium uppercase tracking-wide text-outline">
                          Verified Ground Truth Citations
                        </span>
                        <div className="flex flex-wrap items-center gap-2">
                          {candidate.supporting_source_urls.map((url) => (
                            <a
                              key={url}
                              href={url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 rounded-full bg-surface-container px-2 py-1 text-label-sm shadow-sm transition-colors hover:bg-surface-container-high"
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
                      className="inline-flex w-full items-center justify-center gap-1 rounded bg-primary px-4 py-2 font-display text-headline-sm text-on-primary shadow-sm transition-all hover:bg-primary-container active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60 lg:w-full"
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

function SlidersIcon() {
  return <SlidersHorizontal size={20} className="text-on-surface" />
}
