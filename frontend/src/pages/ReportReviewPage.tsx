import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Check, Copy, Loader2 } from 'lucide-react'
import { api } from '../lib/api'
import {
  buildCitationIndex,
  domainOf,
  type Finding,
  type ReportDetail,
} from '../lib/report'
import type { Company } from '../lib/types'
import {
  Button,
  Notice,
  RecommendationBadge,
  StatusBadge,
  TextField,
  TextareaField,
} from '../components/ui'
import { FindingText } from '../components/report/FindingText'

function SectionHeader({ number, title }: { number: string; title: string }) {
  return (
    <h2 className="label-caps flex items-center gap-2 border-b border-line-soft pb-2 text-ink-soft">
      <span className="text-ink">{number}</span>
      <span>+</span>
      <span>{title}</span>
    </h2>
  )
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      type="button"
      onClick={async () => {
        await navigator.clipboard.writeText(text)
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      }}
      className="inline-flex items-center gap-1 rounded-control border border-line px-1.5 py-0.5 font-ui text-[11px] text-ink-soft transition-colors hover:border-ink-faint hover:text-ink"
    >
      {copied ? (
        <>
          <Check size={11} className="text-forest" />
          Copied
        </>
      ) : (
        <>
          <Copy size={11} />
          Copy
        </>
      )}
    </button>
  )
}

export default function ReportReviewPage() {
  const { reportId } = useParams<{ reportId: string }>()
  const navigate = useNavigate()
  const [detail, setDetail] = useState<ReportDetail | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [company, setCompany] = useState<Company | null>(null)
  const [approving, setApproving] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [editMode, setEditMode] = useState(false)
  const [saving, setSaving] = useState(false)
  const [showRegenerate, setShowRegenerate] = useState(false)
  const [regenPhase, setRegenPhase] = useState<'idle' | 'starting' | 'polling'>('idle')
  const [regenInstruction, setRegenInstruction] = useState('')

  interface EditFormState {
    strategy: string
    sales_angle: string
    value_proposition: string
    roles: string[]
    cold_email: string
    linkedin_message: string
    review_note: string
  }
  const [editForm, setEditForm] = useState<EditFormState | null>(null)

  useEffect(() => {
    if (!reportId) return
    api<ReportDetail>(`/reports/${reportId}`)
      .then(setDetail)
      .catch((e: unknown) =>
        setLoadError(e instanceof Error ? e.message : 'Could not load the report.'),
      )
  }, [reportId])

  useEffect(() => {
    if (!detail || company) return
    api<Company>(`/companies/${detail.report.company_id}`)
      .then(setCompany)
      .catch(() => setCompany(null))
  }, [detail, company])

  async function handleApprove() {
    if (!detail || approving) return
    setApproving(true)
    setActionError(null)
    try {
      const approved = await api<{ review_status: string; approved_at: string | null }>(
        `/reports/${detail.report.id}/approve`,
        { method: 'POST' },
      )
      setDetail({
        ...detail,
        report: {
          ...detail.report,
          review_status: approved.review_status as 'draft' | 'approved',
          approved_at: approved.approved_at,
        },
      })
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Approval failed.')
    } finally {
      setApproving(false)
    }
  }

  function startEdit() {
    if (!detail) return
    const d = detail.report.report_data
    setEditForm({
      strategy: d.strategy.recommended_strategy.statement,
      sales_angle: d.strategy.recommended_sales_angle.statement,
      value_proposition: d.strategy.suggested_value_proposition.statement,
      roles: d.suggested_decision_makers.map((maker) => maker.suggested_role),
      cold_email: d.personalized_outreach.cold_email,
      linkedin_message: d.personalized_outreach.linkedin_message,
      review_note: detail.report.review_note ?? '',
    })
    setEditMode(true)
    setShowRegenerate(false)
    setActionError(null)
  }

  function cancelEdit() {
    setEditMode(false)
    setEditForm(null)
    setActionError(null)
  }

  async function saveEdits() {
    if (!detail || !editForm) return
    setSaving(true)
    setActionError(null)
    try {
      const body: Record<string, unknown> = {}
      if (editForm.strategy.trim()) body.strategy = editForm.strategy.trim()
      if (editForm.sales_angle.trim()) body.sales_angle = editForm.sales_angle.trim()
      if (editForm.value_proposition.trim())
        body.value_proposition = editForm.value_proposition.trim()
      const roles = editForm.roles.map((role) => role.trim()).filter((role) => role)
      if (roles.length > 0) body.suggested_decision_makers = roles
      if (editForm.cold_email.trim()) body.cold_email = editForm.cold_email.trim()
      if (editForm.linkedin_message.trim())
        body.linkedin_message = editForm.linkedin_message.trim()
      if (editForm.review_note.trim()) body.review_note = editForm.review_note.trim()

      if (Object.keys(body).length > 0) {
        await api(`/reports/${detail.report.id}`, { method: 'PATCH', body })
      }
      const fresh = await api<ReportDetail>(`/reports/${detail.report.id}`)
      setDetail(fresh)
      setEditMode(false)
      setEditForm(null)
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Could not save changes.')
    } finally {
      setSaving(false)
    }
  }

  async function handleRegenerate() {
    if (!detail || regenPhase !== 'idle') return
    setActionError(null)
    setRegenPhase('starting')
    try {
      const instruction = regenInstruction.trim()
      await api<{ status: string }>(`/reports/${detail.report.id}/regenerate`, {
        method: 'POST',
        body: instruction ? { instruction } : {},
      })
      setRegenPhase('polling')
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Could not start regeneration.')
      setRegenPhase('idle')
    }
  }

  useEffect(() => {
    if (regenPhase !== 'polling' || !detail) return
    const original = detail.report
    let attempts = 0
    const interval = setInterval(async () => {
      attempts += 1
      try {
        const page = await api<{
          items: { id: string; research_request_id: string; generated_at: string }[]
        }>('/reports', { params: { page: 1, page_size: 5 } })
        const found = page.items.find(
          (item) =>
            item.research_request_id === original.research_request_id &&
            item.id !== original.id &&
            new Date(item.generated_at) > new Date(original.generated_at),
        )
        if (found) {
          setRegenPhase('idle')
          setRegenInstruction('')
          navigate(`/reports/${found.id}`)
          return
        }
      } catch {
        // transient poll failure; keep polling
      }
      if (attempts >= 200) {
        setRegenPhase('idle')
        setActionError(
          'Regeneration is taking longer than expected. Check History in a minute; the new draft may appear there.',
        )
      }
    }, 3000)
    return () => clearInterval(interval)
  }, [regenPhase, detail, navigate])

  if (loadError) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
        <Notice kind="error">{loadError}</Notice>
        <p className="mt-4 text-sm">
          <Link to="/history" className="text-action hover:underline">
            Back to history
          </Link>
        </p>
      </main>
    )
  }

  if (!detail) {
    return (
      <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
        <div className="h-48 animate-pulse rounded-card border border-line-soft bg-card" />
      </main>
    )
  }

  const { report, sources } = detail
  const data = report.report_data
  const citationIndex = buildCitationIndex(sources)
  const approved = report.review_status === 'approved'

  const scoreTone =
    report.opportunity_score >= 70
      ? 'text-ok-ink'
      : report.opportunity_score >= 40
        ? 'text-warn-ink'
        : 'text-bad-ink'

  return (
    <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link to="/history" className="text-xs text-ink-soft hover:text-ink">
          Back to history
        </Link>
        <div className="flex items-center gap-2">
          <StatusBadge status={report.review_status} />
          <Button variant="secondary" onClick={handleApprove} disabled={approving}>
            {approving ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                Approving...
              </>
            ) : approved ? (
              <>
                <Check size={14} />
                Approved
              </>
            ) : (
              'Approve report'
            )}
          </Button>
          <Button
            variant="secondary"
            onClick={startEdit}
            disabled={editMode || regenPhase !== 'idle'}
          >
            Edit draft
          </Button>
          <Button
            variant="secondary"
            onClick={() => {
              setEditMode(false)
              setEditForm(null)
              setShowRegenerate((visible) => !visible)
            }}
            disabled={editMode || regenPhase !== 'idle'}
          >
            Regenerate
          </Button>
        </div>
      </div>
      {editMode && editForm && (
        <section className="mt-3 rounded-card border border-line-soft bg-card p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="label-caps text-ink-soft">Edit draft</h2>
            <p className="text-xs text-ink-faint">
              Saving any change returns the report to draft. Evidence and scores
              are not editable.
            </p>
          </div>
          <div className="mt-4 space-y-4">
            <TextareaField
              label="Recommended strategy"
              value={editForm.strategy}
              onChange={(event) =>
                setEditForm({ ...editForm, strategy: event.target.value })
              }
            />
            <TextareaField
              label="Recommended sales angle"
              value={editForm.sales_angle}
              onChange={(event) =>
                setEditForm({ ...editForm, sales_angle: event.target.value })
              }
            />
            <TextareaField
              label="Suggested value proposition"
              value={editForm.value_proposition}
              onChange={(event) =>
                setEditForm({ ...editForm, value_proposition: event.target.value })
              }
            />
            {editForm.roles.length > 0 && (
              <div>
                <p className="font-ui text-[13px] font-medium text-ink-soft">
                  Decision-maker roles
                </p>
                <div className="mt-1.5 space-y-2">
                  {editForm.roles.map((role, index) => (
                    <input
                      key={index}
                      value={role}
                      onChange={(event) =>
                        setEditForm({
                          ...editForm,
                          roles: editForm.roles.map((existing, position) =>
                            position === index ? event.target.value : existing,
                          ),
                        })
                      }
                      className="h-9 w-full rounded-control border border-line bg-card px-3 font-ui text-sm text-ink focus:border-ink focus:outline focus:outline-1 focus:outline-action"
                      placeholder={`Role ${index + 1}`}
                    />
                  ))}
                </div>
              </div>
            )}
            <TextareaField
              label="Cold email"
              rows={6}
              value={editForm.cold_email}
              onChange={(event) =>
                setEditForm({ ...editForm, cold_email: event.target.value })
              }
            />
            <TextareaField
              label="LinkedIn message"
              rows={4}
              value={editForm.linkedin_message}
              onChange={(event) =>
                setEditForm({ ...editForm, linkedin_message: event.target.value })
              }
            />
            <TextareaField
              label="Review note (private)"
              rows={3}
              value={editForm.review_note}
              onChange={(event) =>
                setEditForm({ ...editForm, review_note: event.target.value })
              }
            />
          </div>
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="secondary" onClick={cancelEdit} disabled={saving}>
              Cancel
            </Button>
            <Button onClick={saveEdits} disabled={saving}>
              {saving ? 'Saving...' : 'Save changes'}
            </Button>
          </div>
        </section>
      )}

      {showRegenerate && (
        <section className="mt-3 rounded-card border border-line-soft bg-card p-5">
          <h2 className="label-caps text-ink-soft">Regenerate report</h2>
          <p className="mt-1 text-xs text-ink-faint">
            Creates a new draft from the same evidence. The original report is
            kept. Takes 1 to 5 minutes.
          </p>
          {regenPhase === 'polling' ? (
            <div className="mt-3 flex items-center gap-2 rounded-control bg-slate-wash p-3">
              <Loader2 size={15} className="animate-spin text-action" />
              <p className="font-ui text-sm text-ink">
                Regeneration is running. This typically takes 1 to 5 minutes.
                Keep this page open; you will be moved to the new draft
                automatically.
              </p>
            </div>
          ) : (
            <>
              <div className="mt-3">
                <TextField
                  label="Guidance (optional)"
                  placeholder="e.g. focus the outreach on hiring growth"
                  maxLength={500}
                  value={regenInstruction}
                  onChange={(event) => setRegenInstruction(event.target.value)}
                />
              </div>
              <div className="mt-4 flex justify-end gap-2">
                <Button
                  variant="secondary"
                  onClick={() => setShowRegenerate(false)}
                  disabled={regenPhase !== 'idle'}
                >
                  Cancel
                </Button>
                <Button onClick={handleRegenerate} disabled={regenPhase !== 'idle'}>
                  Regenerate report
                </Button>
              </div>
            </>
          )}
        </section>
      )}
      {actionError && (
        <div className="mt-3">
          <Notice kind="error">{actionError}</Notice>
        </div>
      )}

      <h1 className="mt-6 font-display text-3xl font-bold tracking-tight text-ink">
        {company?.name ?? 'Intelligence Report'}
      </h1>
      <p className="mt-1 font-ui text-xs text-ink-faint">
        Generated {new Date(report.generated_at).toLocaleString()} | Report{' '}
        <span className="font-mono">{report.id.slice(0, 8)}</span>
      </p>

      <section className="mt-6 rounded-card border border-line-soft bg-card p-5">
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div>
            <p className="label-caps text-ink-faint">Opportunity composite</p>
            <p className={'mt-1 font-display text-5xl font-bold ' + scoreTone}>
              {report.opportunity_score}
              <span className="text-base font-medium text-ink-faint"> / 100</span>
            </p>
          </div>
          <div>
            <p className="label-caps text-ink-faint">Recommendation</p>
            <div className="mt-1.5">
              <RecommendationBadge recommendation={report.contact_recommendation} />
            </div>
          </div>
          <div>
            <p className="label-caps text-ink-faint">Confidence</p>
            <p className="mt-1 font-display text-2xl font-semibold text-ink">
              {data.confidence.score}
              <span className="text-sm font-medium text-ink-faint"> / 100</span>
            </p>
          </div>
        </div>
        <div className="mt-4 border-t border-line-soft pt-3">
          <FindingText
            finding={data.opportunity_assessment.reasons[0]}
            citationIndex={citationIndex}
          />
        </div>
      </section>

      <section className="mt-8">
        <SectionHeader number="01" title="Executive Summary" />
        <div className="mt-3">
          <FindingText finding={data.executive_summary} citationIndex={citationIndex} variant="narrative" />
        </div>
      </section>

      <section className="mt-8">
        <SectionHeader number="02" title="Company Profile" />
        <div className="mt-3 space-y-4">
          <FindingText
            finding={data.company_profile.company_summary}
            citationIndex={citationIndex}
          />
          {(() => {
            const facts: [string, Finding][] = (
              [
                ['Industry', data.company_profile.industry],
                ['Headquarters', data.company_profile.headquarters],
                ['Employee count', data.company_profile.employee_count],
                ['Company size', data.company_profile.company_size],
              ] as [string, Finding | null][]
            ).filter((pair): pair is [string, Finding] => pair[1] !== null)
            if (facts.length === 0) return null
            return (
              <div className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-3">
                {facts.map(([label, finding]) => (
                  <div
                    key={label}
                    className="rounded-card border border-line-soft bg-card p-3"
                  >
                    <p className="label-caps text-ink-faint">{label}</p>
                    <FindingText finding={finding} citationIndex={citationIndex} className="mt-1" />
                  </div>
                ))}
              </div>
            )
          })()}
          {data.company_profile.company_description && (
            <div>
              <p className="label-caps text-ink-faint">Description</p>
              <FindingText
                finding={data.company_profile.company_description} citationIndex={citationIndex} variant="narrative"
                className="mt-0.5"
              />
            </div>
          )}
          {data.company_profile.website_metadata && (
            <div>
              <p className="label-caps text-ink-faint">Website</p>
              <FindingText
                finding={data.company_profile.website_metadata}
                citationIndex={citationIndex}
                className="mt-0.5"
              />
            </div>
          )}
          {data.company_profile.products_and_services.length > 0 && (
            <div>
              <p className="label-caps text-ink-faint">Products and services</p>
              <ul className="mt-1 space-y-2">
                {data.company_profile.products_and_services.map((finding) => (
                  <li key={finding.statement}>
                    <FindingText finding={finding} citationIndex={citationIndex} />
                  </li>
                ))}
              </ul>
            </div>
          )}
          {data.company_profile.funding_information.length > 0 && (
            <div>
              <p className="label-caps text-ink-faint">Funding information</p>
              <ul className="mt-1 space-y-2">
                {data.company_profile.funding_information.map((finding) => (
                  <li key={finding.statement}>
                    <FindingText finding={finding} citationIndex={citationIndex} />
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </section>

      {data.technologies.length > 0 && (
        <section className="mt-8">
          <SectionHeader number="03" title="Technologies" />
          <div className="mt-3 space-y-3">
            {data.technologies.map((item) => (
              <div key={item.technology.statement} className="rounded-control border border-line-soft bg-card p-3">
                <FindingText finding={item.technology} citationIndex={citationIndex} />
                {item.implication && (
                  <div className="mt-2 border-l-2 border-action pl-3">
                    <FindingText finding={item.implication} citationIndex={citationIndex} />
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {data.business_signals.length > 0 && (
        <section className="mt-8">
          <SectionHeader number="04" title="Business Signals" />
          <ul className="mt-3 divide-y divide-line-soft">
            {data.business_signals.map((signal) => (
              <li key={signal.finding.statement} className="py-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-control border border-line bg-slate-wash px-1.5 py-0.5 font-ui text-[10px] font-medium uppercase text-ink-soft">
                    {signal.signal_type}
                  </span>
                  {signal.occurred_at && (
                    <span className="font-mono text-[11px] text-ink-faint">
                      {signal.occurred_at}
                    </span>
                  )}
                </div>
                <div className="mt-1">
                  <FindingText finding={signal.finding} citationIndex={citationIndex} />
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="mt-8">
        <SectionHeader number="05" title="Opportunity Assessment" />
        <div className="mt-3 space-y-3">
          {data.opportunity_assessment.reasons.map((reason, index) => (
            <div key={reason.statement} className="flex gap-3">
              <span className="font-display text-sm font-bold text-ink-faint">{index + 1}.</span>
              <FindingText finding={reason} citationIndex={citationIndex} className="flex-1" />
            </div>
          ))}
        </div>
      </section>

      <section className="mt-8">
        <SectionHeader number="06" title="Contact Recommendation" />
        <div className="mt-3 space-y-2">
          <RecommendationBadge recommendation={report.contact_recommendation} />
          <FindingText
            finding={data.contact_recommendation.rationale}
            citationIndex={citationIndex}
          />
        </div>
      </section>

      {data.pain_points.length > 0 && (
        <section className="mt-8">
          <SectionHeader number="07" title="Pain Points and Operational Hypotheses" />
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {data.pain_points.map((painPoint) => (
              <div key={painPoint.hypothesis.statement} className="rounded-control border border-line-soft bg-card p-3">
                <span className="label-caps text-ink-soft">
                  {painPoint.confidence} confidence
                </span>
                <div className="mt-1.5">
                  <FindingText finding={painPoint.hypothesis} citationIndex={citationIndex} />
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="mt-8">
        <SectionHeader number="08" title="Strategic Angle and Value Proposition" />
        <div className="mt-3 space-y-4">
          {(
            [
              ['Recommended strategy', data.strategy.recommended_strategy],
              ['Recommended sales angle', data.strategy.recommended_sales_angle],
              ['Suggested value proposition', data.strategy.suggested_value_proposition],
            ] as [string, Finding][]
          ).map(([label, finding]) => (
            <div key={label}>
              <p className="label-caps text-ink-faint">{label}</p>
              <FindingText finding={finding} citationIndex={citationIndex} className="mt-0.5" />
            </div>
          ))}
        </div>
      </section>

      {data.suggested_decision_makers.length > 0 && (
        <section className="mt-8">
          <SectionHeader number="09" title="Suggested Decision Makers" />
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {data.suggested_decision_makers.map((maker) => (
              <div key={maker.suggested_role} className="rounded-control border border-line-soft bg-card p-3">
                <p className="font-display text-sm font-semibold text-ink">
                  {maker.suggested_role}
                </p>
                <div className="mt-1">
                  <FindingText finding={maker.rationale} citationIndex={citationIndex} />
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="mt-8">
        <SectionHeader number="10" title="Personalized Outreach Drafts" />
        <p className="mt-2 text-xs text-ink-faint">
          Drafts for manual use. The platform never sends outreach on its own.
        </p>
        <div className="mt-3 space-y-3">
          {(
            [
              ['Cold email', data.personalized_outreach.cold_email],
              ['LinkedIn message', data.personalized_outreach.linkedin_message],
            ] as [string, string][]
          ).map(([label, text]) => (
            <div key={label} className="rounded-control border border-line-soft bg-card p-3">
              <div className="flex items-center justify-between">
                <p className="label-caps text-ink-soft">{label}</p>
                <CopyButton text={text} />
              </div>
              <p className="mt-2 whitespace-pre-wrap font-narrative text-sm leading-relaxed text-ink">
                {text}
              </p>
            </div>
          ))}
          <div className="border-l-2 border-action pl-3">
            <FindingText
              finding={data.personalized_outreach.personalization_rationale}
              citationIndex={citationIndex}
            />
          </div>
        </div>
      </section>

      {data.caveats.length > 0 && (
        <section className="mt-8">
          <SectionHeader number="11" title="Caveats and Boundaries" />
          <ul className="mt-3 space-y-1.5">
            {data.caveats.map((caveat) => (
              <li
                key={caveat}
                className="rounded-control border border-warn-bg bg-warn-bg/50 p-2.5 text-sm text-warn-ink"
              >
                {caveat}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="mt-8">
        <SectionHeader number="12" title="Verified Sources" />
        <ul className="mt-3 divide-y divide-line-soft rounded-card border border-line-soft bg-card">
          {sources.map((source) => {
            const number = citationIndex.get(source.url.replace(/\/+$/, ''))
            return (
              <li key={source.id} className="flex items-center gap-3 px-4 py-2.5">
                <span className="font-mono text-xs text-ink-faint">[{number}]</span>
                <a
                  href={source.url}
                  target="_blank"
                  rel="noreferrer"
                  className="min-w-0 flex-1 truncate font-narrative text-sm text-ink hover:text-action"
                >
                  {source.title ?? domainOf(source.url)}
                </a>
                <span className="label-caps hidden text-ink-faint sm:block">
                  {source.source_type}
                </span>
                <a
                  href={source.url}
                  target="_blank"
                  rel="noreferrer"
                  className="font-mono text-[11px] text-ink-soft hover:text-action"
                >
                  {domainOf(source.url)}
                </a>
              </li>
            )
          })}
        </ul>
        {report.review_note && (
          <div className="mt-4 rounded-card border border-line-soft bg-slate-wash p-3">
            <p className="label-caps text-ink-faint">Private review note</p>
            <p className="mt-1 font-narrative text-sm text-ink">{report.review_note}</p>
          </div>
        )}
      </section>
    </main>
  )
}
