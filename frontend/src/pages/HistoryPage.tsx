import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronLeft, ChevronRight, Eye, Search, X } from 'lucide-react'
import { api } from '../lib/api'
import type { ReportListResponse } from '../lib/types'
import { Button, Notice, RecommendationBadge, StatusBadge } from '../components/ui'

const PAGE_SIZE_DEFAULT = 10
const PAGE_SIZE_OPTIONS = [10, 25, 50]

interface FilterInputs {
  company: string
  industry: string
  from_date: string
  to_date: string
  min_score: string
  max_score: string
  report_status: string
}

const EMPTY_FILTERS: FilterInputs = {
  company: '',
  industry: '',
  from_date: '',
  to_date: '',
  min_score: '',
  max_score: '',
  report_status: '',
}

const FILTER_LABELS: Record<string, string> = {
  company: 'Company',
  industry: 'Industry',
  from_date: 'From',
  to_date: 'To',
  min_score: 'Min score',
  max_score: 'Max score',
  report_status: 'Status',
}

function StatusSegmented({
  value,
  onChange,
}: {
  value: string
  onChange: (value: string) => void
}) {
  const options = [
    { label: 'All', value: '' },
    { label: 'Approved', value: 'approved' },
    { label: 'Draft', value: 'draft' },
  ]
  return (
    <div className="flex rounded-control border border-line-soft bg-slate-wash p-0.5">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          className={
            'px-2.5 py-1 font-ui text-xs transition-colors ' +
            (value === option.value
              ? 'rounded-[3px] border border-line-soft bg-card font-semibold text-ink'
              : 'text-ink-soft hover:text-ink')
          }
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

function FilterGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="label-caps text-ink-faint">{label}</p>
      <div className="mt-1.5">{children}</div>
    </div>
  )
}

const filterInputClass =
  'h-9 w-full rounded-control border border-line bg-card px-3 font-ui text-sm text-ink ' +
  'placeholder:text-ink-faint focus:border-ink focus:outline focus:outline-1 focus:outline-action'

export default function HistoryPage() {
  const navigate = useNavigate()
  const [inputs, setInputs] = useState<FilterInputs>(EMPTY_FILTERS)
  const [applied, setApplied] = useState<Partial<Record<string, string>>>({})
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(PAGE_SIZE_DEFAULT)
  const [data, setData] = useState<ReportListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    api<ReportListResponse>('/reports', {
      params: { page, page_size: pageSize, ...Object.fromEntries(Object.entries(applied).filter(([, v]) => v)) },
    })
      .then((response) => {
        if (!cancelled) setData(response)
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Could not load history.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [applied, page, pageSize])

  function handleApply(event: FormEvent) {
    event.preventDefault()
    if (inputs.from_date && inputs.to_date && inputs.from_date > inputs.to_date) {
      setError('From date cannot be after to date.')
      return
    }
    if (
      inputs.min_score &&
      inputs.max_score &&
      Number(inputs.min_score) > Number(inputs.max_score)
    ) {
      setError('Min score cannot be greater than max score.')
      return
    }
    const next: Partial<Record<string, string>> = {}
    for (const [key, value] of Object.entries(inputs)) {
      if (value.trim()) next[key] = value.trim()
    }
    setApplied(next)
    setPage(1)
    setError(null)
  }

  function clearAll() {
    setInputs(EMPTY_FILTERS)
    setApplied({})
    setPage(1)
    setError(null)
  }

  function removeFilter(key: string) {
    setApplied((current) => {
      const next = { ...current }
      delete next[key]
      return next
    })
    setInputs((current) => ({ ...current, [key]: '' }))
    setPage(1)
  }

  const hasFilters = Object.keys(applied).length > 0
  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1

  return (
    <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
      <p className="label-caps text-ink-faint">Workspace &gt; Reports</p>
      <div className="mt-1 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-semibold text-ink">Report History</h1>
          <p className="mt-2 text-sm text-ink-soft">
            Complete archive of your evidence-backed intelligence reports, newest first.
          </p>
        </div>
        <Button onClick={() => navigate('/research')}>New research</Button>
      </div>

      <form
        onSubmit={handleApply}
        className="mt-6 rounded-card border border-line-soft bg-card p-5"
      >
        <div className="grid gap-4 lg:grid-cols-[1.1fr_1fr_1.3fr_1.2fr_0.9fr]">
          <FilterGroup label="Company">
            <div className="relative">
              <Search
                size={14}
                className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-faint"
              />
              <input
                value={inputs.company}
                onChange={(event) => setInputs({ ...inputs, company: event.target.value })}
                placeholder="Search company"
                className={filterInputClass + ' pl-8'}
              />
            </div>
          </FilterGroup>
          <FilterGroup label="Industry">
            <input
              value={inputs.industry}
              onChange={(event) => setInputs({ ...inputs, industry: event.target.value })}
              placeholder="e.g. fintech"
              className={filterInputClass}
            />
          </FilterGroup>
          <FilterGroup label="Date window">
            <div className="flex items-center gap-1.5">
              <input
                type="date"
                value={inputs.from_date}
                onChange={(event) => setInputs({ ...inputs, from_date: event.target.value })}
                className={filterInputClass}
              />
              <input
                type="date"
                value={inputs.to_date}
                onChange={(event) => setInputs({ ...inputs, to_date: event.target.value })}
                className={filterInputClass}
              />
            </div>
          </FilterGroup>
          <FilterGroup label="Score (min, max)">
            <div className="flex items-center gap-1.5">
              <input
                type="number"
                min={0}
                max={100}
                placeholder="0"
                value={inputs.min_score}
                onChange={(event) => setInputs({ ...inputs, min_score: event.target.value })}
                className={filterInputClass}
              />
              <span className="text-ink-faint">&ndash;</span>
              <input
                type="number"
                min={0}
                max={100}
                placeholder="100"
                value={inputs.max_score}
                onChange={(event) => setInputs({ ...inputs, max_score: event.target.value })}
                className={filterInputClass}
              />
            </div>
          </FilterGroup>
          <FilterGroup label="Status">
            <StatusSegmented
              value={inputs.report_status}
              onChange={(value) => setInputs({ ...inputs, report_status: value })}
            />
          </FilterGroup>
        </div>

        {error && (
          <div className="mt-4">
            <Notice kind="error">{error}</Notice>
          </div>
        )}

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          {hasFilters ? (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="label-caps text-ink-faint">Active criteria:</span>
              {Object.entries(applied).map(([key, value]) => (
                <span
                  key={key}
                  className="inline-flex items-center gap-1 rounded-control border border-line bg-canvas px-1.5 py-0.5 font-ui text-[11px] text-ink-soft"
                >
                  {FILTER_LABELS[key]}: <span className="font-medium text-ink">{value}</span>
                  <button
                    type="button"
                    onClick={() => removeFilter(key)}
                    aria-label={`Remove ${FILTER_LABELS[key]} filter`}
                    className="text-ink-faint hover:text-ink"
                  >
                    <X size={11} />
                  </button>
                </span>
              ))}
              <button
                type="button"
                onClick={clearAll}
                className="font-ui text-[11px] text-action hover:underline"
              >
                Clear all
              </button>
            </div>
          ) : (
            <span className="font-ui text-[11px] text-ink-faint">No filters applied</span>
          )}
        </div>
      </form>

      <section className="mt-6">
        {loading && (
          <div className="space-y-2">
            {[1, 2, 3, 4].map((index) => (
              <div
                key={index}
                className="h-14 animate-pulse rounded-card border border-line-soft bg-card"
              />
            ))}
          </div>
        )}

        {!loading && error && <Notice kind="error">{error}</Notice>}

        {!loading && data && data.items.length === 0 && (
          <div className="rounded-card border border-line-soft bg-card p-8 text-center">
            <p className="font-narrative text-sm text-ink-soft">
              {hasFilters
                ? 'No reports match these filters.'
                : 'No reports yet. Generate your first report from the dashboard.'}
            </p>
          </div>
        )}

        {!loading && data && data.items.length > 0 && (
          <>
            <div className="overflow-x-auto rounded-card border border-line-soft bg-card">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-ink">
                    {[
                      'Company name',
                      'Opportunity score',
                      'Recommendation',
                      'Review status',
                      'Generated date',
                      'Actions',
                    ].map((column) => (
                      <th
                        key={column}
                        className="px-4 py-2.5 font-ui text-[11px] font-medium uppercase tracking-wide text-ink-soft"
                      >
                        {column}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((item) => (
                    <tr
                      key={item.id}
                      onClick={() => navigate(`/reports/${item.id}`)}
                      className="cursor-pointer border-b border-line-soft transition-colors last:border-b-0 hover:bg-canvas"
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <span className="flex h-8 w-8 items-center justify-center rounded-control border border-line bg-canvas font-narrative text-sm font-bold text-ink">
                            {item.company_name.charAt(0).toUpperCase()}
                          </span>
                          <span className="font-narrative text-sm font-bold text-ink">
                            {item.company_name}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className="font-mono text-sm text-ink">
                          {item.opportunity_score}
                        </span>
                        <span className="text-xs text-ink-faint">/100</span>
                        <div className="mt-1 h-1 w-24 rounded-full bg-line-soft">
                          <div
                            className="h-1 rounded-full bg-action"
                            style={{ width: `${item.opportunity_score}%` }}
                          />
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <RecommendationBadge recommendation={item.contact_recommendation} />
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={item.review_status} />
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-ink-soft">
                        {new Date(item.generated_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3">
                        <button
                          type="button"
                          aria-label={`Open ${item.company_name} report`}
                          onClick={(event) => {
                            event.stopPropagation()
                            navigate(`/reports/${item.id}`)
                          }}
                          className="rounded-control border border-line p-1.5 text-ink-soft transition-colors hover:border-ink-faint hover:text-ink"
                        >
                          <Eye size={14} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
              <p className="font-ui text-xs text-ink-soft">
                Showing{' '}
                <span className="font-semibold text-ink">
                  {(data.page - 1) * data.page_size + 1}&ndash;
                  {(data.page - 1) * data.page_size + data.items.length}
                </span>{' '}
                of <span className="font-semibold text-ink">{data.total}</span> reports
              </p>
              <div className="flex items-center gap-3">
                <label className="flex items-center gap-1.5 font-ui text-xs text-ink-soft">
                  Page size
                  <select
                    value={pageSize}
                    onChange={(event) => {
                      setPageSize(Number(event.target.value))
                      setPage(1)
                    }}
                    className="h-8 rounded-control border border-line bg-card px-1.5 font-ui text-xs text-ink"
                  >
                    {PAGE_SIZE_OPTIONS.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </label>
                <span className="font-ui text-xs text-ink-soft">
                  Page {data.page} of {totalPages}
                </span>
                <Button
                  variant="secondary"
                  disabled={data.page <= 1}
                  onClick={() => setPage((current) => current - 1)}
                >
                  <ChevronLeft size={14} />
                  Previous
                </Button>
                <Button
                  variant="secondary"
                  disabled={data.page * data.page_size >= data.total}
                  onClick={() => setPage((current) => current + 1)}
                >
                  Next
                  <ChevronRight size={14} />
                </Button>
              </div>
            </div>
          </>
        )}
      </section>
    </main>
  )
}
