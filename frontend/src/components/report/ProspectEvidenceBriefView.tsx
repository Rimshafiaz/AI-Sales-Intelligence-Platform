import { useState, type ReactNode } from 'react'
import { Check, Copy, ExternalLink } from 'lucide-react'
import type { BriefEvidence, ProspectEvidenceBriefData } from '../../lib/report'

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-8">
      <h2 className="label-caps border-b border-line-soft pb-2 text-ink-soft">{title}</h2>
      <div className="mt-3">{children}</div>
    </section>
  )
}

function CopyDraftButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      type="button"
      onClick={async () => {
        await navigator.clipboard.writeText(text)
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      }}
      className="inline-flex items-center gap-1 rounded-control border border-line px-1.5 py-0.5 font-ui text-[11px] text-ink-soft hover:border-ink-faint hover:text-ink"
    >
      {copied ? <Check size={11} className="text-ok-ink" /> : <Copy size={11} />}
      {copied ? 'Copied' : 'Copy'}
    </button>
  )
}

function EvidenceList({ keys, evidence }: { keys: string[]; evidence: BriefEvidence[] }) {
  const items = keys
    .map((key) => evidence.find((item) => item.key === key))
    .filter((item): item is BriefEvidence => item !== undefined)
  if (items.length === 0) return null
  return (
    <ul className="mt-2 space-y-1.5 border-l-2 border-line-soft pl-3">
      {items.map((item) => (
        <li key={item.key} className="text-xs text-ink-soft">
          <span className="font-medium text-ink">{item.supporting_value}</span>{' '}
          <span className="text-ink-faint">· {item.source.provider}</span>
          {item.source.source_url && (
            <a
              href={item.source.source_url}
              target="_blank"
              rel="noreferrer"
              aria-label={`Open evidence source from ${item.source.provider}`}
              className="ml-1 inline-flex align-text-bottom text-action hover:text-ink"
            >
              <ExternalLink size={12} />
            </a>
          )}
        </li>
      ))}
    </ul>
  )
}

const verdictStyle: Record<string, string> = {
  likely: 'border-ok-bg bg-ok-bg/50 text-ok-ink',
  insufficient_evidence: 'border-warn-bg bg-warn-bg/60 text-warn-ink',
  not_eligible: 'border-line bg-slate-wash text-ink-soft',
  qualified: 'border-ok-bg bg-ok-bg/50 text-ok-ink',
  needs_review: 'border-warn-bg bg-warn-bg/60 text-warn-ink',
  not_a_fit: 'border-line bg-slate-wash text-ink-soft',
}

const evidenceStyle = {
  observed: 'bg-slate-wash text-ink-soft',
  derived_metric: 'bg-slate-wash text-ink-soft',
  inference: 'bg-warn-bg/60 text-warn-ink',
}

function contactHref(type: string, value: string): string {
  if (type === 'email') return `mailto:${value}`
  if (type === 'phone') return `tel:${value}`
  return value
}

export function ProspectEvidenceBriefView({ brief }: { brief: ProspectEvidenceBriefData }) {
  const aggregate = (brief.aggregate_verdict ?? 'needs_review').replaceAll('_', ' ')
  const qualifications = brief.qualifications ?? [brief.verdict]
  return (
    <>
      <section className="mt-6 rounded-card border border-line-soft bg-card p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="label-caps text-ink-faint">Prospect verdict</p>
            <span
              className={
                'mt-1.5 inline-flex rounded-control border px-2 py-1 font-ui text-sm font-semibold capitalize ' +
                verdictStyle[brief.aggregate_verdict ?? 'needs_review']
              }
            >
              {aggregate}
            </span>
            <p className="mt-2 text-xs capitalize text-ink-faint">
              Evidence quality: {brief.evidence_quality.replaceAll('_', ' ')}
            </p>
          </div>
          <div className="max-w-xl">
            <p className="label-caps text-ink-faint">Why it surfaced</p>
            <p className="mt-1 text-sm text-ink">{brief.aggregate_headline ?? aggregate}</p>
          </div>
        </div>
        <ul className="mt-4 divide-y divide-line-soft">
          {qualifications.map((item) => (
            <li key={item.opportunity_model_id} className="flex items-center justify-between gap-3 py-2">
              <span className="min-w-0 truncate text-sm text-ink">
                {brief.modelLabels?.[item.opportunity_model_id] ?? item.opportunity_model_id}
              </span>
              <span
                className={
                  'shrink-0 rounded-control border px-2 py-0.5 font-ui text-xs font-medium capitalize ' +
                  verdictStyle[item.state]
                }
              >
                {item.state.replaceAll('_', ' ')}
              </span>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-xs text-ink-faint">{brief.verdict.reason}</p>
        <EvidenceList keys={brief.verdict.supporting_evidence_keys} evidence={brief.evidence} />
      </section>

      <Section title="Your objective">
        <dl className="grid gap-3 sm:grid-cols-3">
          {[
            ['Goal', brief.objective.goal],
            ['Your offering', brief.objective.offering],
            ['Desired outcome', brief.objective.desired_outcome],
          ].map(([label, value]) => (
            <div key={label} className="rounded-control border border-line-soft bg-card p-3">
              <dt className="label-caps text-ink-faint">{label}</dt>
              <dd className="mt-1 text-sm text-ink">{value}</dd>
            </div>
          ))}
        </dl>
      </Section>

      <Section title="Evidence-backed findings">
        {brief.findings.length === 0 ? (
          <p className="text-sm text-ink-soft">No additional supported findings were produced.</p>
        ) : (
          <div className="space-y-3">
            {brief.findings.map((finding) => (
              <article key={finding.statement} className="rounded-control border border-line-soft bg-card p-3">
                <span className={'rounded-control px-1.5 py-0.5 font-ui text-[10px] font-medium uppercase ' + evidenceStyle[finding.claim_kind]}>
                  {finding.claim_kind.replaceAll('_', ' ')}
                </span>
                <p className="mt-2 text-sm text-ink">{finding.statement}</p>
                <EvidenceList keys={finding.evidence_keys} evidence={brief.evidence} />
              </article>
            ))}
          </div>
        )}
      </Section>

      <Section title="Contact paths">
        {brief.contacts.length === 0 ? (
          <p className="text-sm text-ink-soft">No verified or observed contact path is available.</p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {brief.contacts.map((contact) => (
              <div key={`${contact.contact_type}-${contact.value}`} className="rounded-control border border-line-soft bg-card p-3">
                <p className="label-caps text-ink-faint">{contact.contact_type.replaceAll('_', ' ')}</p>
                <a
                  href={contactHref(contact.contact_type, contact.value)}
                  target={contact.contact_type === 'email' || contact.contact_type === 'phone' ? undefined : '_blank'}
                  rel="noreferrer"
                  className="mt-1 block break-all text-sm text-action hover:text-ink"
                >
                  {contact.value}
                </a>
                <p className="mt-1 text-xs capitalize text-ink-faint">{contact.state}</p>
              </div>
            ))}
          </div>
        )}
      </Section>

      {brief.pitch_angle && (
        <Section title="Recommended pitch angle">
          <div className="rounded-card border border-line-soft bg-card p-4">
            <p className="text-sm text-ink">{brief.pitch_angle.statement}</p>
            <EvidenceList keys={brief.pitch_angle.evidence_keys} evidence={brief.evidence} />
          </div>
        </Section>
      )}

      {brief.outreach_drafts.length > 0 && (
        <Section title="Grounded outreach drafts">
          <p className="text-xs text-ink-faint">Drafts for manual review and sending. SalesLens does not send them automatically.</p>
          <div className="mt-3 space-y-3">
            {brief.outreach_drafts.map((draft) => (
              <article key={draft.channel} className="rounded-control border border-line-soft bg-card p-3">
                <div className="flex items-center justify-between gap-3">
                  <p className="label-caps text-ink-soft">{draft.channel}</p>
                  <CopyDraftButton text={[draft.subject, draft.message].filter(Boolean).join('\n\n')} />
                </div>
                {draft.subject && <p className="mt-2 text-sm font-semibold text-ink">Subject: {draft.subject}</p>}
                <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-ink">{draft.message}</p>
                {draft.grounding.map((grounding) => (
                  <EvidenceList key={grounding.claim} keys={grounding.evidence_keys} evidence={brief.evidence} />
                ))}
              </article>
            ))}
          </div>
        </Section>
      )}

      {brief.caveats.length > 0 && (
        <Section title="Caveats">
          <ul className="space-y-1.5">
            {brief.caveats.map((caveat) => (
              <li key={caveat} className="rounded-control border border-warn-bg bg-warn-bg/50 p-2.5 text-sm text-warn-ink">
                {caveat}
              </li>
            ))}
          </ul>
        </Section>
      )}

      <Section title="Verified sources">
        {brief.sources.length === 0 ? (
          <p className="text-sm text-ink-soft">No separately stored source entries are available.</p>
        ) : (
          <ul className="divide-y divide-line-soft rounded-card border border-line-soft bg-card">
            {brief.sources.map((source) => (
              <li key={source.key} className="px-4 py-3">
                <a href={source.source_url} target="_blank" rel="noreferrer" className="text-sm text-action hover:text-ink">
                  {source.title ?? source.source_url}
                </a>
                <p className="mt-0.5 text-xs text-ink-faint">{source.provider}</p>
              </li>
            ))}
          </ul>
        )}
      </Section>
    </>
  )
}
