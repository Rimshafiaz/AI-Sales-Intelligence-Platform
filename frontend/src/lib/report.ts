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

export interface ReportData {
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

export interface ReportSummary {
  id: string
  research_request_id: string
  company_id: string
  opportunity_score: number
  contact_recommendation: string
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

export interface ReportDetail {
  report: ReportSummary
  sources: SourceItem[]
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
