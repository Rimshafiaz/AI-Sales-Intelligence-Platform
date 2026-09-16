import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Check, Copy } from 'lucide-react'
import type { ProspectEvidenceBriefData } from '../../lib/report'

function Section({ title, children }: { title: string; children: ReactNode }) {
  return <section className="mt-8"><h2 className="label-caps border-b border-line-soft pb-2 text-ink-soft">{title}</h2><div className="mt-3">{children}</div></section>
}

function CopyDraftButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  return <button type="button" onClick={async () => { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000) }} className="inline-flex items-center gap-1 rounded-control border border-line px-1.5 py-0.5 font-ui text-[11px] text-ink-soft hover:border-ink-faint hover:text-ink">{copied ? <Check size={11} className="text-ok-ink" /> : <Copy size={11} />}{copied ? 'Copied' : 'Copy'}</button>
}

const verdictStyle: Record<string, string> = {
  qualified: 'border-ok-bg bg-ok-bg/50 text-ok-ink',
  needs_review: 'border-warn-bg bg-warn-bg/60 text-warn-ink',
  not_a_fit: 'border-line bg-slate-wash text-ink-soft',
}

const legacyModelLabels: Record<string, string> = {
  'web_conversion.no_verified_web_presence': 'Official website',
  'web_conversion.mobile_performance': 'Mobile performance',
  'web_conversion.booking_contact_path': 'Booking and contact path',
  'web_conversion.restaurant_reservation_path': 'Reservation path',
  'web_conversion.restaurant_customer_path': 'Customer path',
  'web_conversion.fitness_membership_path': 'Membership enquiry path',
  'web_conversion.retail_product_path': 'Product enquiry path',
  'web_conversion.clinic_patient_path': 'Patient contact path',
  'social_presence.dormant_official_presence': 'Social activity',
}

function contactHref(type: string, value: string): string {
  if (type === 'email') return `mailto:${value}`
  if (type === 'phone') return `tel:${value}`
  return value
}

export function ProspectEvidenceBriefView({ brief, outreach }: { brief: ProspectEvidenceBriefData; outreach?: ProspectEvidenceBriefData['outreach'] }) {
  const current = brief.schema_version === 2
  const aggregate = brief.aggregate_verdict ?? 'needs_review'
  const assessment = current ? brief.opportunity_assessment ?? [] : (brief.qualifications ?? (brief.verdict ? [brief.verdict] : [])).map((item) => ({
    check: legacyModelLabels[item.opportunity_model_id] ?? 'Selected opportunity',
    result: item.state === 'likely' ? ('opportunity_found' as const) : item.state === 'not_eligible' ? ('no_issue_observed' as const) : ('unresolved' as const),
    evidence_summary: item.reason,
    evidence_keys: item.supporting_evidence_keys,
  }))
  const approach = brief.recommended_approach ?? (brief.pitch_angle ? {
    opportunity_summary: brief.findings?.[0] ?? { statement: brief.pitch_angle.statement, claim_kind: 'inference' as const, evidence_keys: brief.pitch_angle.evidence_keys },
    pitch_angle: brief.pitch_angle,
    personalization_basis: brief.findings ?? [],
    forbidden_claims: [],
    caveats: brief.caveats ?? [],
  } : null)
  const explanation = brief.verdict_explanation ?? brief.aggregate_headline ?? brief.verdict?.reason
  const unresolved = brief.unresolved_evidence ?? (aggregate === 'needs_review' ? brief.caveats ?? [] : [])

  return <>
    <section className="mt-6 rounded-card border border-line-soft bg-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div><h2 className="text-title-md font-semibold text-ink">{brief.prospect.business_name}</h2><p className="mt-1 text-sm text-ink-soft">{[brief.prospect.location, brief.prospect.business_descriptor].filter(Boolean).join(' : ')}</p></div>
        <span className={'rounded-control border px-2 py-1 font-ui text-sm font-semibold ' + verdictStyle[aggregate]}>{aggregate.replaceAll('_', ' ').toUpperCase()}</span>
      </div>
      {explanation && <p className="mt-4 max-w-3xl text-sm text-ink">{explanation}</p>}
      <p className="mt-2 text-xs text-ink-faint">Campaign: {brief.objective.offering}</p>
    </section>

    <Section title="Opportunity assessment">
      <div className="overflow-hidden rounded-card border border-line-soft bg-card">
        <div className="hidden grid-cols-[1fr_1fr_2fr] gap-4 border-b border-line-soft px-4 py-2 sm:grid">{['Check', 'Result', 'Evidence'].map((label) => <span key={label} className="label-caps text-ink-faint">{label}</span>)}</div>
        {assessment.map((row) => <div key={row.check} className="grid gap-1 border-b border-line-soft px-4 py-3 last:border-0 sm:grid-cols-[1fr_1fr_2fr] sm:gap-4"><span className="text-sm font-medium text-ink">{row.check}</span><span className="text-sm text-ink-soft">{row.result === 'opportunity_found' ? 'Opportunity found' : row.result === 'not_an_opportunity' ? 'Not an opportunity' : row.result === 'no_issue_observed' ? 'No issue observed' : 'Unresolved'}</span><span className="text-sm text-ink-soft">{row.evidence_summary}</span></div>)}
      </div>
    </Section>

    {aggregate === 'qualified' && approach && <Section title="Recommended approach">
      <div className="space-y-4 rounded-card border border-line-soft bg-card p-4">
        <p className="text-sm text-ink">{approach.opportunity_summary.statement}</p><p className="text-sm font-medium text-ink">{approach.pitch_angle.statement}</p>
        {approach.personalization_basis.length > 0 && <div><p className="label-caps text-ink-faint">Personalize around</p><ul className="mt-2 space-y-1 text-sm text-ink-soft">{approach.personalization_basis.map((item) => <li key={item.statement}>{item.statement}</li>)}</ul></div>}
        {approach.forbidden_claims.length > 0 && <div><p className="label-caps text-ink-faint">Do not claim</p><ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink-soft">{approach.forbidden_claims.map((claim) => <li key={claim}>{claim}</li>)}</ul></div>}
      </div>
    </Section>}

    {aggregate === 'qualified' && brief.outreach_drafts.length > 0 && <Section title="Outreach">
      <div className="space-y-3">{brief.outreach_drafts.map((draft) => <article key={draft.channel} className="rounded-control border border-line-soft bg-card p-4"><div className="flex items-center justify-between gap-3"><p className="label-caps text-ink-soft">{draft.channel}</p><CopyDraftButton text={[draft.subject, draft.message].filter(Boolean).join('\n\n')} /></div>{draft.subject && <p className="mt-2 text-sm font-semibold text-ink">Subject: {draft.subject}</p>}<p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-ink">{draft.message}</p><p className="mt-3 text-xs text-ink-faint">Based on: {draft.grounding.map((item) => item.claim).join('; ')}</p></article>)}</div>
      {outreach && <Link to={`/campaigns/${outreach.campaign_id}/prospects/${outreach.prospect_id}`} className="mt-3 inline-block text-label-md font-semibold text-action hover:text-ink">Manage approval and sending in Outreach</Link>}
    </Section>}

    {brief.contacts.length > 0 && <Section title="Contact paths"><div className="grid gap-3 sm:grid-cols-2">{brief.contacts.map((contact) => <div key={`${contact.contact_type}-${contact.value}`} className="rounded-control border border-line-soft bg-card p-3"><p className="label-caps text-ink-faint">{contact.contact_type.replaceAll('_', ' ')}</p><a href={contactHref(contact.contact_type, contact.value)} target={['email', 'phone'].includes(contact.contact_type) ? undefined : '_blank'} rel="noreferrer" className="mt-1 block break-all text-sm text-action hover:text-ink">{contact.value}</a><p className="mt-1 text-xs capitalize text-ink-faint">{contact.state}</p></div>)}</div></Section>}

    {unresolved.length > 0 && <Section title="What remains unresolved"><ul className="list-disc space-y-1 pl-5 text-sm text-ink-soft">{unresolved.map((item) => <li key={item}>{item}</li>)}</ul></Section>}
    {(approach?.caveats.length ?? 0) > 0 && <Section title="Caveats"><ul className="list-disc space-y-1 pl-5 text-sm text-ink-soft">{approach?.caveats.map((item) => <li key={item}>{item}</li>)}</ul></Section>}

    <details className="mt-8 rounded-card border border-line-soft bg-card p-4"><summary className="cursor-pointer font-ui text-sm font-semibold text-ink">Evidence &amp; sources ({brief.evidence.length + brief.sources.length})</summary><div className="mt-4 space-y-3">{brief.evidence.map((item) => <div key={item.key} className="text-sm text-ink-soft"><p className="text-ink">{item.supporting_value}</p><p className="mt-0.5 text-xs text-ink-faint">{item.source.provider}</p></div>)}{brief.sources.map((source) => <a key={source.key} href={source.source_url} target="_blank" rel="noreferrer" className="block text-sm text-action hover:text-ink">{source.title ?? source.source_url}</a>)}</div></details>
  </>
}
