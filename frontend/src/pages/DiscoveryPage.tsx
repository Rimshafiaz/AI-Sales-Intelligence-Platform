import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { ExternalLink, Loader2, Sparkles } from 'lucide-react'
import { api } from '../lib/api'
import type { DiscoveryResponse } from '../lib/types'
import { Button, Notice, TextField } from '../components/ui'

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

  async function handleSearch(event: FormEvent) {
    event.preventDefault()
    if (searching) return

    const payload = Object.fromEntries(
      Object.entries(criteria).map(([key, value]) => [key, value.trim() || undefined]),
    )
    if (Object.values(payload).every((value) => value === undefined)) {
      setSearchError('Add at least one criterion before searching.')
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

  const hasSearched = searching || searchError !== null || result !== null

  return (
    <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
      <p className="label-caps text-ink-faint">Company Discovery</p>
      <h1 className="mt-1 font-display text-3xl font-semibold text-ink">
        Discover companies
      </h1>
      <p className="mt-2 max-w-2xl text-sm text-ink-soft">
        Describe your ideal customer. Candidates are not saved until you start
        research on one.
      </p>

      <form
        onSubmit={handleSearch}
        className="mt-6 rounded-card border border-line-soft bg-card p-5"
      >
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <TextField
            label="Industry"
            placeholder="e.g. Fintech"
            value={criteria.industry}
            onChange={(event) => update('industry', event.target.value)}
          />
          <TextField
            label="Region"
            placeholder="e.g. San Francisco"
            value={criteria.region}
            onChange={(event) => update('region', event.target.value)}
          />
          <TextField
            label="Company size"
            placeholder="e.g. 50-200"
            value={criteria.company_size}
            onChange={(event) => update('company_size', event.target.value)}
          />
          <TextField
            label="Keywords"
            placeholder="e.g. payment infrastructure"
            value={criteria.keywords}
            onChange={(event) => update('keywords', event.target.value)}
          />
        </div>
        <div className="mt-4 flex items-center justify-between gap-4">
          <p className="text-xs text-ink-faint">At least one criterion is required.</p>
          <Button type="submit" disabled={searching}>
            {searching ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Searching...
              </>
            ) : (
              'Find companies'
            )}
          </Button>
        </div>
      </form>

      {searchError && (
        <div className="mt-4">
          <Notice kind="error">{searchError}</Notice>
        </div>
      )}
      {handoffError && (
        <div className="mt-4">
          <Notice kind="error">{handoffError}</Notice>
        </div>
      )}

      {hasSearched && (
        <section className="mt-8">
          <div className="flex items-center justify-between">
            <h2 className="label-caps text-ink-soft">Matched candidates</h2>
            {result && (
              <span className="font-ui text-xs text-ink-faint">
                {result.candidates.length} of 5
              </span>
            )}
          </div>

          {searching && (
            <div className="mt-3 space-y-3">
              {[1, 2, 3].map((index) => (
                <div
                  key={index}
                  className="h-24 animate-pulse rounded-card border border-line-soft bg-card"
                />
              ))}
            </div>
          )}

          {!searching && result && result.candidates.length === 0 && (
            <div className="mt-3 rounded-card border border-line-soft bg-card p-6 text-center">
              <p className="font-narrative text-sm text-ink-soft">
                No companies matched your criteria. Try broader terms.
              </p>
            </div>
          )}

          {!searching && result && result.candidates.length > 0 && (
            <div className="mt-3 divide-y divide-line-soft rounded-card border border-line-soft bg-card">
              {result.candidates.map((candidate) => (
                <article key={candidate.company_name} className="p-5">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <h3 className="font-narrative text-xl font-bold text-ink">
                      {candidate.company_name}
                    </h3>
                    {candidate.website && (
                      <a
                        href={candidate.website}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 font-ui text-xs text-action hover:underline"
                      >
                        {domainOf(candidate.website)}
                        <ExternalLink size={12} />
                      </a>
                    )}
                  </div>

                  {candidate.industry && (
                    <span className="mt-2 inline-block rounded-control border border-line bg-slate-wash px-1.5 py-0.5 font-ui text-[11px] text-ink-soft">
                      {candidate.industry}
                    </span>
                  )}

                  {candidate.short_description && (
                    <p className="mt-2 font-narrative text-sm leading-relaxed text-ink-soft">
                      {candidate.short_description}
                    </p>
                  )}

                  <div className="mt-3 border-l-2 border-action pl-3">
                    <p className="label-caps flex items-center gap-1 text-ink-faint">
                      <Sparkles size={11} />
                      AI match rationale
                    </p>
                    <p className="mt-1 font-narrative text-sm leading-relaxed text-ink">
                      {candidate.match_explanation}
                    </p>
                  </div>

                  {candidate.supporting_source_urls.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {candidate.supporting_source_urls.map((url) => (
                        <a
                          key={url}
                          href={url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 rounded-control border border-line bg-canvas px-1.5 py-0.5 font-mono text-[11px] text-ink-soft transition-colors hover:border-ink-faint hover:text-ink"
                        >
                          {domainOf(url)}
                          <ExternalLink size={11} />
                        </a>
                      ))}
                    </div>
                  )}

                  <div className="mt-4">
                    <Button
                      onClick={() => startResearch(candidate.company_name, candidate.website)}
                      disabled={busyCandidate !== null}
                    >
                      {busyCandidate === candidate.company_name ? (
                        <>
                          <Loader2 size={15} className="animate-spin" />
                          Starting research...
                        </>
                      ) : (
                        <>
                          Research this company
                          <ExternalLink size={15} />
                        </>
                      )}
                    </Button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      )}
    </main>
  )
}
