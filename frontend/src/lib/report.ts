export interface Citation {
  source_url: string
  supporting_excerpt: string | null
}

export interface Finding {
  statement: string
  citations: Citation[]
  is_inference: boolean
  rationale: string
}

export interface CompanyProfile {
  company_summary: Finding
  company_description: Finding | null
  industry: Finding | null
  headquarters: Finding | null
  employee_count: Finding | null
  company_size: Finding | null
  website_metadata: Finding | null
  products_and_services: Finding[]
  funding_information: Finding[]
}

export interface TechnologyItem {
  technology: Finding
  implication: Finding | null
}

export interface BusinessSignal {
  signal_type: 'news' | 'hiring' | 'expansion' | 'funding' | 'announcement'
  finding: Finding
  occurred_at: string | null
}

export interface LegacyReportData {
  executive_summary: Finding
  company_profile: CompanyProfile
  technologies: TechnologyItem[]
  business_signals: BusinessSignal[]
  opportunity_assessment: { score: number; reasons: Finding[] }
  contact_recommendation: { recommendation: string; rationale: Finding }
  confidence: { score: number; rationale: string }
  pain_points: { hypothesis: Finding; confidence: string }[]
  strategy: {
    recommended_strategy: Finding
    recommended_sales_angle: Finding
    suggested_value_proposition: Finding
  }
  suggested_decision_makers: { suggested_role: string; rationale: Finding }[]
  personalized_outreach: {
    cold_email: string
    linkedin_message: string
    personalization_rationale: Finding
  }
  caveats: string[]
}

export interface BriefEvidence {
  key: string
  signal_type: string
  evidence_type: 'observed' | 'inference'
  supporting_value: string
  numeric_value: number | null
  source: {
    provider: string
    provider_record_id: string | null
    source_url: string | null
    retrieved_at: string
  }
  captured_at: string
}

export interface ProspectEvidenceBriefData {
  objective: {
    goal: string
    offering: string
    desired_outcome: string
  }
  prospect: {
    business_name: string
    location: string | null
    official_website: string | null
    identity_verified: boolean
  }
  verdict: {
    opportunity_model_id: string
    state: 'likely' | 'insufficient_evidence' | 'not_eligible'
    reason: string
    supporting_evidence_keys: string[]
    evaluated_at: string
  }
  evidence_quality: 'high' | 'medium' | 'needs_review'
  findings: {
    statement: string
    claim_kind: 'observed' | 'derived_metric' | 'inference'
    evidence_keys: string[]
  }[]
  contacts: {
    contact_type: string
    value: string
    state: 'verified' | 'observed'
    source_keys: string[]
  }[]
  pitch_angle: {
    statement: string
    offering: string
    evidence_keys: string[]
  } | null
  outreach_drafts: {
    channel: 'email' | 'linkedin'
    subject: string | null
    message: string
    offering: string
    grounding: { claim: string; evidence_keys: string[] }[]
  }[]
  caveats: string[]
  evidence: BriefEvidence[]
  sources: {
    key: string
    provider: string
    source_url: string
    retrieved_at: string
    title: string | null
    excerpt: string | null
  }[]
}

export type ReportData = LegacyReportData | ProspectEvidenceBriefData

export interface ReportSummary {
  id: string
  research_request_id: string
  company_id: string
  report_kind: 'sales_intelligence' | 'prospect_evidence_brief'
  opportunity_score: number | null
  contact_recommendation: string | null
  review_status: 'draft' | 'approved'
  approved_at: string | null
  review_note: string | null
  report_data: ReportData
  generated_at: string
  created_at: string
}

export interface SourceItem {
  id: string
  url: string
  title: string | null
  excerpt: string | null
  source_type: string
  retrieved_at: string
}

import type { DiscoveryObjective } from './types'

export interface ReportDetail {
  report: ReportSummary
  sources: SourceItem[]
  goal?: string | null
  objective?: DiscoveryObjective | null
}

export function isProspectEvidenceBrief(
  report: ReportSummary,
): report is ReportSummary & { report_data: ProspectEvidenceBriefData } {
  return report.report_kind === 'prospect_evidence_brief'
}

export function buildCitationIndex(sources: SourceItem[]): Map<string, number> {
  const index = new Map<string, number>()
  sources.forEach((source, position) => {
    index.set(source.url.replace(/\/+$/, ''), position + 1)
  })
  return index
}

export function domainOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}
