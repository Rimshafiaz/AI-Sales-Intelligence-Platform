export interface DiscoveryCandidate {
  company_name: string
  website: string | null
  industry: string | null
  short_description: string | null
  match_explanation: string
  supporting_source_urls: string[]
  fit_score: number | null
  fit_tier: 'high' | 'medium' | 'low' | null
  fit_reason: string | null
}

export interface DiscoveryResponse {
  candidates: DiscoveryCandidate[]
}

export interface DiscoveryObjective {
  goal_type: string
  seller_role: string | null
  offering: string | null
  target_sectors: string[]
  target_geographies: string[]
  company_size: string | null
  stage: string | null
  triggers: string[]
  signals_to_look_for: string[]
  decision_makers: string[]
  search_queries: string[]
  fit_rubric: string
  desired_outcome: string
}

export interface ParseDiscoveryResponse {
  objective: DiscoveryObjective
  supported: boolean
  message: string | null
}

export interface Company {
  id: string
  name: string
  website: string | null
  created_at: string
  updated_at: string
}

export interface ResearchRequest {
  id: string
  company_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  created_at: string
  updated_at: string
  started_at: string | null
  finished_at: string | null
  error_message: string | null
}

export interface ResearchSource {
  id: string
  url: string
  title: string | null
  excerpt: string | null
  source_type: string
  retrieved_at: string
}

export interface ReportListItem {
  id: string
  research_request_id: string
  company_id: string
  company_name: string
  opportunity_score: number
  contact_recommendation: string
  review_status: 'draft' | 'approved'
  generated_at: string
}

export interface ReportListResponse {
  items: ReportListItem[]
  total: number
  page: number
  page_size: number
}

export interface DashboardActivity {
  event_type: string
  company_name: string
  status: string | null
  occurred_at: string
}

export interface DashboardSummary {
  reports_generated: number
  companies_researched: number
  industries_researched: number
  most_researched_industries: { industry: string; report_count: number }[]
  average_opportunity_score: number | null
  recent_activity: DashboardActivity[]
}
