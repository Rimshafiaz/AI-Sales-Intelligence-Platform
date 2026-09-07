import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { ExternalLink, Loader2, Search } from 'lucide-react'
import { api } from '../lib/api'
import type { Company } from '../lib/types'
import { Button, Notice, TextField } from '../components/ui'

function isValidWebsite(value: string): boolean {
  try {
    const url = new URL(value)
    return url.protocol === 'http:' || url.protocol === 'https:'
  } catch {
    return false
  }
}

export default function ResearchPage() {
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [website, setWebsite] = useState('')
  const [offering, setOffering] = useState('')
  const [goal, setGoal] = useState('')
  const [region, setRegion] = useState('')
  const [companies, setCompanies] = useState<Company[] | null>(null)
  const [companiesError, setCompaniesError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [busyCompanyId, setBusyCompanyId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api<Company[]>('/companies')
      .then(setCompanies)
      .catch((e: unknown) =>
        setCompaniesError(e instanceof Error ? e.message : 'Could not load companies.'),
      )
  }, [])

  function scopeFields() {
    const cleanOffering = offering.trim()
    const cleanGoal = goal.trim()
    const cleanRegion = region.trim()
    return { cleanOffering, cleanGoal, cleanRegion }
  }

  async function startRequest(companyId: string) {
    const { cleanOffering, cleanGoal, cleanRegion } = scopeFields()
    const request = await api<{ id: string }>(
      `/companies/${companyId}/research-requests`,
      {
        method: 'POST',
        body: {
          goal: cleanGoal,
          offering: cleanOffering,
          ...(cleanRegion ? { region: cleanRegion } : {}),
        },
      },
    )
    navigate(`/research/${request.id}`)
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (submitting) return

    const cleanName = name.trim()
    const cleanWebsite = website.trim()
    const { cleanOffering, cleanGoal } = scopeFields()
    if (!cleanName) {
      setError('Company name is required.')
      return
    }
    if (!cleanOffering) {
      setError('Say what you are offering so the research can be scoped.')
      return
    }
    if (!cleanGoal) {
      setError('State the research goal, e.g. decide whether this business is worth pitching.')
      return
    }
    if (cleanWebsite && !isValidWebsite(cleanWebsite)) {
      setError('Website must be a valid http(s) URL.')
      return
    }

    setSubmitting(true)
    setError(null)
    try {
      const company = await api<Company>('/companies', {
        method: 'POST',
        body: { name: cleanName, ...(cleanWebsite ? { website: cleanWebsite } : {}) },
      })
      await startRequest(company.id)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not start research.')
      setSubmitting(false)
    }
  }

  async function handleQuickPick(company: Company) {
    if (busyCompanyId || submitting) return
    const { cleanOffering, cleanGoal } = scopeFields()
    if (!cleanOffering || !cleanGoal) {
      setError('Fill in what you offer and the research goal above first.')
      return
    }
    setBusyCompanyId(company.id)
    setError(null)
    try {
      await startRequest(company.id)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not start research.')
      setBusyCompanyId(null)
    }
  }

  return (
    <main className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <p className="label-caps text-ink-faint">Research a company</p>
      <h1 className="mt-1 font-display text-3xl font-semibold text-ink">
        Research a company
      </h1>
      <p className="mt-2 max-w-2xl text-sm text-ink-soft">
        Name a business, say what you are offering and what you want to decide.
        The system resolves its identity, collects evidence, and tells you
        whether it is worth pursuing for your offer.
      </p>

      <form
        onSubmit={handleSubmit}
        className="mt-6 rounded-card border border-line-soft bg-card p-5"
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            label="Company name"
            hint="Required"
            placeholder="e.g. Aleezay Hair Beauty Care Salon"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
          <TextField
            label="Website"
            hint="Optional"
            placeholder="https://example.com"
            value={website}
            onChange={(event) => setWebsite(event.target.value)}
          />
          <TextField
            label="What are you offering?"
            hint="Required"
            placeholder="e.g. Website design and online booking setup"
            value={offering}
            onChange={(event) => setOffering(event.target.value)}
          />
          <TextField
            label="Research goal"
            hint="Required"
            placeholder="e.g. Decide whether this business is worth pitching"
            value={goal}
            onChange={(event) => setGoal(event.target.value)}
          />
          <TextField
            label="City or region"
            hint="Optional, recommended"
            placeholder="e.g. Lahore"
            value={region}
            onChange={(event) => setRegion(event.target.value)}
          />
        </div>
        {error && (
          <div className="mt-4">
            <Notice kind="error">{error}</Notice>
          </div>
        )}
        <div className="mt-4 flex justify-end">
          <Button type="submit" disabled={submitting}>
            {submitting ? (
              <>
                <Loader2 size={15} className="animate-spin" />
                Starting...
              </>
            ) : (
              <>
                <Search size={15} />
                Start research
              </>
            )}
          </Button>
        </div>
      </form>

      <section className="mt-10">
        <div className="flex items-baseline justify-between">
          <h2 className="font-display text-lg font-semibold text-ink">
            Or choose from your companies
          </h2>
          <p className="text-xs text-ink-faint">
            Selecting one starts research immediately.
          </p>
        </div>

        {companiesError && (
          <div className="mt-3">
            <Notice kind="error">{companiesError}</Notice>
          </div>
        )}

        {companies === null && !companiesError && (
          <div className="mt-3 h-16 animate-pulse rounded-card border border-line-soft bg-card" />
        )}

        {companies && companies.length === 0 && (
          <div className="mt-3 rounded-card border border-line-soft bg-card p-6 text-center">
            <p className="font-narrative text-sm text-ink-soft">
              You have no companies yet. Create one with the form above.
            </p>
          </div>
        )}

        {companies && companies.length > 0 && (
          <div className="mt-3 divide-y divide-line-soft rounded-card border border-line-soft bg-card">
            {companies.map((company) => (
              <div
                key={company.id}
                className="flex flex-wrap items-center justify-between gap-3 px-5 py-3"
              >
                <div className="flex items-center gap-3">
                  <span className="flex h-8 w-8 items-center justify-center rounded-control border border-line bg-canvas font-display text-sm font-semibold text-ink">
                    {company.name.charAt(0).toUpperCase()}
                  </span>
                  <div>
                    <p className="font-ui text-sm font-semibold text-ink">{company.name}</p>
                    {company.website && (
                      <a
                        href={company.website}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 font-mono text-[11px] text-ink-soft hover:text-action"
                      >
                        {company.website.replace(/^https?:\/\//, '')}
                        <ExternalLink size={11} />
                      </a>
                    )}
                  </div>
                </div>
                <Button
                  variant="secondary"
                  disabled={busyCompanyId !== null || submitting}
                  onClick={() => handleQuickPick(company)}
                >
                  {busyCompanyId === company.id ? (
                    <>
                      <Loader2 size={14} className="animate-spin" />
                      Starting...
                    </>
                  ) : (
                    'Start research'
                  )}
                </Button>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  )
}
