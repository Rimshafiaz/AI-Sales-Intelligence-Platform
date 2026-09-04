import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Check, ExternalLink, Loader2, XCircle } from 'lucide-react'
import { api } from '../lib/api'
import type { Company, ReportListResponse, ResearchRequest, ResearchSource } from '../lib/types'
import { Button, Notice } from '../components/ui'

type StageState = 'done' | 'active' | 'pending'

function formatTime(iso: string | null): string {
  return iso ? new Date(iso).toLocaleTimeString() : ''
}

function domainOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

function StageRow({
  label,
  state,
  timestamp,
}: {
  label: string
  state: StageState
  timestamp: string | null
}) {
  return (
    <li className="flex items-center gap-3 border-b border-line-soft py-3 last:border-b-0">
      {state === 'done' && (
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-ink">
          <Check size={12} className="text-canvas" />
        </span>
      )}
      {state === 'active' && <Loader2 size={18} className="animate-spin text-action" />}
      {state === 'pending' && <span className="h-5 w-5 rounded-full border border-line" />}
      <span
        className={
          'flex-1 font-ui text-sm ' + (state === 'pending' ? 'text-ink-faint' : 'text-ink')
        }
      >
        {label}
      </span>
      {timestamp && <span className="font-mono text-xs text-ink-faint">{formatTime(timestamp)}</span>}
    </li>
  )
}

export default function ResearchProgressPage() {
  const { requestId } = useParams<{ requestId: string }>()
  const navigate = useNavigate()

  const [request, setRequest] = useState<ResearchRequest | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [company, setCompany] = useState<Company | null>(null)
  const [sources, setSources] = useState<ResearchSource[] | null>(null)
  const [generatePhase, setGeneratePhase] = useState<'idle' | 'starting' | 'polling'>('idle')
  const [generateError, setGenerateError] = useState<string | null>(null)
  const loadRequest = useCallback(async () => {
    if (!requestId) return null
    try {
      const data = await api<ResearchRequest>(`/research-requests/${requestId}`)
      setRequest(data)
      setLoadError(null)
      return data
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : 'Could not load the research request.')
      return null
    }
  }, [requestId])

  useEffect(() => {
    void loadRequest()
  }, [loadRequest])

  useEffect(() => {
    if (!request || company) return
    api<Company>(`/companies/${request.company_id}`)
      .then(setCompany)
      .catch(() => setCompany(null))
  }, [request, company])

  useEffect(() => {
    if (request?.status !== 'completed' || sources) return
    api<ResearchSource[]>(`/research-requests/${request.id}/sources`)
      .then(setSources)
      .catch(() => setSources([]))
  }, [request, sources])

  useEffect(() => {
    if (loadError) return
    if (request && (request.status === 'completed' || request.status === 'failed')) return
    const interval = setInterval(() => void loadRequest(), 3000)
    return () => clearInterval(interval)
  }, [request, loadError, loadRequest])

  async function handleGenerate() {
    if (!request || generatePhase !== 'idle') return
    setGenerateError(null)
    setGeneratePhase('starting')
    try {
      await api<{ status: string }>(`/research-requests/${request.id}/reports`, {
        method: 'POST',
      })
      setGeneratePhase('polling')
    } catch (e) {
      setGenerateError(e instanceof Error ? e.message : 'Could not start report generation.')
      setGeneratePhase('idle')
    }
  }

  useEffect(() => {
    if (generatePhase !== 'polling' || !request) return
    const requestIdLocal = request.id
    let attempts = 0
    const interval = setInterval(async () => {
      attempts += 1
      try {
        const page = await api<ReportListResponse>('/reports', {
          params: { page: 1, page_size: 5 },
        })
        const found = page.items.find(
          (item) => item.research_request_id === requestIdLocal,
        )
        if (found) {
          setGeneratePhase('idle')
          navigate(`/reports/${found.id}`)
          return
        }
      } catch {
        // transient poll failure; keep polling
      }
      if (attempts >= 200) {
        setGeneratePhase('idle')
        setGenerateError(
          'Generation did not finish in time. Check History; the report may appear there.',
        )
      }
    }, 3000)
    return () => clearInterval(interval)
  }, [generatePhase, request, navigate])

  async function handleRetry() {
    if (!request) return
    try {
      const fresh = await api<{ id: string }>(
        `/companies/${request.company_id}/research-requests`,
        { method: 'POST' },
      )
      setRequest(null)
      setSources(null)
      navigate(`/research/${fresh.id}`)
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : 'Could not start a new request.')
    }
  }

  if (loadError) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
        <Notice kind="error">{loadError}</Notice>
        <p className="mt-4 text-sm">
          <Link to="/dashboard" className="text-action hover:underline">
            Back to dashboard
          </Link>
        </p>
      </main>
    )
  }

  if (!request) {
    return (
      <main className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
        <div className="h-32 animate-pulse rounded-card border border-line-soft bg-card" />
      </main>
    )
  }

  const companyTitle = company?.name ?? 'Research request'
  const failed = request.status === 'failed'
  const completed = request.status === 'completed'
  const running = request.status === 'running'

  const stages: { label: string; state: StageState; timestamp: string | null }[] = [
    { label: 'Request accepted', state: 'done', timestamp: request.created_at },
    {
      label: 'Resolving company website',
      state: request.started_at ? 'done' : 'active',
      timestamp: request.started_at,
    },
    {
      label: 'Collecting web evidence',
      state: completed || failed ? 'done' : running ? 'active' : 'pending',
      timestamp: null,
    },
    {
      label: 'Evidence ready',
      state: completed ? 'done' : 'pending',
      timestamp: request.finished_at,
    },
  ]

  return (
    <main className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <p className="label-caps text-ink-faint">
        Research request <span className="font-mono">{request.id.slice(0, 8)}</span>
      </p>
      <h1 className="mt-1 font-display text-3xl font-semibold text-ink">{companyTitle}</h1>

      <section className="mt-6 rounded-card border border-line-soft bg-card p-5">
        <h2 className="label-caps text-ink-soft">Investigation progress</h2>
        <ul className="mt-2">
          {stages.map((stage) => (
            <StageRow key={stage.label} {...stage} />
          ))}
          {failed && (
            <li className="flex items-center gap-3 py-3">
              <XCircle size={20} className="text-bad-ink" />
              <span className="flex-1 font-ui text-sm text-bad-ink">Research failed</span>
              <span className="font-mono text-xs text-ink-faint">
                {formatTime(request.finished_at)}
              </span>
            </li>
          )}
        </ul>
        {failed && request.error_message && (
          <div className="mt-2">
            <Notice kind="error">{request.error_message}</Notice>
          </div>
        )}
        {failed && (
          <div className="mt-3">
            <Button onClick={handleRetry}>Try again</Button>
          </div>
        )}
      </section>

      {completed && (
        <>
          <section className="mt-6 rounded-card border border-line-soft bg-card p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="label-caps text-ink-soft">
                Evidence collected {sources ? `(${sources.length} sources)` : ''}
              </h2>
              {generatePhase === 'polling' ? (
                <div className="flex items-center gap-2 rounded-control bg-slate-wash p-2.5">
                  <Loader2 size={15} className="animate-spin text-action" />
                  <p className="font-ui text-sm text-ink">
                    Report generation is running. This takes 1 to 5 minutes; you
                    will be moved to the report automatically.
                  </p>
                </div>
              ) : (
                <Button onClick={handleGenerate} disabled={generatePhase !== 'idle'}>
                  {generatePhase === 'starting' ? (
                    <>
                      <Loader2 size={15} className="animate-spin" />
                      Starting...
                    </>
                  ) : (
                    'Generate report'
                  )}
                </Button>
              )}
            </div>
            {generateError && (
              <div className="mt-3">
                <Notice kind="error">{generateError}</Notice>
              </div>
            )}
            {generatePhase === 'polling' && (
              <p className="mt-3 font-narrative text-sm leading-relaxed text-ink-soft">
                Six analysis agents are reviewing the evidence. This takes one to
                five minutes. The platform never sends outreach on its own.
              </p>
            )}
            {sources && (
              <ul className="mt-4 divide-y divide-line-soft">
                {sources.map((source) => (
                  <li key={source.id} className="flex items-center gap-3 py-2.5">
                    <span className="label-caps w-24 shrink-0 text-ink-faint">
                      {source.source_type}
                    </span>
                    <span className="min-w-0 flex-1 truncate font-narrative text-sm text-ink">
                      {source.title ?? domainOf(source.url)}
                    </span>
                    <a
                      href={source.url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 font-mono text-[11px] text-ink-soft hover:text-action"
                    >
                      {domainOf(source.url)}
                      <ExternalLink size={11} />
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </main>
  )
}
